"""Remote Access REST API — session list only."""
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated

from apps.remote_access.models import RemoteAccessSession
from apps.common.pagination import StandardResultsSetPagination


class RemoteAccessSessionSerializer(serializers.ModelSerializer):
    device_serial = serializers.CharField(source="device.serial_number", read_only=True)
    operator_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    duration_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = RemoteAccessSession
        fields = [
            "id", "device", "device_serial", "operator", "operator_name",
            "status", "status_display",
            "tunnel_host", "tunnel_port",
            "started_at", "ended_at", "duration_seconds",
            "operator_ip", "session_notes",
            "created_at",
        ]

    def get_operator_name(self, obj):
        return obj.operator.get_full_name() or obj.operator.username


class RemoteSessionListView(generics.ListAPIView):
    """GET /api/v1/remote-access/sessions/"""
    serializer_class = RemoteAccessSessionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        from apps.users.models import UserRole
        qs = RemoteAccessSession.objects.select_related("device", "operator")
        if self.request.user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
            qs = qs.filter(operator=self.request.user)
        return qs


from django.urls import path  # noqa: E402

urlpatterns = [
    path("sessions/", RemoteSessionListView.as_view(), name="api-remote-session-list"),
]
