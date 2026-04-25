from django.apps import AppConfig

class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard"
    verbose_name = "Dashboard"

    def ready(self):
        try:
            import apps.dashboard.signals  # noqa: F401
        except ImportError:
            pass
