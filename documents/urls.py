from django.urls import path
from .views import (
    DocumentListView, DocumentDetailView, DocumentCreateView,
    DocumentUpdateView, DocumentDeleteView,
    DocumentTypeListView, DocumentTypeCreateView, DocumentTypeUpdateView, DocumentTypeDeleteView
)

urlpatterns = [
    path('', DocumentListView.as_view(), name='document_list'),
    path('<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
    path('add/', DocumentCreateView.as_view(), name='document_create'),
    path('<int:pk>/edit/', DocumentUpdateView.as_view(), name='document_update'),
    path('<int:pk>/delete/', DocumentDeleteView.as_view(), name='document_delete'),
    
    path('types/', DocumentTypeListView.as_view(), name='document_type_list'),
    path('types/add/', DocumentTypeCreateView.as_view(), name='document_type_create'),
    path('types/<int:pk>/edit/', DocumentTypeUpdateView.as_view(), name='document_type_update'),
    path('types/<int:pk>/delete/', DocumentTypeDeleteView.as_view(), name='document_type_delete'),
]