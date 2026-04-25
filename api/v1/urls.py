"""API v1 URL routing."""
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # JWT auth (for operator API clients)
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Device-facing endpoints (authenticated by X-Device-Key header)
    path("device/", include("api.v1.device_endpoints")),

    # Operator-facing REST API
    path("devices/", include("api.v1.operator_endpoints")),
    path("packets/", include("api.v1.packet_endpoints")),
    path("incidents/", include("api.v1.incident_endpoints")),
    path("tasks/", include("api.v1.task_endpoints")),
    path("alerts/", include("api.v1.alert_endpoints")),
    path("remote-access/", include("api.v1.remote_access_endpoints")),
    path("dashboard/", include("api.v1.dashboard_endpoints")),
    path("map/", include("api.v1.map_endpoints")),
    # Command dispatch (operator sends commands to devices)
    path("commands/", include("api.v1.commands_endpoints")),
]
