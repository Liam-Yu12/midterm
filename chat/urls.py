from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.home, name='home'),
    path('new/', views.new_session, name='new_session'),
    path('<int:pk>/', views.session_detail, name='session_detail'),
]
