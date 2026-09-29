"""Automatic session naming (plan/auto-session-naming.md) and the header rename control."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from billing.models import BillingAccount
from chat.models import ChatSession
from chat.naming import MAX_LENGTH, MAX_WORDS, suggest_session_name
from llm.models import LLMModel
from llm.providers import CompletionResult, ProviderError

User = get_user_model()
REPLY = CompletionResult(text='Sure!', status='complete', input_tokens=190, output_tokens=3)


class SuggestSessionNameTests(SimpleTestCase):
    def test_examples_from_the_spec(self):
        self.assertEqual(suggest_session_name('What are some good study techniques for biology?'),
                         'Study techniques for biology')
        self.assertEqual(suggest_session_name('hello'), 'hello')
        # "Plan Japan trip" would need reordering; the local heuristic keeps word order.
        self.assertEqual(suggest_session_name('Help me plan my trip to Japan next month'),
                         'Plan trip to Japan next month')

    def test_strips_greetings_and_fillers(self):
        self.assertEqual(suggest_session_name('Hi! Can you please explain how photosynthesis works?'),
                         'Explain how photosynthesis works')
        self.assertEqual(suggest_session_name('how do i cook rice without a rice cooker'),
                         'Cook rice without rice cooker')
        self.assertEqual(suggest_session_name('Tell me about the Roman Empire'), 'Roman Empire')

    def test_keeps_the_users_own_opening(self):
        self.assertEqual(suggest_session_name('My name is Hans.'), 'My name is Hans')
        self.assertEqual(suggest_session_name('Good morning'), 'Good morning')

    def test_collapses_whitespace_and_uses_first_sentence(self):
        self.assertEqual(suggest_session_name('   lots    of\n\n  spaces   here  '), 'lots of spaces here')
        self.assertEqual(suggest_session_name('Summarize this: ' + 'word ' * 500), 'Summarize this')
        self.assertEqual(suggest_session_name('Plan a party. Also invite Sam and Lee.'), 'Plan party')

    def test_long_messages_give_short_valid_names(self):
        long_text = ('I need you to review my Django models and tell me whether the billing design '
                     'makes sense for a metered chat app with several providers ') * 20
        for message in (long_text, 'x' * 5000, 'Supercalifragilistic ' * 50):
            with self.subTest(message=message[:30]):
                name = suggest_session_name(message)
                self.assertTrue(name)
                self.assertLessEqual(len(name), MAX_LENGTH)
                self.assertLessEqual(len(name.split()), MAX_WORDS)
                self.assertLessEqual(len(name), ChatSession._meta.get_field('name').max_length)
        self.assertEqual(suggest_session_name('x' * 5000), 'x' * (MAX_LENGTH - 1) + '…')

    def test_no_dangling_connector_words(self):
        name = suggest_session_name('Explain the difference between TCP and UDP to me please')
        self.assertNotIn(name.split()[-1].lower(), {'to', 'and', 'for', 'of', 'the'})

    def test_falls_back_when_nothing_useful(self):
        for message in ('', '   ', '???', '!!! ...'):
            with self.subTest(message=message):
                self.assertEqual(suggest_session_name(message), 'Untitled session')
        self.assertEqual(suggest_session_name('please'), 'please')  # all-filler: keep the raw words


class AutoNamingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('hans', password='x')
        cls.account = BillingAccount.objects.create(name='HANS', credit=Decimal('2.00'))
        cls.account.members.add(cls.user)
        cls.model = LLMModel.objects.get(api_model='gpt-5.6-luna')

    def setUp(self):
        guard = mock.patch('llm.providers.requests.post', side_effect=AssertionError('no proxy calls in tests'))
        guard.start()
        self.addCleanup(guard.stop)
        self.client.force_login(self.user)
        self.session = ChatSession.objects.create(user=self.user, billing_account=self.account, llm_model=self.model)

    def send(self, text, **mock_kwargs):
        with mock.patch('llm.providers.complete', **({'return_value': REPLY} | mock_kwargs)) as complete:
            response = self.client.post(f'/chat/{self.session.pk}/send/', {'content': text})
        self.session.refresh_from_db()
        return response, complete

    def rename(self, name):
        response = self.client.post(f'/chat/{self.session.pk}/rename/', {'name': name}, follow=True)
        self.session.refresh_from_db()
        return response


class AutoNamingTests(AutoNamingTestCase):
    def test_new_sessions_start_untitled(self):
        self.assertEqual(self.session.name, 'Untitled session')
        self.assertFalse(self.session.name_set_by_user)

    def test_first_successful_message_names_the_session(self):
        response, complete = self.send('What are some good study techniques for biology?')
        self.assertEqual(self.session.name, 'Study techniques for biology')
        self.assertFalse(self.session.name_set_by_user)
        self.assertEqual(complete.call_count, 1)  # no extra call just for the name
        page = self.client.get(f'/chat/{self.session.pk}/')
        self.assertContains(page, '<h1>Study techniques for biology</h1>', html=True)
        self.assertContains(page, '<span class="session-name">Study techniques for biology</span>', html=True)

    def test_message_text_is_unchanged(self):
        self.send('  What are some good study techniques for biology?  ')
        self.assertEqual(self.session.messages.first().content, 'What are some good study techniques for biology?')

    def test_later_messages_do_not_rename(self):
        self.send('Help me plan my trip to Japan next month')
        first_name = self.session.name
        self.send('Actually, what about Korea instead?')
        self.send('hello')
        self.assertEqual(self.session.name, first_name)

    def test_failed_first_message_does_not_rename_but_next_success_does(self):
        self.send('Plan a birthday party', side_effect=ProviderError('timeout'))
        self.assertEqual(self.session.name, 'Untitled session')
        self.assertFalse(self.session.messages.exists())
        self.send('Plan a birthday party')  # first *successful* message
        self.assertEqual(self.session.name, 'Plan birthday party')

    def test_blocked_first_message_does_not_rename(self):
        BillingAccount.objects.filter(pk=self.account.pk).update(credit=Decimal('0'))
        self.send('Plan a birthday party')
        self.assertEqual(self.session.name, 'Untitled session')

    def test_manual_rename_before_first_message_is_never_overwritten(self):
        self.rename('My project')
        self.send('What are some good study techniques for biology?')
        self.assertEqual(self.session.name, 'My project')

    def test_manual_rename_to_default_name_is_still_respected(self):
        self.rename('Untitled session')
        self.assertTrue(self.session.name_set_by_user)
        self.send('What are some good study techniques for biology?')
        self.assertEqual(self.session.name, 'Untitled session')

    def test_manual_rename_after_auto_name_sticks(self):
        self.send('What are some good study techniques for biology?')
        self.rename('Biology revision')
        self.send('And for chemistry?')
        self.assertEqual(self.session.name, 'Biology revision')

    def test_long_first_message_gives_short_valid_name(self):
        self.send('Please ' + 'analyse this very long paragraph about many different topics ' * 60)
        self.assertLessEqual(len(self.session.name), MAX_LENGTH)
        self.assertLessEqual(len(self.session.name.split()), MAX_WORDS)
        self.assertTrue(self.session.name.startswith('Analyse'))

    def test_sessions_with_a_preset_name_are_not_auto_renamed(self):
        self.session.name = 'Named by admin'
        self.session.save()
        self.send('What are some good study techniques for biology?')
        self.assertEqual(self.session.name, 'Named by admin')


class RenameControlTests(AutoNamingTestCase):
    def test_rename_still_works_and_marks_the_name_as_users(self):
        response = self.rename('  Trip planning  ')
        self.assertEqual(self.session.name, 'Trip planning')
        self.assertTrue(self.session.name_set_by_user)
        self.assertContains(response, '<h1>Trip planning</h1>', html=True)

    def test_blank_rename_is_still_rejected(self):
        response = self.rename('   ')
        self.assertEqual(self.session.name, 'Untitled session')
        self.assertFalse(self.session.name_set_by_user)
        self.assertContains(response, 'Session name can&#x27;t be blank.')

    def test_rename_keeps_the_100_character_limit(self):
        self.rename('y' * 150)
        self.assertEqual(self.session.name, 'y' * 100)

    def test_rename_and_delete_sit_side_by_side_in_the_header(self):
        html = self.client.get(f'/chat/{self.session.pk}/').content.decode()
        actions = html[html.index('<div class="session-actions">'):]
        actions = actions[:actions.index('</div>')]
        self.assertIn('aria-label="Rename session"', actions)
        self.assertIn('aria-label="Delete session"', actions)
        self.assertLess(actions.index('Rename session'), actions.index('Delete session'))
        self.assertIn(f'action="/chat/{self.session.pk}/rename/"', actions)  # same rename form/view
        self.assertIn(f'href="/chat/{self.session.pk}/delete/"', actions)    # same delete confirmation

    def test_sidebar_items_stay_uncluttered(self):
        html = self.client.get(f'/chat/{self.session.pk}/').content.decode()
        sidebar = html[html.index('<ul class="session-list">'):html.index('</ul>')]
        self.assertNotIn('Rename session', sidebar)
        self.assertEqual(sidebar.count('session-delete'), 1)
