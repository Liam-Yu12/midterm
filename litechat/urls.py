"""URL configuration for the LiteChat MVP. Route table: doc/plan/litechat-mvp.md."""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/chat/', permanent=False)),
    path('login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('chat/', include('chat.urls')),
    path('', include('billing.urls')),
]
