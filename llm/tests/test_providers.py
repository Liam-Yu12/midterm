"""Phase 4b: provider adapters, tested offline against recorded proxy responses.

`requests.post` is mocked everywhere and keys are dummies, so no network call is
made and no real key is needed.
"""
import copy
import json
import os
from pathlib import Path
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from llm.models import LLMModel
from llm.providers import CompletionResult, ProviderError, Turn, complete

FIXTURES = Path(__file__).parent / 'fixtures'
BASE = 'https://proxy.test'
DUMMY_KEYS = {
    'BUILD_OPENAI_KEY': 'dummy-openai-key',
    'BUILD_ANTHROPIC_KEY': 'dummy-anthropic-key',
    'BUILD_GOOGLE_KEY': 'dummy-google-key',
}

LUNA = LLMModel(provider='openai', api_model='gpt-5.6-luna', display_name='GPT-5.6 Luna')
HAIKU = LLMModel(provider='anthropic', api_model='claude-haiku-4-5-20251001', display_name='Claude Haiku 4.5')
GEMINI = LLMModel(provider='google', api_model='gemini-3.8-flash', display_name='Gemini 3.8 Flash')

HISTORY = [
    Turn('user', 'My name is Hans.'),
    Turn('assistant', 'Nice to meet you, Hans!'),
    Turn('user', 'What is my name?'),
]


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


def fake_response(status=200, payload=None, invalid_json=False):
    response = mock.Mock(status_code=status)
    if invalid_json:
        response.json.side_effect = ValueError('not json')
    else:
        response.json.return_value = payload
    return response


