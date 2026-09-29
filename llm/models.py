from django.db import models


class LLMModel(models.Model):
    """A model users can chat with, served through one of the proxy's provider interfaces.

    Prices are our own (per 1M tokens, USD); the proxy reports tokens but no prices.
    """

    class Provider(models.TextChoices):
        OPENAI = 'openai', 'OpenAI'
        ANTHROPIC = 'anthropic', 'Anthropic'
        GOOGLE = 'google', 'Google'

    class Tier(models.TextChoices):
        VALUE = 'value', 'Value'
        STANDARD = 'standard', 'Standard'
        PREMIUM = 'premium', 'Premium'

    provider = models.CharField(max_length=20, choices=Provider.choices)
    api_model = models.CharField(max_length=100, unique=True, help_text='Model ID sent to the proxy.')
    display_name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.VALUE)
    input_price_per_mtok = models.DecimalField(max_digits=10, decimal_places=4)
    output_price_per_mtok = models.DecimalField(max_digits=10, decimal_places=4)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'display_name']
        verbose_name = 'LLM model'

    def __str__(self):
        return f'{self.display_name} ({self.get_provider_display()})'
