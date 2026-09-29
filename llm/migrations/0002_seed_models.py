"""Seed the three models the BUILD LLM Proxy serves (study §5; plan decision D3).

The proxy rejects any other model ID with `400 unknown model`, so these are the
only models offered. Prices are ours (per 1M tokens, USD), not LiteChat's.
"""
from decimal import Decimal

from django.db import migrations

MODELS = [
    {
        'api_model': 'gpt-5.6-luna',
        'provider': 'openai',
        'display_name': 'GPT-5.6 Luna',
        'description': "OpenAI's fast, affordable model for everyday questions and writing.",
        'input_price_per_mtok': Decimal('0.40'),
        'output_price_per_mtok': Decimal('1.60'),
        'sort_order': 10,
    },
    {
        'api_model': 'claude-haiku-4-5-20251001',
        'provider': 'anthropic',
        'display_name': 'Claude Haiku 4.5',
        'description': "Anthropic's quick, compact model for clear, concise answers.",
        'input_price_per_mtok': Decimal('1.00'),
        'output_price_per_mtok': Decimal('5.00'),
        'sort_order': 20,
    },
    {
        'api_model': 'gemini-3.8-flash',
        'provider': 'google',
        'display_name': 'Gemini 3.8 Flash',
        'description': "Google's fast, low-cost model for everyday tasks.",
        'input_price_per_mtok': Decimal('0.30'),
        'output_price_per_mtok': Decimal('2.50'),
        'sort_order': 30,
    },
]


def seed_models(apps, schema_editor):
    LLMModel = apps.get_model('llm', 'LLMModel')
    for fields in MODELS:
        LLMModel.objects.update_or_create(
            api_model=fields['api_model'],
            defaults={**fields, 'tier': 'value', 'is_active': True},
        )


def unseed_models(apps, schema_editor):
    LLMModel = apps.get_model('llm', 'LLMModel')
    LLMModel.objects.filter(api_model__in=[m['api_model'] for m in MODELS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('llm', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_models, unseed_models),
    ]
