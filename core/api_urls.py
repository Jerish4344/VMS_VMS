from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import api_views

router = SimpleRouter()
router.register(r'vehicles', api_views.VehicleViewSet, basename='api-vehicle')
router.register(r'trips', api_views.TripViewSet, basename='api-trip')
router.register(r'maintenance', api_views.MaintenanceViewSet, basename='api-maintenance')
router.register(r'fuel', api_views.FuelTransactionViewSet, basename='api-fuel')
router.register(r'documents', api_views.DocumentViewSet, basename='api-document')

urlpatterns = [
    # Auth endpoints
    path('auth/login/', api_views.LoginView.as_view(), name='api-login'),
    path('auth/logout/', api_views.LogoutView.as_view(), name='api-logout'),
    path('auth/profile/', api_views.ProfileView.as_view(), name='api-profile'),
    path('auth/profile/stats/', api_views.UserProfileStatsView.as_view(), name='api-profile-stats'),
    
    # Dashboard
    path('dashboard/', api_views.DashboardView.as_view(), name='api-dashboard'),
    path('dashboard/stats/', api_views.DashboardStatsView.as_view(), name='api-dashboard-stats'),
    
    # Trip specific endpoints (MUST be before router.urls)
    path('trips/start/', api_views.StartTripView.as_view(), name='api-start-trip'),
    path('trips/my-trips/', api_views.MyTripsView.as_view(), name='api-my-trips'),
    path('trips/ongoing/', api_views.OngoingTripsView.as_view(), name='api-ongoing-trips'),
    path('trips/<int:pk>/end/', api_views.EndTripView.as_view(), name='api-end-trip'),
    path('trips/<int:pk>/upload-odometer-image/', api_views.TripUploadOdometerImageView.as_view(), name='api-trip-upload-odometer-image'),
    
    # Vehicle types
    path('vehicles/types/', api_views.VehicleTypeListView.as_view(), name='api-vehicle-types'),
    
    # Maintenance types
    path('maintenance/types/', api_views.MaintenanceTypeListView.as_view(), name='api-maintenance-types'),
    
    # Fuel stations
    path('fuel/stations/', api_views.FuelStationListView.as_view(), name='api-fuel-stations'),
    
    # Document types and expiring
    path('documents/types/', api_views.DocumentTypeListView.as_view(), name='api-document-types'),
    path('documents/expiring/', api_views.ExpiringDocumentsView.as_view(), name='api-expiring-documents'),
    
    # SOR endpoints
    path('sor/', api_views.SORListView.as_view(), name='api-sor-list'),
    path('sor/<int:pk>/', api_views.SORDetailView.as_view(), name='api-sor-detail'),
    path('sor/<int:pk>/accept/', api_views.SORAcceptView.as_view(), name='api-sor-accept'),
    path('sor/<int:pk>/reject/', api_views.SORRejectView.as_view(), name='api-sor-reject'),
    path('sor/notifications/', api_views.SORNotificationsView.as_view(), name='api-sor-notifications'),
    path('sor/notifications/<int:pk>/read/', api_views.SORNotificationMarkReadView.as_view(), name='api-sor-notification-read'),
    path('sor/notifications/mark-all-read/', api_views.SORNotificationMarkAllReadView.as_view(), name='api-sor-notifications-mark-all-read'),
    
    # Personal Vehicle Staff endpoints
    path('personal-vehicles/', api_views.PersonalVehicleListView.as_view(), name='api-personal-vehicles'),
    path('personal-vehicles/<int:pk>/', api_views.PersonalVehicleDetailView.as_view(), name='api-personal-vehicle-detail'),
    path('personal-vehicles/reimbursement/', api_views.PersonalVehicleReimbursementView.as_view(), name='api-personal-vehicle-reimbursement'),
    path('personal-vehicles/dashboard/', api_views.PersonalVehicleDashboardView.as_view(), name='api-personal-vehicle-dashboard'),
    
    # GPS Tracking endpoints for mobile app
    path('gps/record/', api_views.GPSRecordLocationView.as_view(), name='api-gps-record'),
    path('gps/batch/', api_views.GPSBatchRecordView.as_view(), name='api-gps-batch'),
    path('gps/status/<int:trip_id>/', api_views.GPSTripStatusView.as_view(), name='api-gps-status'),
    path('gps/finalize/<int:trip_id>/', api_views.GPSFinalizeView.as_view(), name='api-gps-finalize'),
    path('gps/route/<int:trip_id>/', api_views.GPSTripRouteView.as_view(), name='api-gps-route'),
    
    # ===== P2P Integration Endpoints =====
    # For external P2P (Procure to Pay) system to fetch SOR data for SIR creation
    path('p2p/sor/', api_views.P2PSORListView.as_view(), name='api-p2p-sor-list'),
    path('p2p/sor/<int:pk>/', api_views.P2PSORDetailView.as_view(), name='api-p2p-sor-detail'),
    path('p2p/sor/<int:pk>/confirm-receipt/', api_views.P2PSORConfirmReceiptView.as_view(), name='api-p2p-sor-confirm-receipt'),
    
    # Router URLs (ViewSets) - must be last to not override specific paths
    path('', include(router.urls)),
]
