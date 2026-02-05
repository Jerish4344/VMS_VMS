from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.db import connection
from django.views.generic import TemplateView
from dashboard.views import DashboardView

def health_check(request):
    """Health check endpoint for monitoring."""
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return JsonResponse({
        "status": "ok" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "1.0.0",
    })

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
    
    # API Endpoints
    path('api/', include('geolocation.urls')),

    # Mobile API Endpoints
    path('api/', include('core.api_urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
