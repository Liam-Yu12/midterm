from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import NewSessionForm
from .models import ChatSession


@login_required
def home(request):
    return render(request, 'chat/home.html')


@login_required
def new_session(request):
    form = NewSessionForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        session = ChatSession.objects.create(
            user=request.user,
            billing_account=form.cleaned_data['billing_account'],
            llm_model=form.cleaned_data['llm_model'],
        )
        return redirect('chat:session_detail', pk=session.pk)
    return render(request, 'chat/new_session.html', {
        'form': form,
        'models': form.fields['llm_model'].queryset,
        'has_accounts': form.fields['billing_account'].queryset.exists(),
    })


@login_required
def session_detail(request, pk):
    session = get_object_or_404(
        ChatSession.objects.select_related('llm_model', 'billing_account'),
        pk=pk, user=request.user,
    )
    return render(request, 'chat/session_detail.html', {
        'session': session,
        'chat_messages': session.messages.all(),
    })
