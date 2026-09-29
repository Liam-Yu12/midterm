from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()


@register.filter
def usd(value):
    """Format a Decimal amount as dollars rounded to cents, e.g. $2.00 or -$0.01."""
    cents = Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    sign = '-' if cents < 0 else ''
    return f'{sign}${abs(cents):,.2f}'
