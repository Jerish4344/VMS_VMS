from django.urls import path

from . import views
from .views_notification import sor_notifications_api

urlpatterns = [
    path('', views.sor_list, name='sor_list'),
    path('create/', views.sor_create, name='sor_create'),
    path('export/', views.sor_export, name='sor_export'),
    path('accept/<int:pk>/', views.sor_accept, name='sor_accept'),
    path('view/<int:pk>/', views.sor_view, name='sor_view'),
    path('edit/<int:pk>/', views.sor_edit, name='sor_edit'),
    path('delete/<int:pk>/', views.sor_delete, name='sor_delete'),
    path('notifications/api/', sor_notifications_api, name='sor_notifications_api'),
]
