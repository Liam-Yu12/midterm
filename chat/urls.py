from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.home, name='home'),
    path('new/', views.new_session, name='new_session'),
    path('<int:pk>/', views.session_detail, name='session_detail'),
    path('<int:pk>/send/', views.send_message, name='send_message'),
    path('<int:pk>/rename/', views.rename_session, name='rename_session'),
    path('<int:pk>/delete/', views.delete_session, name='delete_session'),
]
