from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import NewSessionForm
from .models import ChatSession


def _get_own_session(request, pk):
    return get_object_or_404(
        ChatSession.objects.select_related('llm_model', 'billing_account'),
        pk=pk, user=request.user,
    )


def _render_session(request, session, *, error=None, draft=''):
    return render(request, 'chat/session_detail.html', {
        'session': session,
        'chat_messages': session.messages.all(),
        'error': error,
        'draft': draft,
        'max_length': services.MAX_MESSAGE_LENGTH,
    })


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
    return _render_session(request, _get_own_session(request, pk))


@login_required
@require_POST
def send_message(request, pk):
    session = _get_own_session(request, pk)
    text = request.POST.get('content', '')
    try:
        services.send_message(session, text)
    except services.SendError as exc:
        return _render_session(request, session, error=exc.user_message, draft=text)
    return redirect('chat:session_detail', pk=session.pk)
