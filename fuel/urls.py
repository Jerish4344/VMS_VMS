from django.urls import path
from .views import (
    FuelTransactionListView, FuelTransactionDetailView, FuelTransactionCreateView,
    FuelTransactionUpdateView, FuelTransactionDeleteView,
    FuelStationListView, FuelStationCreateView, FuelStationUpdateView, FuelStationDeleteView
)

urlpatterns = [
    path('', FuelTransactionListView.as_view(), name='fuel_transaction_list'),
    path('<int:pk>/', FuelTransactionDetailView.as_view(), name='fuel_transaction_detail'),
    path('add/', FuelTransactionCreateView.as_view(), name='fuel_transaction_create'),
    path('<int:pk>/edit/', FuelTransactionUpdateView.as_view(), name='fuel_transaction_update'),
    path('<int:pk>/delete/', FuelTransactionDeleteView.as_view(), name='fuel_transaction_delete'),
    
    path('stations/', FuelStationListView.as_view(), name='fuel_station_list'),
    path('stations/add/', FuelStationCreateView.as_view(), name='fuel_station_create'),
    path('stations/<int:pk>/edit/', FuelStationUpdateView.as_view(), name='fuel_station_update'),
    path('stations/<int:pk>/delete/', FuelStationDeleteView.as_view(), name='fuel_station_delete'),
]