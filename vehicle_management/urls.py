from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dashboard.views import DashboardView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Dashboard
    path('', DashboardView.as_view(), name='dashboard'),
    
    # Authentication
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Vehicle Management
    path('vehicles/', include('vehicles.urls')),
    
    # Trip Management
    path('trips/', include('trips.urls')),
    
    # Maintenance Management
    path('maintenance/', include('maintenance.urls')),
    
    # Fuel Management
    path('fuel/', include('fuel.urls')),
    
    # Document Management
    path('documents/', include('documents.urls')),
    
    # Accident Management
    path('accidents/', include('accidents.urls')),
    
    # Reports
    path('reports/', include('reports.urls')),
    
    # API Endpoints
    path('api/', include('geolocation.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)