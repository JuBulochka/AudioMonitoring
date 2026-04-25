"""Development settings — debug mode, relaxed security."""
from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Disable HTTPS enforcement in development
SECURE_SSL_REDIRECT = False

# Show emails in console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Django Debug Toolbar (optional — uncomment if installed)
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
# INTERNAL_IPS = ["127.0.0.1"]

# Relaxed CORS in dev
CORS_ALLOW_ALL_ORIGINS = True

# Use local file storage in dev
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

LOGGING["root"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "DEBUG"  # noqa: F405
