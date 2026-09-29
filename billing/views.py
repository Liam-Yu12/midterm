from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def profile(request):
    accounts = request.user.billing_accounts.all()
    return render(request, 'billing/profile.html', {'accounts': accounts})
