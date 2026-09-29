from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import BillingAccount

User = get_user_model()


class ProfilePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hans = User.objects.create_user('hans', password='x', first_name='Hans Liam', last_name='Yu')
        cls.other = User.objects.create_user('other', password='x')
        cls.hans_account = BillingAccount.objects.create(name='HANS LIAM YU', credit=Decimal('2.00'))
        cls.hans_account.members.add(cls.hans)
        cls.other_account = BillingAccount.objects.create(name='OTHER PERSON', credit=Decimal('9.99'))
        cls.other_account.members.add(cls.other)

    def test_shows_user_profile_and_own_account_credit(self):
        self.client.force_login(self.hans)
        response = self.client.get('/profile/')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'billing/profile.html')
        self.assertContains(response, 'Hans Liam Yu')
        self.assertContains(response, 'Member since')
        self.assertContains(response, '[Personal] HANS LIAM YU')
        self.assertContains(response, 'Active')
        self.assertContains(response, '$2.00')

    def test_does_not_list_other_users_accounts(self):
        self.client.force_login(self.hans)
        response = self.client.get('/profile/')

        self.assertNotContains(response, 'OTHER PERSON')
        self.assertNotContains(response, '$9.99')
        self.assertEqual(list(response.context['accounts']), [self.hans_account])

    def test_reflects_admin_credit_change(self):
        self.hans_account.credit = Decimal('7.5')
        self.hans_account.save()
        self.client.force_login(self.hans)
        self.assertContains(self.client.get('/profile/'), '$7.50')

    def test_suspended_status_is_shown(self):
        self.hans_account.status = BillingAccount.Status.SUSPENDED
        self.hans_account.save()
        self.client.force_login(self.hans)
        self.assertContains(self.client.get('/profile/'), 'Suspended')

    def test_user_without_accounts_sees_message(self):
        lonely = User.objects.create_user('lonely', password='x')
        self.client.force_login(lonely)
        self.assertContains(self.client.get('/profile/'), "don't belong to any billing account")


class AdminTopUpTests(TestCase):
    def test_admin_can_top_up_credit(self):
        admin = User.objects.create_superuser('admin', password='admin-pass-123')
        account = BillingAccount.objects.create(name='HANS LIAM YU', credit=Decimal('0.50'))
        self.client.force_login(admin)

        response = self.client.post(f'/admin/billing/billingaccount/{account.pk}/change/', {
            'name': account.name,
            'kind': account.kind,
            'status': account.status,
            'credit': '10.00',
            'members': [],
        })

        self.assertEqual(response.status_code, 302)
        account.refresh_from_db()
        self.assertEqual(account.credit, Decimal('10.00'))
