"""Phase 4: the seeded catalog holds exactly the three proxy models."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from llm.models import LLMModel

EXPECTED = {
    'gpt-5.6-luna': ('openai', 'GPT-5.6 Luna'),
    'claude-haiku-4-5-20251001': ('anthropic', 'Claude Haiku 4.5'),
    'gemini-3.8-flash': ('google', 'Gemini 3.8 Flash'),
}


class SeededCatalogTests(TestCase):
    def test_exactly_the_three_proxy_models_are_active(self):
        active = LLMModel.objects.filter(is_active=True)
        self.assertEqual(active.count(), 3)
        self.assertEqual(
            {m.api_model: (m.provider, m.display_name) for m in active},
            EXPECTED,
        )

    def test_one_model_per_provider(self):
        self.assertEqual(
            sorted(LLMModel.objects.values_list('provider', flat=True)),
            ['anthropic', 'google', 'openai'],
        )

    def test_prices_are_positive_and_tier_is_value(self):
        for model in LLMModel.objects.all():
            with self.subTest(model=model.api_model):
                self.assertGreater(model.input_price_per_mtok, 0)
                self.assertGreater(model.output_price_per_mtok, 0)
                self.assertEqual(model.tier, LLMModel.Tier.VALUE)
                self.assertTrue(model.description)

    def test_default_ordering_groups_by_provider(self):
        self.assertEqual(
            [m.provider for m in LLMModel.objects.all()],
            ['openai', 'anthropic', 'google'],
        )

    def test_str(self):
        self.assertEqual(str(LLMModel.objects.get(api_model='gpt-5.6-luna')), 'GPT-5.6 Luna (OpenAI)')

    def test_admin_lists_models(self):
        admin = get_user_model().objects.create_superuser('admin', password='admin-pass-123')
        self.client.force_login(admin)
        response = self.client.get('/admin/llm/llmmodel/')
        self.assertEqual(response.status_code, 200)
        for _, name in EXPECTED.values():
            self.assertContains(response, name)
