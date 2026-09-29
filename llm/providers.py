"""Provider adapters for the BUILD LLM Proxy (https://proxy.litechat.ai).

The proxy exposes three provider-native interfaces, each with its own key, request
shape and response shape (study §5.2). This module hides those differences behind
one call:

    complete(llm_model, turns, system_prompt=None) -> CompletionResult

Keys are read from the environment at call time and are never logged or included
in errors; `sensitive_variables` hides them from Django's debug/error reports if an
unexpected exception escapes. Requests are not retried (proxy docs: "do not
automatically retry").
"""
import logging
import os
from dataclasses import dataclass

import requests
from django.conf import settings
from django.views.decorators.debug import sensitive_variables

logger = logging.getLogger(__name__)

KEY_ENV_VARS = {
    'openai': 'BUILD_OPENAI_KEY',
    'anthropic': 'BUILD_ANTHROPIC_KEY',
    'google': 'BUILD_GOOGLE_KEY',
}


@dataclass(frozen=True)
class Turn:
    role: str  # "user" or "assistant"
    content: str


@dataclass(frozen=True)
class CompletionResult:
    text: str
    status: str  # "complete" or "truncated"
    input_tokens: int
    output_tokens: int


class ProviderError(Exception):
    """A failed proxy call. `kind` is one of KINDS; messages never contain secrets."""

    KINDS = ('auth', 'rate_limited', 'bad_request', 'upstream', 'timeout', 'bad_response')

    DEFAULT_MESSAGES = {
        'auth': 'The AI service rejected our credentials. Please contact the administrator.',
        'rate_limited': 'The AI service is busy. Please try again in a moment.',
        'bad_request': 'The request could not be processed.',
        'upstream': 'The AI service is unavailable right now.',
        'timeout': 'The AI service took too long to respond. Please try again.',
        'bad_response': 'The AI service is unavailable right now.',
    }

    def __init__(self, kind, user_message=None, status_code=None):
        assert kind in self.KINDS, kind
        self.kind = kind
        self.user_message = user_message or self.DEFAULT_MESSAGES[kind]
        self.status_code = status_code
        super().__init__(f'{kind} (HTTP {status_code})' if status_code else kind)


# --- Request builders: (api_model, turns, system_prompt, max_tokens, key) -> (url, headers, body)

@sensitive_variables('key')
def _build_openai(api_model, turns, system_prompt, max_tokens, key):
    messages = [{'role': 'system', 'content': system_prompt}] if system_prompt else []
    messages += [{'role': t.role, 'content': t.content} for t in turns]
    return (
        f'{settings.LITECHAT_PROXY_BASE_URL}/openai/v1/chat/completions',
        {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        {'model': api_model, 'messages': messages, 'max_tokens': max_tokens, 'reasoning_effort': 'none'},
    )


@sensitive_variables('key')
def _build_anthropic(api_model, turns, system_prompt, max_tokens, key):
    body = {
        'model': api_model,
        'messages': [{'role': t.role, 'content': t.content} for t in turns],
        'max_tokens': max_tokens,
        'thinking': {'type': 'disabled'},
    }
    if system_prompt:
        body['system'] = system_prompt
    return (
        f'{settings.LITECHAT_PROXY_BASE_URL}/anthropic/v1/messages',
        {'x-api-key': key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'},
        body,
    )


@sensitive_variables('key')
def _build_google(api_model, turns, system_prompt, max_tokens, key):
    body = {
        'contents': [
            {'role': 'model' if t.role == 'assistant' else 'user', 'parts': [{'text': t.content}]}
            for t in turns
        ],
        'generationConfig': {'maxOutputTokens': max_tokens, 'thinkingConfig': {'thinkingBudget': 0}},
    }
    if system_prompt:
        body['systemInstruction'] = {'parts': [{'text': system_prompt}]}
    return (
        f'{settings.LITECHAT_PROXY_BASE_URL}/google/v1beta/models/{api_model}:generateContent',
        {'x-goog-api-key': key, 'Content-Type': 'application/json'},
        body,
    )


# --- Response parsers: dict -> CompletionResult (KeyError/TypeError/IndexError mean a bad response)

def _parse_openai(data):
    choice = data['choices'][0]
    usage = data['usage']
    return CompletionResult(
        text=choice['message'].get('content') or '',
        status='truncated' if choice.get('finish_reason') == 'length' else 'complete',
        input_tokens=int(usage['prompt_tokens']),
        output_tokens=int(usage['completion_tokens']),
    )


def _parse_anthropic(data):
    usage = data['usage']
    return CompletionResult(
        text=''.join(block['text'] for block in data['content'] if block.get('type') == 'text'),
        status='truncated' if data.get('stop_reason') == 'max_tokens' else 'complete',
        input_tokens=int(usage['input_tokens']),
        output_tokens=int(usage['output_tokens']),
    )


def _parse_google(data):
    candidate = data['candidates'][0]
    usage = data['usageMetadata']
    return CompletionResult(
        text=''.join(part.get('text', '') for part in candidate['content'].get('parts', [])),
        status='truncated' if candidate.get('finishReason') == 'MAX_TOKENS' else 'complete',
        input_tokens=int(usage['promptTokenCount']),
        output_tokens=int(usage.get('candidatesTokenCount', 0)),
    )


_ADAPTERS = {
    'openai': (_build_openai, _parse_openai),
    'anthropic': (_build_anthropic, _parse_anthropic),
    'google': (_build_google, _parse_google),
}


def _error_kind_for_status(status_code):
    if status_code in (401, 403):
        return 'auth'
    if status_code == 429:
        return 'rate_limited'
    if 400 <= status_code < 500:
        return 'bad_request'
    return 'upstream'


# No arguments: mask *all* locals, here and in every frame below (requests/urllib3
# internals hold the headers under other names, e.g. `kwargs`).
@sensitive_variables()
def complete(llm_model, turns, system_prompt=None):
    """Send the conversation to the model's provider interface and return the reply.

    Raises ProviderError on any failure. Never retries.
    """
    provider = llm_model.provider
    if provider not in _ADAPTERS:
        logger.error('Unsupported provider=%s for model=%s', provider, llm_model.api_model)
        raise ProviderError('bad_request')
    build, parse = _ADAPTERS[provider]

    key = os.environ.get(KEY_ENV_VARS[provider], '')
    if not key:
        logger.error('Proxy key missing for provider=%s (env var %s)', provider, KEY_ENV_VARS[provider])
        raise ProviderError('auth')

    url, headers, body = build(
        llm_model.api_model, list(turns), system_prompt, settings.LITECHAT_MAX_OUTPUT_TOKENS, key,
    )

    try:
        response = requests.post(url, headers=headers, json=body, timeout=settings.LITECHAT_PROXY_TIMEOUT)
    except requests.Timeout:
        logger.warning('Proxy timeout provider=%s', provider)
        raise ProviderError('timeout') from None
    except requests.RequestException as exc:
        logger.warning('Proxy connection error provider=%s type=%s', provider, type(exc).__name__)
        raise ProviderError('upstream') from None

    if response.status_code != 200:
        kind = _error_kind_for_status(response.status_code)
        logger.warning('Proxy error provider=%s kind=%s status=%s', provider, kind, response.status_code)
        raise ProviderError(kind, status_code=response.status_code)

    try:
        return parse(response.json())
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        logger.warning('Proxy returned an unexpected response shape provider=%s', provider)
        raise ProviderError('bad_response', status_code=response.status_code) from None
