from django.apps import AppConfig

class RemoteAccessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.remote_access"
    verbose_name = "Remote_access"

    def ready(self):
        try:
            import apps.remote_access.signals  # noqa: F401
        except ImportError:
            pass
