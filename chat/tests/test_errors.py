"""Phase 11: user-facing handling of proxy failures, without leaking secrets.

Two layers are tested:
- the chat page for every ProviderError kind (adapter mocked), and
- the real adapter wired to the page, with `requests.post` mocked to return each
  HTTP failure the proxy documents. Keys are dummies; nothing reaches the network.
"""
import sys
from decimal import Decimal
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.views.debug import ExceptionReporter

from billing.models import BillingAccount, UsageCharge
from chat.models import ChatSession
from llm.models import LLMModel
from llm.providers import ProviderError, Turn, complete
from llm.tests.test_providers import DUMMY_KEYS, DummyKeysMixin

User = get_user_model()

EXPECTED_MESSAGES = {
    'auth': 'The AI service rejected our credentials. Please contact the administrator.',
    'rate_limited': 'The AI service is busy. Please try again in a moment.',
    'timeout': 'The AI service took too long to respond. Please try again.',
    'upstream': 'The AI service is unavailable right now.',
    'bad_response': 'The AI service is unavailable right now.',
    'bad_request': 'The request could not be processed.',
}
DRAFT = 'Please summarise my notes <b>now</b>'


def fake_response(status, payload=None):
    response = mock.Mock(status_code=status)
    response.json.return_value = payload if payload is not None else {}
    return response


@override_settings(LITECHAT_PROXY_BASE_URL='https://proxy.test')
class ErrorPageTestCase(DummyKeysMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('hans', password='x')
        cls.account = BillingAccount.objects.create(name='HANS LIAM YU', credit=Decimal('2.00'))
        cls.account.members.add(cls.user)

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def session_for(self, api_model='gpt-5.6-luna'):
        return ChatSession.objects.create(user=self.user, billing_account=self.account,
                                          llm_model=LLMModel.objects.get(api_model=api_model))

    def send(self, session, text=DRAFT):
        return self.client.post(f'/chat/{session.pk}/send/', {'content': text})

    def assert_failed_cleanly(self, response, session, message):
        """The page shows `message`, keeps the draft, and nothing was saved or charged."""
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, message)
        self.assertEqual(response.context['draft'], DRAFT)
        self.assertContains(response, 'Please summarise my notes &lt;b&gt;now&lt;/b&gt;</textarea>')
        self.assertFalse(session.messages.exists())
        self.assertFalse(UsageCharge.objects.exists())
        self.assertEqual(BillingAccount.objects.get(pk=self.account.pk).credit, Decimal('2.00'))
        body = response.content.decode()
        for key in DUMMY_KEYS.values():
            self.assertNotIn(key, body)


class ProviderErrorKindTests(ErrorPageTestCase):
    """Every ProviderError kind shows its planned message (plan 11.1, 11.5)."""

    def test_each_kind_shows_its_message_keeps_draft_and_charges_nothing(self):
        session = self.session_for()
        for kind, message in EXPECTED_MESSAGES.items():
            with self.subTest(kind=kind), \
                    mock.patch('llm.providers.complete', side_effect=ProviderError(kind, status_code=500)):
                self.assert_failed_cleanly(self.send(session), session, message)


