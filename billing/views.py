from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.shortcuts import redirect, render

from .services import ensure_personal_account


@login_required
def profile(request):
    accounts = request.user.billing_accounts.all()
    return render(request, 'billing/profile.html', {'accounts': accounts})


def signup(request):
    """Self-service sign-up: a new user with a funded [Personal] account, logged straight in."""
    if request.user.is_authenticated:
        return redirect('chat:home')
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():  # never leave a user without their personal account
            user = form.save()
            ensure_personal_account(user, settings.LITECHAT_SIGNUP_CREDIT)
        login(request, user)
        return redirect('chat:home')
    return render(request, 'registration/signup.html', {'form': form})
