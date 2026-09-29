"""Chat use cases: turning stored history into provider turns and sending a message."""
from django.db import transaction

from llm import providers
from llm.providers import ProviderError, Turn

from .models import Message

MAX_MESSAGE_LENGTH = 8000


class SendError(Exception):
    """A message could not be sent. `user_message` is safe to show in the UI."""

    def __init__(self, user_message):
        super().__init__(user_message)
        self.user_message = user_message


def build_turns(session):
    """The session's stored messages, oldest first, as provider turns.

    The proxy is stateless, so the full history is sent on every request.
    """
    return [Turn(role=m.role, content=m.content) for m in session.messages.all()]


def send_message(session, text):
    """Send `text` to the session's model and store the exchange.

    The user message and the assistant reply are saved together, and only if the
    provider call succeeds; on failure nothing is saved and SendError is raised.
    Returns the saved assistant Message.
    """
    text = (text or '').strip()
    if not text:
        raise SendError('Please type a message.')
    if len(text) > MAX_MESSAGE_LENGTH:
        raise SendError(f'Messages can be at most {MAX_MESSAGE_LENGTH:,} characters.')

    turns = build_turns(session) + [Turn(role=Message.Role.USER, content=text)]
    try:
        result = providers.complete(session.llm_model, turns)
    except ProviderError as exc:
        raise SendError(exc.user_message) from exc

    # Phase 7 adds the credit check before the call and the charge inside this transaction.
    with transaction.atomic():
        Message.objects.create(session=session, role=Message.Role.USER, content=text)
        reply = Message.objects.create(
            session=session,
            role=Message.Role.ASSISTANT,
            content=result.text,
            status=result.status,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        session.save(update_fields=['updated_at'])  # auto_now: moves the session up the list
    return reply
