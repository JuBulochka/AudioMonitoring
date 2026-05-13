"""API v1 URL routing."""
from django.urls import path, include
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """GET /api/v1/auth/me/ — return current user profile."""
    user = request.user
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.get_full_name() or user.username,
        "role": user.role,
        "role_display": user.get_role_display(),
        "is_active": user.is_active,
    })


urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", me, name="api-me"),

    path("device/", include("api.v1.device_endpoints")),

    path("devices/", include("api.v1.operator_endpoints")),
    path("packets/", include("api.v1.packet_endpoints")),
    path("incidents/", include("api.v1.incident_endpoints")),
    path("tasks/", include("api.v1.task_endpoints")),
    path("alerts/", include("api.v1.alert_endpoints")),
    path("remote-access/", include("api.v1.remote_access_endpoints")),
    path("dashboard/", include("api.v1.dashboard_endpoints")),
    path("map/", include("api.v1.map_endpoints")),
    path("commands/", include("api.v1.commands_endpoints")),
]
