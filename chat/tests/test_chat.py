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

from billing.models import BillingAccount, UsageCharge
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



class MeteredSendTests(MockedProviderTestCase):
    """Phase 7: sending charges the session's billing account."""

    def set_credit(self, credit, status=BillingAccount.Status.ACTIVE):
        BillingAccount.objects.filter(pk=self.account.pk).update(credit=Decimal(credit), status=status)

    def credit(self):
        return BillingAccount.objects.get(pk=self.account.pk).credit

    def test_successful_send_deducts_exact_cost_and_links_charge(self):
        self.mock_complete()  # 187 in / 9 out on Luna ($0.40 / $1.60) -> $0.000089
        self.client.post(self.send_url, {'content': 'HELLO'})

        reply = self.session.messages.get(role='assistant')
        charge = UsageCharge.objects.get()
        self.assertEqual(reply.cost, Decimal('0.000089'))
        self.assertEqual(charge.message, reply)
        self.assertEqual(charge.cost, Decimal('0.000089'))
        self.assertEqual((charge.input_tokens, charge.output_tokens), (187, 9))
        self.assertEqual(charge.billing_account, self.account)
        self.assertEqual(self.credit(), Decimal('2.00') - Decimal('0.000089'))

    def test_zero_credit_blocks_send_without_calling_proxy(self):
        self.set_credit('0')
        complete = self.mock_complete()
        response = self.client.post(self.send_url, {'content': 'HELLO'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Insufficient credit in [Personal] HANS LIAM YU. Ask an administrator to top up.')
        self.assertContains(response, 'HELLO</textarea>')
        complete.assert_not_called()
        self.assertFalse(self.session.messages.exists())
        self.assertFalse(UsageCharge.objects.exists())
        self.assertEqual(self.credit(), Decimal('0'))

    def test_suspended_account_blocks_send_without_calling_proxy(self):
        self.set_credit('5', status=BillingAccount.Status.SUSPENDED)
        complete = self.mock_complete()
        response = self.client.post(self.send_url, {'content': 'HELLO'})
        self.assertContains(response, 'This billing account is not active.')
        complete.assert_not_called()
        self.assertFalse(self.session.messages.exists())

    def test_provider_error_charges_nothing(self):
        self.mock_complete(side_effect=ProviderError('upstream', status_code=502))
        self.client.post(self.send_url, {'content': 'HELLO'})
        self.assertEqual(self.credit(), Decimal('2.00'))
        self.assertFalse(UsageCharge.objects.exists())
        self.assertFalse(self.session.messages.exists())

    def test_truncated_reply_is_charged(self):
        self.mock_complete(return_value=CompletionResult(text='cut', status='truncated',
                                                         input_tokens=200, output_tokens=1024))
        self.client.post(self.send_url, {'content': 'Write an essay.'})
        expected = Decimal('0.001718')  # 200 x 0.40/1M + 1024 x 1.60/1M = 0.00008 + 0.0016384
        self.assertEqual(UsageCharge.objects.get().cost, expected)
        self.assertEqual(self.credit(), Decimal('2.00') - expected)
        self.assertEqual(self.session.messages.get(role='assistant').status, Message.Status.TRUNCATED)

    def test_low_but_positive_credit_allows_final_overdraw(self):
        self.set_credit('0.00005')
        self.mock_complete()
        self.client.post(self.send_url, {'content': 'HELLO'})
        self.assertEqual(self.credit(), Decimal('-0.000039'))
        complete = self.mock_complete()
        response = self.client.post(self.send_url, {'content': 'again'})
        self.assertContains(response, 'Insufficient credit')
        complete.assert_not_called()

    def test_charge_failure_rolls_back_messages_and_credit(self):
        self.mock_complete()
        with mock.patch('billing.services.UsageCharge.objects.create', side_effect=RuntimeError('db down')), \
                self.assertRaises(RuntimeError):
            services.send_message(self.session, 'HELLO')
        self.assertFalse(self.session.messages.exists())
        self.assertEqual(self.credit(), Decimal('2.00'))

    def test_two_sessions_on_same_account_share_the_balance(self):
        haiku = LLMModel.objects.get(api_model='claude-haiku-4-5-20251001')
        other = ChatSession.objects.create(user=self.hans, billing_account=self.account, llm_model=haiku)
        self.mock_complete()
        self.client.post(self.send_url, {'content': 'one'})           # Luna: 0.000089
        self.client.post(f'/chat/{other.pk}/send/', {'content': 'two'})  # Haiku: 187 x 1/1M + 9 x 5/1M = 0.000232
        self.assertEqual(self.credit(), Decimal('2.00') - Decimal('0.000089') - Decimal('0.000232'))
        self.assertEqual(UsageCharge.objects.filter(billing_account=self.account).count(), 2)

    def test_profile_shows_updated_balance(self):
        self.mock_complete(return_value=CompletionResult(text='long', status='complete',
                                                         input_tokens=100_000, output_tokens=100_000))
        self.client.post(self.send_url, {'content': 'HELLO'})  # 0.04 + 0.16 = 0.20
        self.assertContains(self.client.get('/profile/'), '$1.80')


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

    def test_only_the_session_page_uses_the_chat_layout(self):
        # app-chat gives the session page its fixed-height layout (composer at the bottom).
        self.assertContains(self.client.get(self.url), '<div class="app app-chat">')
        for url in ('/chat/', '/chat/new/', '/profile/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, '<div class="app">')
                self.assertNotContains(response, 'app-chat')

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


class BillingMembershipTests(MockedProviderTestCase):
    """QA fix: membership of the session's billing account is re-checked on every send."""

    def test_removed_member_gets_403_and_nothing_is_sent_saved_or_charged(self):
        complete = self.mock_complete()
        self.account.members.remove(self.hans)

        response = self.client.post(self.send_url, {'content': 'charge the old account'})

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'You are no longer a member of [Personal] HANS LIAM YU', status_code=403)
        self.assertContains(response, 'charge the old account</textarea>', status_code=403)
        complete.assert_not_called()
        self.assertFalse(self.session.messages.exists())
        self.assertFalse(UsageCharge.objects.exists())
        self.assertEqual(BillingAccount.objects.get(pk=self.account.pk).credit, Decimal('2.00'))

    def test_removed_member_can_still_read_their_history(self):
        Message.objects.create(session=self.session, role='user', content='old question')
        self.account.members.remove(self.hans)
        self.assertContains(self.client.get(self.url), 'old question')

    def test_shared_account_member_can_send(self):
        shared = BillingAccount.objects.create(name='CLASS ITENT 45', kind=BillingAccount.Kind.SHARED,
                                               credit=Decimal('5.00'))
        shared.members.add(self.hans, self.other)
        session = ChatSession.objects.create(user=self.hans, billing_account=shared, llm_model=self.luna)
        self.mock_complete()
        response = self.client.post(f'/chat/{session.pk}/send/', {'content': 'hi'})
        self.assertRedirects(response, f'/chat/{session.pk}/')
        self.assertEqual(UsageCharge.objects.get().billing_account, shared)

    def test_removed_from_shared_account_is_blocked(self):
        shared = BillingAccount.objects.create(name='CLASS ITENT 45', kind=BillingAccount.Kind.SHARED,
                                               credit=Decimal('5.00'))
        shared.members.add(self.hans, self.other)
        session = ChatSession.objects.create(user=self.hans, billing_account=shared, llm_model=self.luna)
        shared.members.remove(self.hans)
        complete = self.mock_complete()
        response = self.client.post(f'/chat/{session.pk}/send/', {'content': 'hi'})
        self.assertEqual(response.status_code, 403)
        complete.assert_not_called()
        self.assertEqual(BillingAccount.objects.get(pk=shared.pk).credit, Decimal('5.00'))
