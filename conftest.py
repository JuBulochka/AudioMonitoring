import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Make Celery tasks run synchronously in tests
from django.conf import settings
settings.CELERY_TASK_ALWAYS_EAGER = True
settings.CELERY_TASK_EAGER_PROPAGATES = True

from config.celery import app as celery_app
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True
