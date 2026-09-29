"""Phases 8-10: the sidebar session list, rename and delete."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from billing.models import BillingAccount
from chat.models import ChatSession, Message
from llm.models import LLMModel
from llm.providers import CompletionResult, Turn

User = get_user_model()


class SessionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hans = User.objects.create_user('hans', password='hans-pass-123')
        cls.other = User.objects.create_user('other', password='x')
        cls.account = BillingAccount.objects.create(name='HANS LIAM YU', credit=Decimal('2.00'))
        cls.account.members.add(cls.hans)
        cls.other_account = BillingAccount.objects.create(name='OTHER PERSON', credit=Decimal('2.00'))
        cls.other_account.members.add(cls.other)
        cls.luna = LLMModel.objects.get(api_model='gpt-5.6-luna')
        cls.gemini = LLMModel.objects.get(api_model='gemini-3.8-flash')

    def setUp(self):
        # No test here may reach the proxy.
        guard = mock.patch('llm.providers.requests.post', side_effect=AssertionError('tests must not call the proxy'))
        guard.start()
        self.addCleanup(guard.stop)
        self.client.force_login(self.hans)

    def make_session(self, name='Untitled session', user=None, model=None, age_days=0):
        user = user or self.hans
        session = ChatSession.objects.create(
            user=user, name=name, llm_model=model or self.luna,
            billing_account=self.account if user == self.hans else self.other_account,
        )
        if age_days:
            ChatSession.objects.filter(pk=session.pk).update(updated_at=timezone.now() - timedelta(days=age_days))
            session.refresh_from_db()
        return session

    def sidebar_names(self, response):
        return [s.name for s in response.context['sidebar_sessions']]


class SidebarTests(SessionTestCase):
    def test_lists_only_own_sessions_most_recent_first(self):
        self.make_session('Oldest', age_days=5)
        self.make_session('Newest')
        self.make_session('Middle', age_days=2)
        self.make_session('Not mine', user=self.other)

        response = self.client.get('/chat/')
        self.assertEqual(self.sidebar_names(response), ['Newest', 'Middle', 'Oldest'])
        self.assertNotContains(response, 'Not mine')

    def test_item_shows_name_date_and_link(self):
        session = self.make_session('Trip planning')
        response = self.client.get('/chat/')
        self.assertContains(response, f'href="/chat/{session.pk}/"')
        self.assertContains(response, 'Trip planning')
        self.assertContains(response, session.updated_at.strftime('%b ') + str(session.updated_at.day))

    def test_current_session_is_highlighted(self):
        current = self.make_session('Current')
        self.make_session('Another')
        response = self.client.get(f'/chat/{current.pk}/')
        content = response.content.decode()
        self.assertEqual(content.count('session-item active'), 1)
        self.assertLess(content.index('session-item active'), content.index('>Current<'))
        self.assertContains(response, 'aria-current="page"', count=1)

    def test_no_highlight_off_session_pages(self):
        self.make_session('Current')
        self.assertNotContains(self.client.get('/chat/'), 'session-item active')

    def test_empty_list_message(self):
        self.assertContains(self.client.get('/chat/'), 'No sessions yet.')

    def test_sidebar_appears_on_every_app_page(self):
        self.make_session('Everywhere')
        for url in ('/chat/', '/chat/new/', '/profile/'):
            with self.subTest(url=url):
                self.assertEqual(self.sidebar_names(self.client.get(url)), ['Everywhere'])


class HistoryTests(SessionTestCase):
    def test_reopening_a_session_renders_all_messages_in_order(self):
        session = self.make_session('Old chat', age_days=3)
        for role, text in [('user', 'alpha'), ('assistant', 'bravo'), ('user', 'charlie'), ('assistant', 'delta')]:
            Message.objects.create(session=session, role=role, content=text)
        self.make_session('Newer chat')

        content = self.client.get(f'/chat/{session.pk}/').content.decode()
        positions = [content.index(word) for word in ('alpha', 'bravo', 'charlie', 'delta')]
        self.assertEqual(positions, sorted(positions))

    def test_sending_in_an_older_session_continues_its_history(self):
        session = self.make_session('Old chat', age_days=3)
        Message.objects.create(session=session, role='user', content='My name is Hans.')
        Message.objects.create(session=session, role='assistant', content='Hi Hans!')
        reply = CompletionResult(text='Your name is Hans.', status='complete', input_tokens=190, output_tokens=5)
        with mock.patch('llm.providers.complete', return_value=reply) as complete:
            self.client.post(f'/chat/{session.pk}/send/', {'content': 'What is my name?'})
        self.assertEqual(complete.call_args.args[1], [
            Turn('user', 'My name is Hans.'), Turn('assistant', 'Hi Hans!'), Turn('user', 'What is my name?'),
        ])
        # Sending moved the older session to the top.
        self.assertEqual(self.sidebar_names(self.client.get('/chat/'))[0], 'Old chat')

    def test_sessions_and_history_persist_across_logout_and_login(self):
        luna_chat = self.make_session('Luna chat')
        gemini_chat = self.make_session('Gemini chat', model=self.gemini)
        Message.objects.create(session=luna_chat, role='user', content='kept message')

        self.client.post('/logout/')
        self.assertTrue(self.client.login(username='hans', password='hans-pass-123'))

        self.assertEqual(sorted(self.sidebar_names(self.client.get('/chat/'))), ['Gemini chat', 'Luna chat'])
        self.assertContains(self.client.get(f'/chat/{luna_chat.pk}/'), 'kept message')
        self.assertContains(self.client.get(f'/chat/{gemini_chat.pk}/'), 'Model: Gemini 3.8 Flash')


class RenameTests(SessionTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.make_session('Untitled session', age_days=1)
        self.url = f'/chat/{self.session.pk}/rename/'

    def test_owner_can_rename_and_name_shows_in_header_and_sidebar(self):
        response = self.client.post(self.url, {'name': '  Trip planning  '}, follow=True)
        self.assertRedirects(response, f'/chat/{self.session.pk}/')
        self.session.refresh_from_db()
        self.assertEqual(self.session.name, 'Trip planning')
        self.assertContains(response, '<h1>Trip planning</h1>', html=True)
        self.assertEqual(self.sidebar_names(response), ['Trip planning'])

    def test_name_is_capped_at_100_characters(self):
        self.client.post(self.url, {'name': 'x' * 150})
        self.session.refresh_from_db()
        self.assertEqual(self.session.name, 'x' * 100)

    def test_blank_name_is_rejected_and_old_name_kept(self):
        response = self.client.post(self.url, {'name': '   '}, follow=True)
        self.session.refresh_from_db()
        self.assertEqual(self.session.name, 'Untitled session')
        self.assertContains(response, "Session name can&#x27;t be blank.")

    def test_rename_does_not_reorder_sessions(self):
        before = self.session.updated_at
        self.client.post(self.url, {'name': 'Renamed'})
        self.session.refresh_from_db()
        self.assertEqual(self.session.updated_at, before)

    def test_other_user_gets_404_and_name_is_unchanged(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, {'name': 'Hacked'}).status_code, 404)
        self.session.refresh_from_db()
        self.assertEqual(self.session.name, 'Untitled session')

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        self.assertRedirects(self.client.post(self.url, {'name': 'x'}),
                             f'/login/?next={self.url}', fetch_redirect_response=False)

    def test_session_page_has_rename_form(self):
        response = self.client.get(f'/chat/{self.session.pk}/')
        self.assertContains(response, f'action="{self.url}"')
        self.assertContains(response, 'name="name"')


class DeleteTests(SessionTestCase):
    def setUp(self):
        super().setUp()
        self.session = self.make_session('Trip planning')
        self.url = f'/chat/{self.session.pk}/delete/'

    def send_paid_message(self):
        reply = CompletionResult(text='Sure!', status='complete', input_tokens=1000, output_tokens=500)
        with mock.patch('llm.providers.complete', return_value=reply):
            self.client.post(f'/chat/{self.session.pk}/send/', {'content': 'Plan a trip'})

    def test_get_shows_confirmation(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'chat/session_confirm_delete.html')
        self.assertContains(response, "Delete 'Trip planning'?")
        self.assertContains(response, 'This cannot be undone.')
        self.assertTrue(ChatSession.objects.filter(pk=self.session.pk).exists())

    def test_post_deletes_session_and_messages_and_redirects_home(self):
        Message.objects.create(session=self.session, role='user', content='hello')
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, '/chat/')
        self.assertFalse(ChatSession.objects.filter(pk=self.session.pk).exists())
        self.assertFalse(Message.objects.exists())
        self.assertContains(response, 'Deleted &#x27;Trip planning&#x27;.')

    def test_deleted_current_session_leaves_sidebar_and_is_gone(self):
        keep = self.make_session('Keep me', age_days=1)
        response = self.client.post(self.url, follow=True)
        self.assertEqual(self.sidebar_names(response), ['Keep me'])
        self.assertEqual(self.client.get(f'/chat/{self.session.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/chat/{keep.pk}/').status_code, 200)

    def test_usage_charges_survive_and_balance_is_unchanged(self):
        from billing.models import UsageCharge
        self.send_paid_message()  # Luna: 1000 x 0.40/1M + 500 x 1.60/1M = 0.0012
        charge = UsageCharge.objects.get()
        balance_before = BillingAccount.objects.get(pk=self.account.pk).credit
        self.assertEqual(balance_before, Decimal('2.00') - Decimal('0.0012'))

        self.client.post(self.url)

        charge.refresh_from_db()
        self.assertIsNone(charge.message)
        self.assertEqual(charge.session_label, f'#{self.session.pk} Trip planning')
        self.assertEqual(charge.cost, Decimal('0.001200'))
        self.assertEqual(BillingAccount.objects.get(pk=self.account.pk).credit, balance_before)

    def test_other_user_gets_404_and_nothing_is_deleted(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assertTrue(ChatSession.objects.filter(pk=self.session.pk).exists())

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        self.assertRedirects(self.client.post(self.url), f'/login/?next={self.url}', fetch_redirect_response=False)
        self.assertTrue(ChatSession.objects.filter(pk=self.session.pk).exists())

    def test_delete_links_in_header_and_sidebar(self):
        response = self.client.get(f'/chat/{self.session.pk}/')
        self.assertContains(response, f'href="{self.url}"', count=2)
