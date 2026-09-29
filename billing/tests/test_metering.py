"""Phase 7: pricing, credit checks and charging (billing.services)."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing import services
from billing.models import BillingAccount, UsageCharge
from chat.models import ChatSession, Message
from llm.models import LLMModel

User = get_user_model()


class CalculateCostTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.luna = LLMModel.objects.get(api_model='gpt-5.6-luna')                 # $0.40 / $1.60
        cls.haiku = LLMModel.objects.get(api_model='claude-haiku-4-5-20251001')   # $1.00 / $5.00
        cls.gemini = LLMModel.objects.get(api_model='gemini-3.8-flash')           # $0.30 / $2.50

    def test_exact_cost_per_model(self):
        cases = [
            (self.luna, 1_000_000, 1_000_000, Decimal('2.000000')),
            (self.haiku, 1_000_000, 1_000_000, Decimal('6.000000')),
            (self.gemini, 1_000_000, 1_000_000, Decimal('2.800000')),
            (self.haiku, 1000, 500, Decimal('0.003500')),   # 0.001 + 0.0025
            (self.gemini, 2000, 400, Decimal('0.001600')),  # 0.0006 + 0.001
            (self.luna, 0, 0, Decimal('0.000000')),
        ]
        for model, tokens_in, tokens_out, expected in cases:
            with self.subTest(model=model.api_model, tokens_in=tokens_in, tokens_out=tokens_out):
                self.assertEqual(services.calculate_cost(model, tokens_in, tokens_out), expected)

    def test_rounds_half_up_to_six_decimal_places(self):
        # Study's recorded Luna reply: 187 in, 9 out -> 0.0000748 + 0.0000144 = 0.0000892
        self.assertEqual(services.calculate_cost(self.luna, 187, 9), Decimal('0.000089'))
        # 5 in at $0.30/M = 0.0000015 -> rounds half-up to 0.000002
        self.assertEqual(services.calculate_cost(self.gemini, 5, 0), Decimal('0.000002'))

    def test_returns_decimal(self):
        self.assertIsInstance(services.calculate_cost(self.luna, 10, 10), Decimal)


class EnsureCanSpendTests(TestCase):
    def test_active_account_with_credit_passes(self):
        services.ensure_can_spend(BillingAccount.objects.create(name='A', credit=Decimal('0.000001')))

    def test_zero_credit_is_insufficient(self):
        account = BillingAccount.objects.create(name='HANS', credit=Decimal('0'))
        with self.assertRaises(services.InsufficientCredit) as ctx:
            services.ensure_can_spend(account)
        self.assertEqual(ctx.exception.user_message,
                         'Insufficient credit in [Personal] HANS. Ask an administrator to top up.')

    def test_negative_credit_is_insufficient(self):
        account = BillingAccount.objects.create(name='A', credit=Decimal('-0.01'))
        with self.assertRaises(services.InsufficientCredit):
            services.ensure_can_spend(account)

    def test_suspended_account_is_refused(self):
        account = BillingAccount.objects.create(name='A', credit=Decimal('5'),
                                                status=BillingAccount.Status.SUSPENDED)
        with self.assertRaises(services.AccountInactive) as ctx:
            services.ensure_can_spend(account)
        self.assertEqual(ctx.exception.user_message, 'This billing account is not active.')

    def test_uses_current_database_state_not_stale_object(self):
        account = BillingAccount.objects.create(name='A', credit=Decimal('2'))
        BillingAccount.objects.filter(pk=account.pk).update(credit=Decimal('0'))
        with self.assertRaises(services.InsufficientCredit):
            services.ensure_can_spend(account)  # the in-memory object still says 2


class RecordChargeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('hans', password='x')
        cls.haiku = LLMModel.objects.get(api_model='claude-haiku-4-5-20251001')

    def setUp(self):
        self.account = BillingAccount.objects.create(name='HANS', credit=Decimal('2.00'))
        self.session = ChatSession.objects.create(user=self.user, billing_account=self.account,
                                                  llm_model=self.haiku, name='Trip planning')

    def reply(self, session=None):
        return Message.objects.create(session=session or self.session, role='assistant', content='ok')

    def test_deducts_cost_and_records_charge(self):
        message = self.reply()
        charge = services.record_charge(self.account, message, self.haiku, 1000, 500)

        self.account.refresh_from_db()
        message.refresh_from_db()
        self.assertEqual(charge.cost, Decimal('0.003500'))
        self.assertEqual(self.account.credit, Decimal('1.996500'))
        self.assertEqual(message.cost, Decimal('0.003500'))
        self.assertEqual(charge.message, message)
        self.assertEqual(charge.billing_account, self.account)
        self.assertEqual((charge.input_tokens, charge.output_tokens), (1000, 500))
        self.assertEqual(charge.session_label, f'#{self.session.pk} Trip planning')

    def test_final_charge_may_overdraw(self):
        BillingAccount.objects.filter(pk=self.account.pk).update(credit=Decimal('0.001'))
        services.record_charge(self.account, self.reply(), self.haiku, 1000, 500)
        self.account.refresh_from_db()
        self.assertEqual(self.account.credit, Decimal('-0.002500'))

    def test_uses_database_balance_not_stale_object(self):
        # Another charge lands after this account object was loaded.
        BillingAccount.objects.filter(pk=self.account.pk).update(credit=Decimal('1.00'))
        services.record_charge(self.account, self.reply(), self.haiku, 1000, 500)  # object still says 2.00
        self.account.refresh_from_db()
        self.assertEqual(self.account.credit, Decimal('0.996500'))

    def test_two_sessions_on_same_account_share_the_balance(self):
        other_session = ChatSession.objects.create(user=self.user, billing_account=self.account,
                                                   llm_model=LLMModel.objects.get(api_model='gpt-5.6-luna'))
        services.record_charge(self.account, self.reply(), self.haiku, 1000, 500)          # 0.0035
        services.record_charge(self.account, self.reply(other_session), other_session.llm_model,
                               1_000_000, 0)                                               # 0.40
        self.account.refresh_from_db()
        self.assertEqual(self.account.credit, Decimal('1.596500'))
        self.assertEqual(UsageCharge.objects.filter(billing_account=self.account).count(), 2)

    def test_failure_rolls_back_deduction(self):
        with mock.patch.object(UsageCharge.objects, 'create', side_effect=RuntimeError('db down')), \
                self.assertRaises(RuntimeError):
            services.record_charge(self.account, self.reply(), self.haiku, 1000, 500)
        self.account.refresh_from_db()
        self.assertEqual(self.account.credit, Decimal('2.00'))
        self.assertFalse(UsageCharge.objects.exists())


class UsageChargeAdminTests(TestCase):
    def test_admin_lists_charges_read_only(self):
        admin = User.objects.create_superuser('admin', password='admin-pass-123')
        self.client.force_login(admin)
        self.assertEqual(self.client.get('/admin/billing/usagecharge/').status_code, 200)
        self.assertEqual(self.client.get('/admin/billing/usagecharge/add/').status_code, 403)
