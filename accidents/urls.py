from django.urls import path
from .views import (
    AccidentListView, AccidentDetailView, AccidentCreateView,
    AccidentUpdateView, AccidentDeleteView, RemoveAccidentImageView
)

urlpatterns = [
    path('', AccidentListView.as_view(), name='accident_list'),
    path('<int:pk>/', AccidentDetailView.as_view(), name='accident_detail'),
    path('add/', AccidentCreateView.as_view(), name='accident_create'),
    path('<int:pk>/edit/', AccidentUpdateView.as_view(), name='accident_update'),
    path('<int:pk>/delete/', AccidentDeleteView.as_view(), name='accident_delete'),
    path('image/<int:pk>/remove/', RemoveAccidentImageView.as_view(), name='remove_accident_image'),
]