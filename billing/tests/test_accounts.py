"""billing.services.ensure_personal_account, shared by sign-up and seed_demo."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import BillingAccount
from billing.services import ensure_personal_account

User = get_user_model()


class EnsurePersonalAccountTests(TestCase):
    def test_creates_active_personal_account_named_after_user(self):
        user = User.objects.create_user('hans', password='x')
        account, created = ensure_personal_account(user, Decimal('2.00'))

        self.assertTrue(created)
        self.assertEqual(str(account), '[Personal] HANS')
        self.assertEqual(account.status, BillingAccount.Status.ACTIVE)
        self.assertEqual(account.credit, Decimal('2.00'))
        self.assertEqual(list(account.members.all()), [user])

    def test_uses_full_name_when_set(self):
        user = User.objects.create_user('hans', password='x', first_name='Hans Liam', last_name='Yu')
        account, _ = ensure_personal_account(user, Decimal('2.00'))
        self.assertEqual(account.name, 'HANS LIAM YU')

    def test_existing_account_is_reactivated_and_credit_reset(self):
        user = User.objects.create_user('hans', password='x')
        account, _ = ensure_personal_account(user, Decimal('2.00'))
        BillingAccount.objects.filter(pk=account.pk).update(credit=Decimal('0.10'),
                                                            status=BillingAccount.Status.SUSPENDED)

        again, created = ensure_personal_account(user, Decimal('5.00'))

        self.assertFalse(created)
        self.assertEqual(again.pk, account.pk)
        self.assertEqual((again.status, again.credit), (BillingAccount.Status.ACTIVE, Decimal('5.00')))
        self.assertEqual(BillingAccount.objects.count(), 1)

    def test_shared_accounts_are_not_treated_as_personal(self):
        user = User.objects.create_user('hans', password='x')
        shared = BillingAccount.objects.create(name='CLASS', kind=BillingAccount.Kind.SHARED)
        shared.members.add(user)
        account, created = ensure_personal_account(user, Decimal('2.00'))
        self.assertTrue(created)
        self.assertNotEqual(account.pk, shared.pk)