class DummyKeysMixin:
    """Replace any real proxy keys (settings loads .env) with dummies for every test.

    Patched in setUp, not as a class decorator: a class-level mock.patch.dict only
    wraps test methods defined on that class, not those inherited by subclasses.
    """

    def setUp(self):
        super().setUp()
        env = {k: v for k, v in os.environ.items() if k not in DUMMY_KEYS}
        patcher = mock.patch.dict(os.environ, {**env, **DUMMY_KEYS}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_header(self, headers, name, expected):
        # Compare without echoing the actual value, so a failure can never print a real key.
        self.assertTrue(headers.get(name) == expected, f'{name} header does not hold the expected dummy key')


@override_settings(LITECHAT_PROXY_BASE_URL=BASE, LITECHAT_PROXY_TIMEOUT=120, LITECHAT_MAX_OUTPUT_TOKENS=1024)
class AdapterTestCase(DummyKeysMixin, SimpleTestCase):
    def call(self, model, payload=None, turns=HISTORY, system_prompt=None, **response_kwargs):
        """Run complete() against a fake proxy response; return (result, post_mock)."""
        with mock.patch('llm.providers.requests.post',
                        return_value=fake_response(payload=payload, **response_kwargs)) as post:
            return complete(model, turns, system_prompt=system_prompt), post

    def sent(self, post):
        (url,), kwargs = post.call_args
        return url, kwargs['headers'], kwargs['json'], kwargs['timeout']


class OpenAIAdapterTests(AdapterTestCase):
    def test_request_shape(self):
        _, post = self.call(LUNA, fixture('openai_ok.json'), system_prompt='Be terse.')
        url, headers, body, timeout = self.sent(post)

        self.assertEqual(url, f'{BASE}/openai/v1/chat/completions')
        self.assert_header(headers, 'Authorization', 'Bearer dummy-openai-key')
        self.assertEqual(timeout, 120)
        self.assertEqual(body['model'], 'gpt-5.6-luna')
        self.assertEqual(body['max_tokens'], 1024)
        self.assertEqual(body['reasoning_effort'], 'none')
        self.assertEqual(body['messages'], [
            {'role': 'system', 'content': 'Be terse.'},
            {'role': 'user', 'content': 'My name is Hans.'},
            {'role': 'assistant', 'content': 'Nice to meet you, Hans!'},
            {'role': 'user', 'content': 'What is my name?'},
        ])

    def test_no_system_message_without_system_prompt(self):
        _, post = self.call(LUNA, fixture('openai_ok.json'))
        self.assertEqual(self.sent(post)[2]['messages'][0]['role'], 'user')

    def test_parses_text_and_tokens(self):
        result, _ = self.call(LUNA, fixture('openai_ok.json'))
        self.assertEqual(result, CompletionResult(text='ok', status='complete', input_tokens=187, output_tokens=1))

    def test_detects_truncation(self):
        result, _ = self.call(LUNA, fixture('openai_length.json'))
        self.assertEqual(result.status, 'truncated')
        self.assertEqual(result.output_tokens, 1024)


class AnthropicAdapterTests(AdapterTestCase):
    def test_request_shape(self):
        _, post = self.call(HAIKU, fixture('anthropic_ok.json'), system_prompt='Be terse.')
        url, headers, body, _ = self.sent(post)

        self.assertEqual(url, f'{BASE}/anthropic/v1/messages')
        self.assert_header(headers, 'x-api-key', 'dummy-anthropic-key')
        self.assertEqual(headers['anthropic-version'], '2023-06-01')
        self.assertNotIn('Authorization', headers)
        self.assertEqual(body['model'], 'claude-haiku-4-5-20251001')
        self.assertEqual(body['max_tokens'], 1024)
        self.assertEqual(body['thinking'], {'type': 'disabled'})
        self.assertEqual(body['system'], 'Be terse.')
        self.assertEqual([m['role'] for m in body['messages']], ['user', 'assistant', 'user'])
        self.assertEqual(body['messages'][2]['content'], 'What is my name?')

    def test_no_system_field_without_system_prompt(self):
        _, post = self.call(HAIKU, fixture('anthropic_ok.json'))
        self.assertNotIn('system', self.sent(post)[2])

    def test_parses_text_and_tokens(self):
        result, _ = self.call(HAIKU, fixture('anthropic_ok.json'))
        self.assertEqual(result, CompletionResult(text='ok', status='complete', input_tokens=186, output_tokens=1))

    def test_joins_text_blocks_and_skips_other_blocks(self):
        payload = fixture('anthropic_ok.json')
        payload['content'] = [
            {'type': 'thinking', 'thinking': 'hmm'},
            {'type': 'text', 'text': 'Hello, '},
            {'type': 'text', 'text': 'Hans.'},
        ]
        result, _ = self.call(HAIKU, payload)
        self.assertEqual(result.text, 'Hello, Hans.')

    def test_detects_truncation(self):
        payload = fixture('anthropic_ok.json')
        payload['stop_reason'] = 'max_tokens'
        result, _ = self.call(HAIKU, payload)
        self.assertEqual(result.status, 'truncated')


class GoogleAdapterTests(AdapterTestCase):
    def test_request_shape(self):
        _, post = self.call(GEMINI, fixture('google_ok.json'), system_prompt='Be terse.')
        url, headers, body, _ = self.sent(post)

        self.assertEqual(url, f'{BASE}/google/v1beta/models/gemini-3.8-flash:generateContent')
        self.assert_header(headers, 'x-goog-api-key', 'dummy-google-key')
        self.assertNotIn('Authorization', headers)
        self.assertEqual(body['generationConfig'], {'maxOutputTokens': 1024, 'thinkingConfig': {'thinkingBudget': 0}})
        self.assertEqual(body['systemInstruction'], {'parts': [{'text': 'Be terse.'}]})
        self.assertEqual(body['contents'][2], {'role': 'user', 'parts': [{'text': 'What is my name?'}]})

    def test_maps_assistant_role_to_model(self):
        _, post = self.call(GEMINI, fixture('google_ok.json'))
        self.assertEqual([c['role'] for c in self.sent(post)[2]['contents']], ['user', 'model', 'user'])

    def test_no_system_instruction_without_system_prompt(self):
        _, post = self.call(GEMINI, fixture('google_ok.json'))
        self.assertNotIn('systemInstruction', self.sent(post)[2])

    def test_parses_text_and_tokens(self):
        result, _ = self.call(GEMINI, fixture('google_ok.json'))
        self.assertEqual(result, CompletionResult(text='ok', status='complete', input_tokens=187, output_tokens=1))

    def test_detects_truncation(self):
        payload = fixture('google_ok.json')
        payload['candidates'][0]['finishReason'] = 'MAX_TOKENS'
        result, _ = self.call(GEMINI, payload)
        self.assertEqual(result.status, 'truncated')


class ErrorHandlingTests(AdapterTestCase):
    def assert_error(self, kind, *, model=LUNA, **call_kwargs):
        with self.assertRaises(ProviderError) as ctx:
            self.call(model, **call_kwargs)
        self.assertEqual(ctx.exception.kind, kind)
        self.assertTrue(ctx.exception.user_message)
        for key in DUMMY_KEYS.values():
            self.assertNotIn(key, str(ctx.exception))
            self.assertNotIn(key, ctx.exception.user_message)
        return ctx.exception

    def test_401_is_auth(self):
        error = self.assert_error('auth', status=401, payload=fixture('openai_error_401.json'))
        self.assertEqual(error.status_code, 401)

    def test_403_is_auth(self):
        self.assert_error('auth', status=403, payload={})

    def test_429_is_rate_limited(self):
        self.assert_error('rate_limited', status=429, payload={})

    def test_400_is_bad_request(self):
        self.assert_error('bad_request', status=400, payload=fixture('openai_error_400.json'))

    def test_5xx_is_upstream(self):
        for status in (500, 502, 503, 504):
            with self.subTest(status=status):
                self.assert_error('upstream', status=status, payload={})

    def test_malformed_json_is_bad_response(self):
        self.assert_error('bad_response', invalid_json=True)

    def test_missing_fields_are_bad_response(self):
        for model, name in ((LUNA, 'openai_ok.json'), (HAIKU, 'anthropic_ok.json'), (GEMINI, 'google_ok.json')):
            with self.subTest(provider=model.provider):
                payload = fixture(name)
                payload.pop('usage', None)
                payload.pop('usageMetadata', None)
                self.assert_error('bad_response', model=model, payload=payload)

    def test_timeout(self):
        with mock.patch('llm.providers.requests.post', side_effect=requests.Timeout()), \
                self.assertRaises(ProviderError) as ctx:
            complete(LUNA, HISTORY)
        self.assertEqual(ctx.exception.kind, 'timeout')

    def test_connection_error_is_upstream(self):
        with mock.patch('llm.providers.requests.post', side_effect=requests.ConnectionError()), \
                self.assertRaises(ProviderError) as ctx:
            complete(LUNA, HISTORY)
        self.assertEqual(ctx.exception.kind, 'upstream')

    def test_missing_key_is_auth_and_makes_no_request(self):
        env = {k: v for k, v in DUMMY_KEYS.items() if k != 'BUILD_ANTHROPIC_KEY'}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch('llm.providers.requests.post') as post, \
                self.assertRaises(ProviderError) as ctx:
            complete(HAIKU, HISTORY)
        self.assertEqual(ctx.exception.kind, 'auth')
        post.assert_not_called()

    def test_errors_are_not_retried(self):
        with mock.patch('llm.providers.requests.post', return_value=fake_response(status=502, payload={})) as post, \
                self.assertRaises(ProviderError):
            complete(LUNA, HISTORY)
        self.assertEqual(post.call_count, 1)

    def test_logs_do_not_contain_keys(self):
        with self.assertLogs('llm.providers', level='WARNING') as logs:
            self.assert_error('auth', status=401, payload={})
        for key in DUMMY_KEYS.values():
            self.assertNotIn(key, '\n'.join(logs.output))

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ProviderError) as ctx:
            complete(LLMModel(provider='mistral', api_model='x'), HISTORY)
        self.assertEqual(ctx.exception.kind, 'bad_request')


class FixtureHygieneTests(DummyKeysMixin, SimpleTestCase):
    def test_fixtures_are_valid_json_without_credentials(self):
        for path in FIXTURES.glob('*.json'):
            with self.subTest(fixture=path.name):
                text = path.read_text()
                json.loads(text)
                for marker in ('Bearer', 'x-api-key', 'x-goog-api-key'):
                    self.assertNotIn(marker, text)

    def test_parsers_do_not_mutate_fixture(self):
        payload = fixture('openai_ok.json')
        original = copy.deepcopy(payload)
        with mock.patch('llm.providers.requests.post', return_value=fake_response(payload=payload)):
            complete(LUNA, HISTORY)
        self.assertEqual(payload, original)
