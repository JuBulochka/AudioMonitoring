"""Development settings — debug mode, relaxed security."""
from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = [
    "https://almetpt-tatneft.ru",
    "https://www.almetpt-tatneft.ru",
    "http://localhost",
    "http://127.0.0.1",
]

SECURE_SSL_REDIRECT = False

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


CORS_ALLOW_ALL_ORIGINS = True

DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

LOGGING["root"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "DEBUG"  # noqa: F405
