"""Self-service sign-up (plan/user-signup.md §2)."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from billing.models import BillingAccount
from chat.models import ChatSession
from llm.models import LLMModel

User = get_user_model()
GOOD = {'username': 'teacher', 'password1': 'Litechat-Grader-2026', 'password2': 'Litechat-Grader-2026'}


class SignupTests(TestCase):
    def signup(self, **overrides):
        return self.client.post('/signup/', {**GOOD, **overrides})

    def test_page_renders_and_login_links_to_it(self):
        response = self.client.get('/signup/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/signup.html')
        for field in ('name="username"', 'name="password1"', 'name="password2"', 'CREATE ACCOUNT'):
            self.assertContains(response, field)
        self.assertContains(self.client.get('/login/'), 'href="/signup/"')

    def test_valid_signup_creates_user_and_funded_account_and_logs_in(self):
        response = self.signup()

        self.assertRedirects(response, '/chat/')
        user = User.objects.get(username='teacher')
        self.assertTrue(user.check_password(GOOD['password1']))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        account = user.billing_accounts.get()
        self.assertEqual(str(account), '[Personal] TEACHER')
        self.assertEqual(account.status, BillingAccount.Status.ACTIVE)
        self.assertEqual(account.credit, Decimal('2.00'))
        self.assertContains(self.client.get('/profile/'), '$2.00')

    def test_new_user_can_start_a_conversation(self):
        self.signup()
        response = self.client.get('/chat/new/')
        self.assertContains(response, '[Personal] TEACHER')
        luna = LLMModel.objects.get(api_model='gpt-5.6-luna')
        account = BillingAccount.objects.get(members__username='teacher')
        self.client.post('/chat/new/', {'billing_account': account.pk, 'llm_model': luna.pk})
        self.assertTrue(ChatSession.objects.filter(user__username='teacher').exists())

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user('teacher', password='x')
        response = self.signup()
        self.assertContains(response, 'A user with that username already exists.')
        self.assertEqual(User.objects.filter(username='teacher').count(), 1)
        self.assertFalse(BillingAccount.objects.exists())

    def test_password_mismatch_is_rejected(self):
        response = self.signup(password2='Something-Else-2026')
        self.assertContains(response, 'The two password fields didn’t match.')
        self.assertFalse(User.objects.exists())

    def test_weak_passwords_are_rejected(self):
        cases = {
            'short': ('Ab1-x', 'This password is too short.'),
            'common': ('password123', 'This password is too common.'),
            'numeric': ('839201746153', 'This password is entirely numeric.'),
        }
        for label, (password, message) in cases.items():
            with self.subTest(label):
                response = self.signup(password1=password, password2=password)
                self.assertContains(response, message)
        self.assertFalse(User.objects.exists())
        self.assertFalse(BillingAccount.objects.exists())

    def test_username_with_space_is_rejected(self):
        response = self.signup(username='liam yu')
        self.assertContains(response, 'Enter a valid username.')
        self.assertContains(response, 'no spaces')
        self.assertFalse(User.objects.exists())

    def test_logged_in_user_is_sent_to_chat(self):
        self.client.force_login(User.objects.create_user('hans', password='x'))
        self.assertRedirects(self.client.get('/signup/'), '/chat/')
        self.assertRedirects(self.client.post('/signup/', GOOD), '/chat/')
        self.assertFalse(User.objects.filter(username='teacher').exists())

    @override_settings(LITECHAT_SIGNUP_CREDIT=Decimal('0'))
    def test_zero_signup_credit_blocks_chatting_until_top_up(self):
        self.signup()
        account = BillingAccount.objects.get(members__username='teacher')
        self.assertEqual(account.credit, Decimal('0'))
        session = ChatSession.objects.create(user=account.members.get(), billing_account=account,
                                             llm_model=LLMModel.objects.get(api_model='gpt-5.6-luna'))
        with mock.patch('llm.providers.complete') as complete:
            response = self.client.post(f'/chat/{session.pk}/send/', {'content': 'hi'})
        self.assertContains(response, 'Insufficient credit in [Personal] TEACHER')
        complete.assert_not_called()

    def test_account_creation_failure_leaves_no_user(self):
        with mock.patch('billing.views.ensure_personal_account', side_effect=RuntimeError('db down')), \
                self.assertRaises(RuntimeError):
            self.signup()
        self.assertFalse(User.objects.filter(username='teacher').exists())
        self.assertNotIn('_auth_user_id', self.client.session)
