# vehicle_management/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# ZeptoMail alert recipients for trip distance alerts
import json as _json
ZEPTO_ALERT_RECIPIENTS = _json.loads(os.environ.get('ZEPTO_ALERT_RECIPIENTS', '[]'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('DJANGO_SECRET_KEY environment variable is required in production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = [
    '52.87.151.66',
    'vms.jeyarama.com',
    'localhost',
    '127.0.0.1'
]

# SSL Settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS — tell browsers to always use HTTPS
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Additional security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'crispy_forms',
    'crispy_bootstrap5',
    'drf_spectacular',
    'compressor',
    
    # Project apps
    'core',
    'accounts',
    'vehicles',
    'trips',
    'maintenance',
    'fuel',
    'documents',
    'geolocation',
    'dashboard',
    'accidents',
    'reports',
    'generators',
    'sor',
    'chatbot',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # GZipMiddleware is handled by the Nginx
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.DriverApprovalMiddleware',  # Add this line
]

ROOT_URLCONF = 'vehicle_management.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dashboard.context_processors.notifications_processor',
                'accounts.context_processors.approval_notifications',  # Add this line
            ],
        },
    },
]

WSGI_APPLICATION = 'vehicle_management.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'vms'),
        'USER': os.environ.get('DB_USER', 'admin'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'autocommit': True,
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'connect_timeout': 30,  # Reduced from 60
            'read_timeout': 60,     # Reduced from 300
            'write_timeout': 60,    # Reduced from 300
        },
        'CONN_MAX_AGE': 300,  # Keep connections alive for 5 minutes
        'CONN_HEALTH_CHECKS': True,  # Enable connection health checks
    }
}

# =============================================================================
# REDIS CACHE CONFIGURATION
# =============================================================================
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
            'IGNORE_EXCEPTIONS': True,  # Silently fail if Redis is down
        }
    }
}

# Use cached_db sessions: cache-first with DB fallback (works if Redis is down)
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# Cache timeout defaults (in seconds)
CACHE_TTL = 60 * 5  # 5 minutes default

# =============================================================================
# CELERY CONFIGURATION (uses Redis DB 2, cache uses DB 1)
# =============================================================================
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/2')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 min soft limit
CELERY_TASK_TIME_LIMIT = 600       # 10 min hard limit
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# In DEBUG mode, run tasks synchronously (no Redis/worker needed for local dev)
if DEBUG:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# Celery Beat — periodic task schedule
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'send-document-expiry-notifications': {
        'task': 'core.tasks.run_management_command',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM IST
        'args': ('send_document_expiry_notifications', '--days', '30'),
    },
    'send-maintenance-reminders': {
        'task': 'core.tasks.run_management_command',
        'schedule': crontab(hour=8, minute=15),  # Daily at 8:15 AM IST
        'args': ('send_maintenance_reminders', '--days', '3'),
    },
    'send-approval-reminders': {
        'task': 'core.tasks.run_management_command',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM IST
        'args': ('send_approval_reminders',),
    },
    'archive-location-history': {
        'task': 'core.tasks.run_management_command',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),  # 1st of every month at 2 AM
        'args': ('archive_location_history', '--days', '90', '--execute'),
    },
    'overnight-trip-alert': {
        'task': 'trips.tasks.send_overnight_trip_alert_async',
        'schedule': crontab(hour=5, minute=30),  # Daily at 5:30 AM IST
    },
}

# Jazzmin Settings
JAZZMIN_SETTINGS = {
    # title of the window (Will default to current_admin_site.site_title if absent or None)
    "site_title": "Vehicle Management System",
    
    # Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_header": "VMS Admin",
    
    # Logo to use for your site, must be present in static files
    # "site_logo": "img/logo.png",
    
    # CSS classes that are applied to the logo
    "site_logo_classes": "img-circle",
    
    # Welcome text on the login screen
    "welcome_sign": "Welcome to the Vehicle Management System",
    
    # Copyright on the footer
    "copyright": "Vehicle Management System Ltd",
    
    # The model admin to search from the search bar
    "search_model": "vehicles.Vehicle",
    
    # Field name on user model that contains avatar image
    "user_avatar": None,
    
    ############
    # Top Menu #
    ############
    # Links to put along the top menu
    "topmenu_links": [
        # Url that gets reversed (Permissions can be added)
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        
        # External url that opens in a new window (Permissions can be added)
        {"name": "Support", "url": "https://github.com/yourusername/vehicle-management-system", "new_window": True},
        
        # Model admin to link to (Permissions checked against model)
        {"model": "auth.User"},
        
        # App with dropdown menu to all its models pages
        {"app": "vehicles"},
        {"app": "maintenance"},
    ],
    
    #############
    # Side Menu #
    #############
    # Whether to display the side menu
    "show_sidebar": True,
    
    # Whether to aut expand the menu
    "navigation_expanded": True,
    
    # List of apps to base side menu ordering off of
    "order_with_respect_to": ["auth", "vehicles", "maintenance", "accounts"],
    
    # Custom icons for side menu apps/models
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "vehicles.Vehicle": "fas fa-car",
        "vehicles.VehicleType": "fas fa-truck",
        "maintenance.Maintenance": "fas fa-wrench",
        "maintenance.MaintenanceType": "fas fa-tools",
        "maintenance.MaintenanceProvider": "fas fa-building",
    },
    
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    
    #################
    # Related Modal #
    #################
    # Use modals instead of popups for related lookups
    "related_modal_active": True,
    
    #############
    # UI Tweaks #
    #############
    # Relative paths to custom CSS/JS scripts (must be present in static files)
    "custom_css": None,
    "custom_js": None,
    
    # Whether to show the UI customizer on the sidebar
    "show_ui_builder": True,
    
    ###############
    # Change view #
    ###############
    # Render out the change view as a single form, or in tabs
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
}

