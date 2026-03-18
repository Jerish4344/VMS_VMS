from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.db import connection
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from dashboard.views import DashboardView

def health_check(request):
    """Health check endpoint for monitoring / load balancer.
    Returns minimal info to avoid leaking system details."""
    from django.core.cache import cache as _cache

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    
    # Check Redis cache
    try:
        _cache.set('_health_check', '1', 10)
        cache_ok = _cache.get('_health_check') == '1'
    except Exception:
        cache_ok = False
    
    overall = "ok" if (db_ok and cache_ok) else "degraded"
    status_code = 200 if overall == "ok" else 503
    return JsonResponse({"status": overall}, status=status_code)

urlpatterns = [
    # Health check endpoint (no auth required)
    path('health/', health_check, name='health_check'),

    # Privacy Policy (for Google Play Store)
    path('privacy-policy/', TemplateView.as_view(template_name='privacy_policy.html'), name='privacy_policy'),
    
    # Data Deletion Request (for Google Play Store)
    path('data-deletion/', TemplateView.as_view(template_name='data_deletion.html'), name='data_deletion'),

    path('admin/', admin.site.urls),
    
    # Dashboard
    path('', DashboardView.as_view(), name='dashboard'),
    path('dashboard/', include('dashboard.urls')),
    
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

    # Generator Management
    path('generators/', include('generators.urls')),
    
    # Document Management
    path('documents/', include('documents.urls')),
    
    # Accident Management
    path('accidents/', include('accidents.urls')),

    # SOR Management
    path('sor/', include('sor.urls')),
    
    # Reports
    path('reports/', include('reports.urls')),
    
    # Chatbot
    path('chatbot/', include('chatbot.urls')),
    
    # Geolocation / Tracking
    path('geolocation/', include('geolocation.urls')),

    # API Endpoints (Mobile + Core)
    path('api/', include('core.api_urls')),

    # API Documentation (Swagger/OpenAPI)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
