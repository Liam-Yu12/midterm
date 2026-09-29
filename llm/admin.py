from django.contrib import admin

from .models import LLMModel


@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'provider', 'api_model', 'tier',
                    'input_price_per_mtok', 'output_price_per_mtok', 'is_active', 'sort_order')
    list_filter = ('provider', 'tier', 'is_active')
