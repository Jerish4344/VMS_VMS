from django.urls import path

from . import views
from .views_notification import sor_notifications_api

urlpatterns = [
    path('', views.sor_list, name='sor_list'),
    path('create/', views.sor_create, name='sor_create'),
    path('accept/<int:pk>/', views.sor_accept, name='sor_accept'),
    path('notifications/api/', sor_notifications_api, name='sor_notifications_api'),
]
