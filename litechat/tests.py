"""Phase 1 smoke tests: the project is configured and serves its basic routes."""
from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase


class ProjectConfigTests(SimpleTestCase):
    def test_litechat_apps_are_installed(self):
        for app_label in ('billing', 'llm', 'chat'):
            self.assertTrue(apps.is_installed(app_label), app_label)

    def test_proxy_settings(self):
        self.assertEqual(settings.LITECHAT_PROXY_BASE_URL, 'https://proxy.litechat.ai')
        self.assertEqual(settings.LITECHAT_PROXY_TIMEOUT, 120)
        self.assertEqual(settings.LITECHAT_MAX_OUTPUT_TOKENS, 1024)

    def test_auth_redirect_settings(self):
        self.assertEqual(settings.LOGIN_URL, '/login/')
        self.assertEqual(settings.LOGIN_REDIRECT_URL, '/chat/')
        self.assertEqual(settings.LOGOUT_REDIRECT_URL, '/login/')

    def test_base_template_links_stylesheet(self):
        html = render_to_string('base.html')
        self.assertIn('/static/css/app.css', html)
        self.assertIn('<title>LiteChat</title>', html)

    def test_stylesheet_is_findable(self):
        self.assertIsNotNone(finders.find('css/app.css'))


class ProjectRoutesTests(TestCase):
    def test_root_redirects_to_chat(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/chat/', fetch_redirect_response=False)

    def test_admin_login_page_loads(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
