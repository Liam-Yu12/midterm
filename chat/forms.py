from django import forms

from billing.models import BillingAccount
from llm.models import LLMModel


class NewSessionForm(forms.Form):
    billing_account = forms.ModelChoiceField(
        queryset=BillingAccount.objects.none(),
        empty_label=None,
        help_text='Costs for this session will be charged to the selected account.',
    )
    llm_model = forms.ModelChoiceField(
        queryset=LLMModel.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        empty_label=None,
        error_messages={'required': 'Please choose a model.'},
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the user's own active accounts can be charged.
        self.fields['billing_account'].queryset = user.billing_accounts.filter(
            status=BillingAccount.Status.ACTIVE,
        )
