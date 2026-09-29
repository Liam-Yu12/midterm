from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    """A conversation, charged to one billing account and bound to one model at creation."""

    DEFAULT_NAME = 'Untitled session'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')
    billing_account = models.ForeignKey('billing.BillingAccount', on_delete=models.PROTECT, related_name='chat_sessions')
    llm_model = models.ForeignKey('llm.LLMModel', on_delete=models.PROTECT, related_name='chat_sessions')
    name = models.CharField(max_length=100, default=DEFAULT_NAME)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class Message(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    class Status(models.TextChoices):
        COMPLETE = 'complete', 'Complete'
        TRUNCATED = 'truncated', 'Truncated'

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETE)
    # Usage and cost are recorded on assistant messages only.
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.role}: {self.content[:40]}'
