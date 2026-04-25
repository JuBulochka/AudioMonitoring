from django.apps import AppConfig

class AlertsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.alerts"
    verbose_name = "Alerts"

    def ready(self):
        try:
            import apps.alerts.signals  # noqa: F401
        except ImportError:
            pass
