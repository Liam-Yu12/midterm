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
