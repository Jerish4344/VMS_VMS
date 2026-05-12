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
    # Bundle (multiple SORs in one trip)
    path('bundle/create/', views.sor_bundle_create, name='sor_bundle_create'),
    path('bundle/<uuid:bundle_id>/', views.sor_bundle_progress, name='sor_bundle_progress'),
    path('bundle/<uuid:bundle_id>/accept/', views.sor_bundle_accept, name='sor_bundle_accept'),
    path('bundle/<uuid:bundle_id>/sor/<int:sor_id>/complete/', views.sor_bundle_complete_sor, name='sor_bundle_complete_sor'),
    path('notifications/api/', sor_notifications_api, name='sor_notifications_api'),
]
