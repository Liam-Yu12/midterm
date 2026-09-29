from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from billing.models import BillingAccount
from billing.templatetags.money import usd


class BillingAccountModelTests(TestCase):
    def test_defaults(self):
        account = BillingAccount.objects.create(name='HANS LIAM YU')
        self.assertEqual(account.kind, BillingAccount.Kind.PERSONAL)
        self.assertEqual(account.status, BillingAccount.Status.ACTIVE)
        self.assertEqual(account.credit, Decimal('0'))
        self.assertTrue(account.is_active)

    def test_str_matches_litechat_format(self):
        account = BillingAccount(name='HANS LIAM YU', kind=BillingAccount.Kind.PERSONAL)
        self.assertEqual(str(account), '[Personal] HANS LIAM YU')

    def test_credit_keeps_sub_cent_precision(self):
        account = BillingAccount.objects.create(name='A', credit=Decimal('1.999877'))
        account.refresh_from_db()
        self.assertEqual(account.credit, Decimal('1.999877'))

    def test_suspended_account_is_not_active(self):
        self.assertFalse(BillingAccount(status=BillingAccount.Status.SUSPENDED).is_active)


class UsdFilterTests(SimpleTestCase):
    def test_formats_dollars_to_cents(self):
        self.assertEqual(usd(Decimal('2')), '$2.00')
        self.assertEqual(usd(Decimal('1.999877')), '$2.00')
        self.assertEqual(usd(Decimal('1.234')), '$1.23')
        self.assertEqual(usd(Decimal('1234.5')), '$1,234.50')

    def test_formats_negative_balance(self):
        self.assertEqual(usd(Decimal('-0.0061')), '-$0.01')
