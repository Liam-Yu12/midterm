"""Phase 5: new conversation with billing account + model selection."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import BillingAccount
from chat.models import ChatSession
from llm.models import LLMModel

User = get_user_model()


def make_account(user, name, status=BillingAccount.Status.ACTIVE, credit='2.00'):
    account = BillingAccount.objects.create(name=name, status=status, credit=Decimal(credit))
    account.members.add(user)
    return account


class NewSessionPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hans = User.objects.create_user('hans', password='x')
        cls.other = User.objects.create_user('other', password='x')
        cls.personal = make_account(cls.hans, 'HANS LIAM YU')
        cls.suspended = make_account(cls.hans, 'OLD CLASS ACCOUNT', status=BillingAccount.Status.SUSPENDED)
        cls.others_account = make_account(cls.other, 'OTHER PERSON')
        cls.luna = LLMModel.objects.get(api_model='gpt-5.6-luna')

    def setUp(self):
        self.client.force_login(self.hans)

    def test_lists_only_users_active_accounts(self):
        response = self.client.get('/chat/new/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'chat/new_session.html')
        self.assertEqual(list(response.context['form'].fields['billing_account'].queryset), [self.personal])
        self.assertContains(response, '[Personal] HANS LIAM YU')
        self.assertNotContains(response, 'OLD CLASS ACCOUNT')
        self.assertNotContains(response, 'OTHER PERSON')
        self.assertContains(response, 'Costs for this session will be charged to the selected account.')

    def test_lists_three_models_grouped_by_provider_with_tier_and_price(self):
        response = self.client.get('/chat/new/')
        self.assertEqual(response.context['models'].count(), 3)
        for provider in ('OpenAI', 'Anthropic', 'Google'):
            self.assertContains(response, f'<legend class="provider-name">{provider}</legend>', html=False)
        for name in ('GPT-5.6 Luna', 'Claude Haiku 4.5', 'Gemini 3.8 Flash'):
            self.assertContains(response, name)
        self.assertContains(response, 'Value tier', count=3)
        self.assertContains(response, '$0.40 in · $1.60 out per 1M tokens')

    def test_inactive_models_are_not_offered(self):
        LLMModel.objects.filter(api_model='gemini-3.8-flash').update(is_active=False)
        response = self.client.get('/chat/new/')
        self.assertNotContains(response, 'Gemini 3.8 Flash')

    def test_valid_post_creates_untitled_session_and_redirects(self):
        response = self.client.post('/chat/new/', {'billing_account': self.personal.pk, 'llm_model': self.luna.pk})

        session = ChatSession.objects.get()
        self.assertRedirects(response, f'/chat/{session.pk}/')
        self.assertEqual(session.user, self.hans)
        self.assertEqual(session.billing_account, self.personal)
        self.assertEqual(session.llm_model, self.luna)
        self.assertEqual(session.name, 'Untitled session')

    def test_rejects_another_users_account(self):
        response = self.client.post('/chat/new/', {'billing_account': self.others_account.pk, 'llm_model': self.luna.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors['billing_account'])
        self.assertFalse(ChatSession.objects.exists())

    def test_rejects_suspended_account(self):
        response = self.client.post('/chat/new/', {'billing_account': self.suspended.pk, 'llm_model': self.luna.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors['billing_account'])
        self.assertFalse(ChatSession.objects.exists())

    def test_requires_a_model(self):
        response = self.client.post('/chat/new/', {'billing_account': self.personal.pk})
        self.assertContains(response, 'Please choose a model.')
        self.assertFalse(ChatSession.objects.exists())

    def test_rejects_inactive_model(self):
        self.luna.is_active = False
        self.luna.save()
        response = self.client.post('/chat/new/', {'billing_account': self.personal.pk, 'llm_model': self.luna.pk})
        self.assertTrue(response.context['form'].errors['llm_model'])
        self.assertFalse(ChatSession.objects.exists())

    def test_user_without_active_account_sees_message(self):
        self.client.force_login(User.objects.create_user('lonely', password='x'))
        response = self.client.get('/chat/new/')
        self.assertContains(response, "You don't have an active billing account")
        self.assertNotContains(response, 'Start conversation')

    def test_user_without_active_account_cannot_post(self):
        lonely = User.objects.create_user('lonely', password='x')
        self.client.force_login(lonely)
        self.client.post('/chat/new/', {'billing_account': self.personal.pk, 'llm_model': self.luna.pk})
        self.assertFalse(ChatSession.objects.exists())


class ChatHomeTests(TestCase):
    def test_empty_state_links_to_new_conversation(self):
        self.client.force_login(User.objects.create_user('hans', password='x'))
        response = self.client.get('/chat/')
        self.assertContains(response, 'Start a New Conversation')
        self.assertContains(response, 'href="/chat/new/"')


class SessionDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hans = User.objects.create_user('hans', password='x')
        cls.other = User.objects.create_user('other', password='x')
        cls.account = make_account(cls.hans, 'HANS LIAM YU')
        cls.session = ChatSession.objects.create(
            user=cls.hans, billing_account=cls.account,
            llm_model=LLMModel.objects.get(api_model='claude-haiku-4-5-20251001'),
        )

    def test_owner_sees_empty_session_with_model_and_account(self):
        self.client.force_login(self.hans)
        response = self.client.get(f'/chat/{self.session.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Untitled session')
        self.assertContains(response, 'Model: Claude Haiku 4.5')
        self.assertContains(response, 'Billing account: [Personal] HANS LIAM YU')
        self.assertContains(response, 'No messages yet.')

    def test_other_user_gets_404(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/chat/{self.session.pk}/').status_code, 404)

    def test_anonymous_is_redirected_to_login(self):
        url = f'/chat/{self.session.pk}/'
        self.assertRedirects(self.client.get(url), f'/login/?next={url}', fetch_redirect_response=False)