# Custom admin site settings
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

# Custom user model
AUTH_USER_MODEL = 'accounts.CustomUser'

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# Add your app's static directories
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),  # if you have a main static folder
    # Add other static directories if needed
]

# Make sure you have this
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # Throttling — protects the server with 300 concurrent users
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '120/minute',
        'gps_tracking': '600/minute',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# CORS Settings for Mobile App
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://vms.jeyarama.com",
    "https://52.87.151.66",
]
CORS_ALLOW_CREDENTIALS = True

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.zeptomail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@jeyarama.com')

# ZeptoMail API settings
ZEPTO_API_KEY = os.environ.get('ZEPTO_API_KEY', '')  # Set via environment variable
ZEPTO_TEMPLATE_KEY = ''  # (Optional) Paste your ZeptoMail template key here if using templates

# Google Maps API Configuration
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

# Groq AI API key (for chatbot)
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# Document settings
ALLOWED_DOCUMENT_TYPES = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB

# Sentry Error Tracking
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
    )

# drf-spectacular (OpenAPI/Swagger)
SPECTACULAR_SETTINGS = {
    'TITLE': 'VMS Fleet Management API',
    'DESCRIPTION': 'Vehicle Management System REST API for mobile and web clients.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Django Compressor
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)
COMPRESS_ENABLED = True
COMPRESS_CSS_FILTERS = ['compressor.filters.css_default.CssAbsoluteFilter', 'compressor.filters.cssmin.CSSMinFilter']
COMPRESS_JS_FILTERS = ['compressor.filters.jsmin.JSMinFilter']

# Geolocation settings
LOCATION_UPDATE_INTERVAL = 30  # Seconds

# Vehicle tracking settings
TRIP_END_AUTO_TIMEOUT = 12  # Hours - time after which an ongoing trip will be auto-ended

# Custom template tags
from django.template.defaultfilters import register

@register.filter(name='status_color')
def status_color(status):
    colors = {
        'available': 'success',
        'in_use': 'primary',
        'maintenance': 'warning',
        'retired': 'secondary',
        'ongoing': 'info',
        'completed': 'success',
        'cancelled': 'danger',
        'scheduled': 'warning',
        'in_progress': 'primary',
        'reported': 'warning',
        'under_investigation': 'info',
        'repair_scheduled': 'primary',
        'repair_in_progress': 'primary',
        'resolved': 'success',
    }
    return colors.get(status, 'secondary')

LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTHENTICATION_BACKENDS = [
    'accounts.backends.CombinedAuthBackend',  # Primary: routes non-drivers locally, only calls StyleHR for drivers
    'django.contrib.auth.backends.ModelBackend',  # Fallback: Django default
]

CSRF_TRUSTED_ORIGINS = [
    "https://vms.jeyarama.com",
    "http://vms.jeyarama.com:8000",
]

# StyleHR API Configuration
STYLEHR_API_URL = 'https://stylehr.in/api/login/'
STYLEHR_API_TIMEOUT = 10  # seconds (reduced from 30 to avoid blocking workers)

import logging

class IgnoreNotificationPolling(logging.Filter):
    def filter(self, record):
        # Filter out notification polling and other frequent requests
        message = record.getMessage()
        return not any(path in message for path in [
            '/accounts/notifications/data/',
            'GET /accounts/notifications/data/',
            'accounts/notifications/data'
        ])

# Ensure logs directory exists
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'filters': {
        'ignore_polling': {
            '()': IgnoreNotificationPolling,
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'approval_auth.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['ignore_polling'],
        },
    },
    'root': {
        'handlers': ['console'],
    },
    'loggers': {
        'accounts.backends': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'accounts.views': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Session Configuration
SESSION_COOKIE_AGE = 8 * 60 * 60  # 8 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Security Settings for API calls
REQUESTS_TIMEOUT = 30
REQUESTS_VERIFY_SSL = True  # Set to False only for development with self-signed certificates

# Notification settings
DRIVER_APPROVAL_NOTIFICATIONS = True
DEFAULT_FROM_EMAIL = 'noreply@yourvms.com'

# Bulk upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB (was 100MB — prevents memory abuse)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000    # Reduced from 10000

# Disable atomic requests for bulk operations
ATOMIC_REQUESTS = False
