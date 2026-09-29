from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from billing.models import BillingAccount

User = get_user_model()


def seed(**kwargs):
    call_command('seed_demo', stdout=StringIO(), **kwargs)


class SeedDemoTests(TestCase):
    def test_creates_user_and_personal_account_with_two_dollars(self):
        seed(username='demo', password='demo-pass-123')

        user = User.objects.get(username='demo')
        self.assertTrue(user.check_password('demo-pass-123'))
        account = user.billing_accounts.get()
        self.assertEqual(account.kind, BillingAccount.Kind.PERSONAL)
        self.assertEqual(account.status, BillingAccount.Status.ACTIVE)
        self.assertEqual(account.credit, Decimal('2.00'))
        self.assertEqual(str(account), '[Personal] DEMO')

    def test_running_twice_does_not_duplicate(self):
        seed(username='demo', password='first-pass-123')
        seed(username='demo', password='second-pass-456')

        self.assertEqual(User.objects.filter(username='demo').count(), 1)
        self.assertEqual(BillingAccount.objects.count(), 1)
        self.assertTrue(User.objects.get(username='demo').check_password('second-pass-456'))

    def test_rerun_resets_credit_and_reactivates(self):
        seed(username='demo', password='demo-pass-123')
        account = BillingAccount.objects.get()
        account.credit = Decimal('0.10')
        account.status = BillingAccount.Status.SUSPENDED
        account.save()

        seed(username='demo', password='demo-pass-123', credit='5')

        account.refresh_from_db()
        self.assertEqual(account.credit, Decimal('5'))
        self.assertEqual(account.status, BillingAccount.Status.ACTIVE)

    def test_prompts_for_password_when_not_given(self):
        with mock.patch('billing.management.commands.seed_demo.getpass.getpass', return_value='prompted-pass-1'):
            seed(username='demo')
        self.assertTrue(User.objects.get(username='demo').check_password('prompted-pass-1'))

    def test_rejects_invalid_credit(self):
        with self.assertRaises(CommandError):
            seed(username='demo', password='demo-pass-123', credit='abc')
        with self.assertRaises(CommandError):
            seed(username='demo', password='demo-pass-123', credit='-1')
        self.assertFalse(User.objects.filter(username='demo').exists())
