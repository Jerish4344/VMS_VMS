from django.apps import AppConfig


class GeolocationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'geolocation'
    # Human-friendly name shown in Django admin “Applications” list
    verbose_name = 'GPS Tracking / Geolocation'