class ProxyFailureEndToEndTests(ErrorPageTestCase):
    """The real adapter + chat page, with each documented proxy failure simulated."""

    HTTP_CASES = [
        (400, 'bad_request'), (401, 'auth'), (403, 'auth'), (429, 'rate_limited'),
        (500, 'upstream'), (502, 'upstream'), (503, 'upstream'), (504, 'upstream'),
    ]

    def test_http_failures_on_every_provider(self):
        for api_model in ('gpt-5.6-luna', 'claude-haiku-4-5-20251001', 'gemini-3.8-flash'):
            session = self.session_for(api_model)
            for status, kind in self.HTTP_CASES:
                with self.subTest(provider=api_model, status=status), \
                        mock.patch('llm.providers.requests.post', return_value=fake_response(
                            status, {'error': {'message': 'internal upstream detail xyz'}})):
                    response = self.send(session)
                    self.assert_failed_cleanly(response, session, EXPECTED_MESSAGES[kind])
                    self.assertNotContains(response, 'internal upstream detail xyz')

    def test_network_failures(self):
        session = self.session_for()
        cases = [
            (requests.Timeout('read timed out'), 'timeout'),
            (requests.ConnectionError('connection refused'), 'upstream'),
        ]
        for error, kind in cases:
            with self.subTest(error=type(error).__name__), \
                    mock.patch('llm.providers.requests.post', side_effect=error):
                self.assert_failed_cleanly(self.send(session), session, EXPECTED_MESSAGES[kind])

    def test_malformed_success_response(self):
        session = self.session_for()
        with mock.patch('llm.providers.requests.post', return_value=fake_response(200, {'unexpected': True})):
            self.assert_failed_cleanly(self.send(session), session, EXPECTED_MESSAGES['bad_response'])

    def test_missing_key_is_shown_as_credentials_problem_without_calling_proxy(self):
        session = self.session_for('claude-haiku-4-5-20251001')
        with mock.patch.dict('os.environ', {'BUILD_ANTHROPIC_KEY': ''}), \
                mock.patch('llm.providers.requests.post') as post:
            self.assert_failed_cleanly(self.send(session), session, EXPECTED_MESSAGES['auth'])
        post.assert_not_called()

    def test_failures_are_logged_with_kind_and_status_only(self):
        session = self.session_for()
        with mock.patch('llm.providers.requests.post', return_value=fake_response(
                401, {'error': {'message': 'invalid or inactive provider key detail-abc'}})), \
                self.assertLogs('llm.providers', level='WARNING') as logs:
            self.send(session)
        log_text = '\n'.join(logs.output)
        self.assertIn('kind=auth', log_text)
        self.assertIn('status=401', log_text)
        self.assertNotIn('detail-abc', log_text)
        for key in DUMMY_KEYS.values():
            self.assertNotIn(key, log_text)


class SecretHygieneTests(DummyKeysMixin, TestCase):
    def test_unsupported_provider_message_is_generic(self):
        with self.assertRaises(ProviderError) as ctx, self.assertLogs('llm.providers', level='ERROR'):
            complete(LLMModel(provider='mistral', api_model='mistral-x'), [Turn('user', 'hi')])
        self.assertEqual(ctx.exception.user_message, EXPECTED_MESSAGES['bad_request'])
        self.assertNotIn('mistral', ctx.exception.user_message)

    def error_report_html(self, fn):
        """Run `fn` so that an unexpected error escapes mid-request; return Django's HTML error page."""
        model = LLMModel(provider='openai', api_model='gpt-5.6-luna')
        with mock.patch('llm.providers.requests.post', side_effect=ZeroDivisionError('boom')):
            try:
                fn(model, [Turn('user', 'hi')])
            except ZeroDivisionError:
                # Under runserver, request.META carries the process environment, keys included.
                request = RequestFactory().post('/chat/1/send/', **DUMMY_KEYS)
                return ExceptionReporter(request, *sys.exc_info()).get_traceback_html()
        self.fail('expected ZeroDivisionError')

    def test_error_pages_do_not_contain_keys_with_debug_on_or_off(self):
        """If something unexpected escapes complete(), the debug page / error report hides the key."""
        for debug in (True, False):
            with self.subTest(DEBUG=debug), override_settings(DEBUG=debug):
                html = self.error_report_html(complete)
                self.assertIn('ZeroDivisionError', html)
                self.assertIn('********************', html)  # sensitive locals were captured and masked
                for key in DUMMY_KEYS.values():
                    self.assertNotIn(key, html)

    def test_masking_depends_on_sensitive_variables(self):
        # Guard against the decorator being removed: the undecorated function would leak the key.
        with override_settings(DEBUG=True):
            self.assertIn('dummy-openai-key', self.error_report_html(complete.__wrapped__))
