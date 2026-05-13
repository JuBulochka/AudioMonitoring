"""REST API уведомлений для списка, счетчика и отметки прочитанного."""
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alerts.models import Alert, Notification
from apps.common.pagination import StandardResultsSetPagination



class FlatNotificationSerializer(serializers.ModelSerializer):
    """Превращает связку Alert и Notification в один объект для фронтенда."""
    title = serializers.CharField(source="alert.title", read_only=True)
    message = serializers.CharField(source="alert.message", read_only=True)
    severity = serializers.CharField(source="alert.severity", read_only=True)
    severity_display = serializers.SerializerMethodField()
    device = serializers.SerializerMethodField()
    incident = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title", "message",
            "severity", "severity_display",
            "is_read", "is_dismissed",
            "created_at",
            "device", "incident",
        ]

    def get_severity_display(self, obj):
        return obj.alert.get_severity_display()

    def get_device(self, obj):
        d = obj.alert.device
        if not d:
            return None
        return {"id": str(d.id), "serial_number": d.serial_number}

    def get_incident(self, obj):
        i = obj.alert.incident
        if not i:
            return None
        return {"id": str(i.id), "title": i.title}



class NotificationListView(generics.ListAPIView):
    """Возвращает уведомления пользователя с фильтром прочитано/непрочитано."""
    serializer_class = FlatNotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = Notification.objects.filter(
            user=self.request.user,
            is_dismissed=False,
        ).select_related("alert__device", "alert__incident").order_by("-created_at")

        params = self.request.query_params
        is_read_param = params.get("is_read", "").lower()
        unread_only_param = params.get("unread_only", "").lower()
        if is_read_param == "false" or unread_only_param == "true":
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
    """POST /api/v1/alerts/notifications/read-all/ (alias: mark-all-read/)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({"success": True, "marked_count": count})


class UnreadCountView(APIView):
    """GET /api/v1/alerts/notifications/unread-count/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False, is_dismissed=False
        ).count()
        return Response({"count": count, "unread_count": count})


from django.urls import path  # noqa: E402

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="api-notification-list"),
    path("notifications/unread-count/", UnreadCountView.as_view(), name="api-unread-count"),
    path("notifications/read-all/", MarkAllReadView.as_view(), name="api-notifications-read-all"),
    path("notifications/mark-all-read/", MarkAllReadView.as_view(), name="api-notifications-mark-all-read"),
    path("notifications/<uuid:id>/read/", MarkNotificationReadView.as_view(), name="api-notification-read"),
]
