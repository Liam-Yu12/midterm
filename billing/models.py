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


class UsageCharge(models.Model):
    """Audit record of one metered reply. Survives deletion of the chat session."""

    billing_account = models.ForeignKey(BillingAccount, on_delete=models.PROTECT, related_name='charges')
    message = models.OneToOneField('chat.Message', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='charge')
    session_label = models.CharField(max_length=150, help_text='Snapshot of the session ID and name.')
    llm_model = models.ForeignKey('llm.LLMModel', on_delete=models.PROTECT, related_name='charges')
    input_tokens = models.PositiveIntegerField()
    output_tokens = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=12, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.cost} from {self.billing_account} ({self.session_label})'
