"""Metering: pricing token usage and charging it to a billing account (plan decision D4).

Policy: the account must be active with credit > 0 *before* a proxy call; the actual
cost is charged only after a successful reply, so the final reply may overdraw
the account slightly. Failed calls are never charged.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import F

from .models import BillingAccount, UsageCharge

TOKENS_PER_PRICE_UNIT = Decimal(1_000_000)  # prices are per 1M tokens
COST_PRECISION = Decimal('0.000001')        # matches the 6-dp credit/cost fields


class BillingError(Exception):
    """A send was refused for billing reasons. `user_message` is safe to show."""

    def __init__(self, user_message):
        super().__init__(user_message)
        self.user_message = user_message


class AccountInactive(BillingError):
    def __init__(self, account):
        super().__init__('This billing account is not active.')


class InsufficientCredit(BillingError):
    def __init__(self, account):
        super().__init__(f'Insufficient credit in {account}. Ask an administrator to top up.')


def calculate_cost(llm_model, input_tokens, output_tokens):
    """USD cost of one reply: tokens x per-1M-token price, rounded half-up to 6 dp."""
    cost = (
        Decimal(input_tokens) * llm_model.input_price_per_mtok
        + Decimal(output_tokens) * llm_model.output_price_per_mtok
    ) / TOKENS_PER_PRICE_UNIT
    return cost.quantize(COST_PRECISION, rounding=ROUND_HALF_UP)


def ensure_can_spend(account):
    """Raise unless the account (re-read from the database) is active and has credit > 0."""
    current = BillingAccount.objects.get(pk=account.pk)
    if not current.is_active:
        raise AccountInactive(current)
    if current.credit <= 0:
        raise InsufficientCredit(current)


def record_charge(account, message, llm_model, input_tokens, output_tokens):
    """Charge a reply's cost to the account and record it; all-or-nothing.

    Locks the account row, subtracts the cost in the database (so concurrent charges
    cannot overwrite each other), stores the cost on the message and creates the
    UsageCharge. Returns the UsageCharge.
    """
    cost = calculate_cost(llm_model, input_tokens, output_tokens)
    with transaction.atomic():
        BillingAccount.objects.select_for_update().get(pk=account.pk)
        BillingAccount.objects.filter(pk=account.pk).update(credit=F('credit') - cost)
        message.cost = cost
        message.save(update_fields=['cost'])
        return UsageCharge.objects.create(
            billing_account_id=account.pk,
            message=message,
            session_label=f'#{message.session_id} {message.session.name}'[:150],
            llm_model=llm_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )
