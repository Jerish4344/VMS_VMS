# vehicle_management/settings.py

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '41o!--&b-+974d)us83w0$l0y_%xhw(-7+xxn4h0n*=c#hjt5-'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = [
    '44.202.73.68',
    'vms.jeyarama.com',
    'localhost',
    '127.0.0.1'
]

# SSL Settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

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
    'crispy_forms',
    'crispy_bootstrap5',
    
    # Project apps
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
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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
        'NAME': 'vms',
        'USER': 'admin',
        'PASSWORD': 'Qsys160w',
        'HOST': 'database-1.cu94as0wos8e.us-east-1.rds.amazonaws.com',
        'PORT': '3306',
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

# For production, consider using PostgreSQL:
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'vehicle_management',
#         'USER': 'postgres',
#         'PASSWORD': 'your_password',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

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
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Email settings (update these for production)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' # For development
# For production, use SMTP:
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-email@gmail.com'
# EMAIL_HOST_USER_PASSWORD = 'your-email-password'

# Document settings
ALLOWED_DOCUMENT_TYPES = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB

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
    'accounts.backends.StyleHRAuthBackend',  # Primary: StyleHR authentication
    'django.contrib.auth.backends.ModelBackend',  # Fallback: Django default
    'accounts.backends.CombinedAuthBackend',  # Our new combined backend
]

CSRF_TRUSTED_ORIGINS = [
    "https://vms.jeyarama.com",
    "http://vms.jeyarama.com:8000",
]

# StyleHR API Configuration
STYLEHR_API_URL = 'https://stylehr.in/api/login/'
STYLEHR_API_TIMEOUT = 30  # seconds


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/approval_auth.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'accounts.backends': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'accounts.views': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
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

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'ignore_polling': {
            '()': IgnoreNotificationPolling,
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['ignore_polling'],
        },
    },
    'root': {
        'handlers': ['console'],
    },
    'loggers': {
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Bulk upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000    # For many records

# Disable atomic requests for bulk operations
ATOMIC_REQUESTS = False

