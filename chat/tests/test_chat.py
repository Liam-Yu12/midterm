"""Phase 6: sending messages and keeping history, with the provider adapter mocked.

`llm.providers.complete` is replaced by a mock in every test. As a second guard,
`llm.providers.requests.post` is patched to fail the test if anything reaches it.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from billing.models import BillingAccount
from chat import services
from chat.models import ChatSession, Message
from llm.models import LLMModel
from llm.providers import CompletionResult, ProviderError, Turn

User = get_user_model()

OK_REPLY = CompletionResult(text='Hello! How can I help you today?', status='complete',
                            input_tokens=187, output_tokens=9)


class MockedProviderTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hans = User.objects.create_user('hans', password='x')
        cls.other = User.objects.create_user('other', password='x')
        cls.account = BillingAccount.objects.create(name='HANS LIAM YU', credit=Decimal('2.00'))
        cls.account.members.add(cls.hans)
        cls.luna = LLMModel.objects.get(api_model='gpt-5.6-luna')

    def setUp(self):
        network_guard = mock.patch('llm.providers.requests.post',
                                   side_effect=AssertionError('tests must not call the proxy'))
        network_guard.start()
        self.addCleanup(network_guard.stop)
        self.session = ChatSession.objects.create(user=self.hans, billing_account=self.account, llm_model=self.luna)
        self.url = f'/chat/{self.session.pk}/'
        self.send_url = f'/chat/{self.session.pk}/send/'
        self.client.force_login(self.hans)

    def mock_complete(self, **kwargs):
        patcher = mock.patch('llm.providers.complete', **({'return_value': OK_REPLY} | kwargs))
        complete = patcher.start()
        self.addCleanup(patcher.stop)
        return complete


class SendMessageTests(MockedProviderTestCase):
    def test_send_saves_user_message_and_reply_then_redirects(self):
        complete = self.mock_complete()

        response = self.client.post(self.send_url, {'content': '  HELLO  '})

        self.assertRedirects(response, self.url)
        user_msg, reply = self.session.messages.all()
        self.assertEqual((user_msg.role, user_msg.content), ('user', 'HELLO'))
        self.assertEqual((reply.role, reply.content, reply.status), ('assistant', OK_REPLY.text, 'complete'))
        self.assertEqual((reply.input_tokens, reply.output_tokens), (187, 9))
        complete.assert_called_once_with(self.luna, [Turn('user', 'HELLO')])

    def test_reply_is_shown_on_session_page(self):
        self.mock_complete()
        response = self.client.post(self.send_url, {'content': 'HELLO'}, follow=True)
        self.assertContains(response, 'class="bubble bubble-user"')
        self.assertContains(response, 'HELLO')
        self.assertContains(response, 'Hello! How can I help you today?')
        self.assertNotContains(response, 'No messages yet.')

    def test_second_message_sends_full_history(self):
        complete = self.mock_complete(side_effect=[
            OK_REPLY,
            CompletionResult(text='Your name is Hans.', status='complete', input_tokens=210, output_tokens=6),
        ])

        self.client.post(self.send_url, {'content': 'My name is Hans.'})
        self.client.post(self.send_url, {'content': 'What is my name?'})

        second_turns = complete.call_args_list[1].args[1]
        self.assertEqual(second_turns, [
            Turn('user', 'My name is Hans.'),
            Turn('assistant', OK_REPLY.text),
            Turn('user', 'What is my name?'),
        ])
        self.assertEqual(
            list(self.session.messages.values_list('role', 'content')),
            [('user', 'My name is Hans.'), ('assistant', OK_REPLY.text),
             ('user', 'What is my name?'), ('assistant', 'Your name is Hans.')],
        )

    def test_uses_the_sessions_model(self):
        haiku = LLMModel.objects.get(api_model='claude-haiku-4-5-20251001')
        session = ChatSession.objects.create(user=self.hans, billing_account=self.account, llm_model=haiku)
        complete = self.mock_complete()
        self.client.post(f'/chat/{session.pk}/send/', {'content': 'hi'})
        self.assertEqual(complete.call_args.args[0], haiku)

    def test_truncated_reply_is_saved_and_marked(self):
        self.mock_complete(return_value=CompletionResult(text='A long answer that stops', status='truncated',
                                                         input_tokens=190, output_tokens=1024))
        response = self.client.post(self.send_url, {'content': 'Write an essay.'}, follow=True)
        self.assertEqual(self.session.messages.last().status, Message.Status.TRUNCATED)
        self.assertContains(response, '(reply cut off: token limit)')

    def test_blank_message_is_rejected_without_calling_provider(self):
        complete = self.mock_complete()
        response = self.client.post(self.send_url, {'content': '   '})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please type a message.')
        complete.assert_not_called()
        self.assertFalse(self.session.messages.exists())

    def test_overlong_message_is_rejected_and_draft_kept(self):
        complete = self.mock_complete()
        draft = 'x' * (services.MAX_MESSAGE_LENGTH + 1)
        response = self.client.post(self.send_url, {'content': draft})
        self.assertContains(response, 'at most 8,000 characters')
        self.assertEqual(response.context['draft'], draft)
        complete.assert_not_called()

    def test_provider_error_saves_nothing_and_keeps_draft(self):
        self.mock_complete(side_effect=ProviderError('timeout'))
        response = self.client.post(self.send_url, {'content': 'Are you there?'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'took too long to respond')
        self.assertContains(response, 'Are you there?</textarea>')
        self.assertFalse(self.session.messages.exists())

    def test_successful_send_moves_session_to_top(self):
        self.mock_complete()
        long_ago = timezone.now() - timedelta(days=3)
        ChatSession.objects.filter(pk=self.session.pk).update(updated_at=long_ago)
        self.client.post(self.send_url, {'content': 'bump'})
        self.session.refresh_from_db()
        self.assertGreater(self.session.updated_at, long_ago)

    def test_does_not_touch_credit_yet(self):
        # Metering arrives in Phase 7; until then sending must not change the balance.
        self.mock_complete()
        self.client.post(self.send_url, {'content': 'HELLO'})
        self.account.refresh_from_db()
        self.assertEqual(self.account.credit, Decimal('2.00'))
        self.assertIsNone(self.session.messages.last().cost)


class SendAccessTests(MockedProviderTestCase):
    def test_other_users_session_is_404_on_get_and_send(self):
        complete = self.mock_complete()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.send_url, {'content': 'hi'}).status_code, 404)
        complete.assert_not_called()

    def test_anonymous_send_redirects_to_login(self):
        self.client.logout()
        response = self.client.post(self.send_url, {'content': 'hi'})
        self.assertRedirects(response, f'/login/?next={self.send_url}', fetch_redirect_response=False)

    def test_send_requires_post(self):
        self.assertEqual(self.client.get(self.send_url).status_code, 405)


class SessionPageTests(MockedProviderTestCase):
    def test_page_has_message_form_and_script(self):
        response = self.client.get(self.url)
        self.assertContains(response, f'action="{self.send_url}"')
        self.assertContains(response, 'name="content"')
        self.assertContains(response, '/static/js/chat.js')
        self.assertContains(response, 'Model: GPT-5.6 Luna')

    def test_history_is_rendered_in_order(self):
        for role, content in [('user', 'first'), ('assistant', 'second'), ('user', 'third')]:
            Message.objects.create(session=self.session, role=role, content=content)
        content = self.client.get(self.url).content.decode()
        self.assertLess(content.index('first'), content.index('second'))
        self.assertLess(content.index('second'), content.index('third'))


class BuildTurnsTests(MockedProviderTestCase):
    def test_build_turns_returns_stored_messages_oldest_first(self):
        Message.objects.create(session=self.session, role='user', content='a')
        Message.objects.create(session=self.session, role='assistant', content='b')
        self.assertEqual(services.build_turns(self.session), [Turn('user', 'a'), Turn('assistant', 'b')])

    def test_build_turns_is_empty_for_new_session(self):
        self.assertEqual(services.build_turns(self.session), [])
