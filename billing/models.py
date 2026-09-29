from decimal import Decimal

from django.conf import settings
from django.db import models


class BillingAccount(models.Model):
    """An account that holds dollar credit and is charged for LLM usage."""

    class Kind(models.TextChoices):
        PERSONAL = 'personal', 'Personal'
        SHARED = 'shared', 'Shared'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'

    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PERSONAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    # Six decimal places: a single message costs fractions of a cent.
    # May go slightly negative after the final message (see plan decision D4).
    credit = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('0'))
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='billing_accounts', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['kind', 'name']

    def __str__(self):
        return f'[{self.get_kind_display()}] {self.name}'

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE
