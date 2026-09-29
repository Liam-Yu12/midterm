"""Phase 2: login, logout and protection of app pages."""
from django.contrib.auth import get_user_model
from django.test import TestCase

# App pages that must require login. Phase 5 adds /chat/new/.
PROTECTED_URLS = ['/chat/', '/profile/']

PASSWORD = 'correct-horse-battery'


class LoginRequiredTests(TestCase):
    def test_anonymous_users_are_redirected_to_login(self):
        for url in PROTECTED_URLS:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f'/login/?next={url}', fetch_redirect_response=False)


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='hans', password=PASSWORD)

    def test_login_page_renders(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/login.html')
        self.assertContains(response, 'Welcome!')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'LOG-IN')

    def test_valid_login_redirects_to_chat(self):
        response = self.client.post('/login/', {'username': 'hans', 'password': PASSWORD})
        self.assertRedirects(response, '/chat/')
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_valid_login_honours_next(self):
        response = self.client.post('/login/', {'username': 'hans', 'password': PASSWORD, 'next': '/chat/'})
        self.assertRedirects(response, '/chat/')

    def test_bad_password_shows_error(self):
        response = self.client.post('/login/', {'username': 'hans', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct username and password')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logged_in_user_visiting_login_goes_to_chat(self):
        self.client.force_login(self.user)
        response = self.client.get('/login/')
        self.assertRedirects(response, '/chat/')

    def test_chat_page_uses_app_layout_for_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get('/chat/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'app_layout.html')
        self.assertContains(response, 'Signed in as hans')
        self.assertContains(response, 'action="/logout/"')


class LogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='hans', password=PASSWORD)

    def test_logout_post_ends_session(self):
        self.client.force_login(self.user)
        response = self.client.post('/logout/')
        self.assertRedirects(response, '/login/')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertRedirects(self.client.get('/chat/'), '/login/?next=/chat/', fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get('/logout/')
        self.assertEqual(response.status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
