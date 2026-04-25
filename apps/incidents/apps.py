from django.apps import AppConfig

class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.incidents"
    verbose_name = "Incidents"

    def ready(self):
        try:
            import apps.incidents.signals  # noqa: F401
        except ImportError:
            pass
