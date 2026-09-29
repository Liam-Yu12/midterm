"""URL configuration for the LiteChat MVP. Route table: doc/plan/litechat-mvp.md."""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/chat/', permanent=False)),
    path('chat/', include('chat.urls')),
    path('', include('billing.urls')),
    # Login/logout views are wired in Phase 2.
]
