from django.contrib import admin

from .models import BillingAccount


@admin.register(BillingAccount)
class BillingAccountAdmin(admin.ModelAdmin):
    # Credit top-ups are done by editing the `credit` field here.
    list_display = ('name', 'kind', 'status', 'credit', 'created_at')
    list_filter = ('kind', 'status')
    search_fields = ('name', 'members__username')
    filter_horizontal = ('members',)
