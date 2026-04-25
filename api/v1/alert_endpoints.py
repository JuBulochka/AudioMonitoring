"""Alert / Notification REST API."""
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alerts.models import Alert, Notification
from apps.common.pagination import StandardResultsSetPagination


class AlertSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(source="get_alert_type_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    device_serial = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "id", "device", "device_serial", "incident",
            "alert_type", "alert_type_display",
            "severity", "severity_display",
            "title", "message", "payload", "created_at",
        ]

    def get_device_serial(self, obj):
        return obj.device.serial_number if obj.device else None


class NotificationSerializer(serializers.ModelSerializer):
    alert = AlertSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "alert", "is_read", "read_at", "is_dismissed", "created_at"]


class NotificationListView(generics.ListAPIView):
    """GET /api/v1/alerts/notifications/ — current user's inbox."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = Notification.objects.filter(
            user=self.request.user,
            is_dismissed=False,
        ).select_related("alert__device")

        unread_only = self.request.query_params.get("unread_only")
        if unread_only == "true":
            qs = qs.filter(is_read=False)

        return qs


class MarkNotificationReadView(APIView):
    """POST /api/v1/alerts/notifications/<id>/read/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        try:
            notif = Notification.objects.get(id=id, user=request.user)
        except Notification.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        notif.mark_read()
        return Response({"success": True})


class MarkAllReadView(APIView):
    """POST /api/v1/alerts/notifications/mark-all-read/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.utils import timezone
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({"success": True, "marked_count": count})


class UnreadCountView(APIView):
    """GET /api/v1/alerts/notifications/unread-count/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False, is_dismissed=False).count()
        return Response({"unread_count": count})


from django.urls import path  # noqa: E402

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="api-notification-list"),
    path("notifications/unread-count/", UnreadCountView.as_view(), name="api-unread-count"),
    path("notifications/mark-all-read/", MarkAllReadView.as_view(), name="api-mark-all-read"),
    path("notifications/<uuid:id>/read/", MarkNotificationReadView.as_view(), name="api-notification-read"),
]
