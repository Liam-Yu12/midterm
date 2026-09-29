from django.contrib import admin

from .models import BillingAccount, UsageCharge


@admin.register(BillingAccount)
class BillingAccountAdmin(admin.ModelAdmin):
    # Credit top-ups are done by editing the `credit` field here.
    list_display = ('name', 'kind', 'status', 'credit', 'created_at')
    list_filter = ('kind', 'status')
    search_fields = ('name', 'members__username')
    filter_horizontal = ('members',)


@admin.register(UsageCharge)
class UsageChargeAdmin(admin.ModelAdmin):
    """Read-only audit trail of metered replies."""

    list_display = ('created_at', 'billing_account', 'session_label', 'llm_model',
                    'input_tokens', 'output_tokens', 'cost')
    list_filter = ('billing_account', 'llm_model')
    readonly_fields = [f.name for f in UsageCharge._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
