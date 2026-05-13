"""
Operator-facing Device API endpoints.
"""
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.devices.models import Device, DeviceStatus, DeviceHeartbeat, OperatorComment
from apps.devices.services import change_device_status, get_devices_for_map
from apps.common.pagination import StandardResultsSetPagination
from apps.common.permissions import CanManageDevices, IsOperatorOrAbove
from apps.users.access import filter_devices_by_user


# ---------------------------------------------------------------------------
# Serializers (inline for brevity — in a full project, move to serializers.py)
# ---------------------------------------------------------------------------
from rest_framework import serializers


class RegionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()


class PumpJackSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    well_number = serializers.CharField()
    name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    site_name = serializers.SerializerMethodField()
    field_name = serializers.SerializerMethodField()
    region_name = serializers.SerializerMethodField()

    def get_site_name(self, obj):
        return obj.site.name

    def get_field_name(self, obj):
        return obj.site.field.name

    def get_region_name(self, obj):
        return obj.site.field.region.name


class DeviceListSerializer(serializers.ModelSerializer):
    region_name = serializers.SerializerMethodField()
    field_name = serializers.SerializerMethodField()
    site_name = serializers.SerializerMethodField()
    well_number = serializers.SerializerMethodField()
    latitude = serializers.FloatField(read_only=True)
    longitude = serializers.FloatField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    assigned_operator_name = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            "id", "serial_number", "name", "status", "status_display",
            "is_online", "is_active",
            "last_seen_at", "last_packet_at", "last_heartbeat_at",
            "firmware_version", "model_version",
            "latitude", "longitude",
            "region_name", "field_name", "site_name", "well_number",
            "assigned_operator_name", "tags",
        ]

    def get_region_name(self, obj): return obj.pump_jack.site.field.region.name
    def get_field_name(self, obj): return obj.pump_jack.site.field.name
    def get_site_name(self, obj): return obj.pump_jack.site.name
    def get_well_number(self, obj): return obj.pump_jack.well_number
    def get_assigned_operator_name(self, obj):
        if obj.assigned_operator:
            return obj.assigned_operator.get_full_name() or obj.assigned_operator.username
        return None


class DeviceDetailSerializer(DeviceListSerializer):
    recent_heartbeat = serializers.SerializerMethodField()

    class Meta(DeviceListSerializer.Meta):
        fields = DeviceListSerializer.Meta.fields + ["notes", "recent_heartbeat", "created_at", "updated_at"]

    def get_recent_heartbeat(self, obj):
        hb = obj.heartbeats.first()
        if not hb:
            return None
        return {
            "received_at": hb.received_at,
            "cpu_temp": hb.cpu_temp,
            "cpu_usage": hb.cpu_usage,
            "disk_usage_pct": hb.disk_usage_pct,
            "memory_usage_pct": hb.memory_usage_pct,
        }


class DeviceStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=DeviceStatus.choices)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class OperatorCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = OperatorComment
        fields = ["id", "text", "author_name", "created_at", "updated_at"]
        read_only_fields = ["id", "author_name", "created_at", "updated_at"]

    def get_author_name(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return "System"


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
class DeviceFilter(filters.FilterSet):
    region = filters.NumberFilter(field_name="pump_jack__site__field__region")
    field = filters.NumberFilter(field_name="pump_jack__site__field")
    status = filters.MultipleChoiceFilter(choices=DeviceStatus.choices)
    is_online = filters.BooleanFilter()
    has_anomaly = filters.BooleanFilter(field_name="audio_packets__has_anomaly")
    search = filters.CharFilter(method="search_filter")

    def search_filter(self, queryset, name, value):
        return queryset.filter(
            models.Q(name__icontains=value)
            | models.Q(serial_number__icontains=value)
            | models.Q(pump_jack__well_number__icontains=value)
        )

    class Meta:
        model = Device
        fields = ["region", "field", "status", "is_online"]


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class DeviceListView(generics.ListAPIView):
    """
    GET /api/v1/devices/
    List all active devices with filtering and pagination.
    """
    serializer_class = DeviceListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_class = DeviceFilter
    search_fields = ["name", "serial_number", "pump_jack__well_number"]
    ordering_fields = ["serial_number", "name", "status", "last_seen_at"]
    ordering = ["-last_seen_at"]

    def get_queryset(self):
        qs = Device.objects.filter(is_active=True).select_related(
            "pump_jack__site__field__region",
            "assigned_operator",
        ).prefetch_related("heartbeats")

        return filter_devices_by_user(qs, self.request.user)


from django.db import models  # noqa: E402 — needed for Q above


class DeviceDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/devices/<id>/
    """
    serializer_class = DeviceDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return filter_devices_by_user(Device.objects.filter(is_active=True), self.request.user).select_related(
            "pump_jack__site__field__region",
            "assigned_operator",
        ).prefetch_related("heartbeats")


class DeviceStatusUpdateView(APIView):
    """
    PATCH /api/v1/devices/<id>/status/
    Update device status with reason.
    """
    permission_classes = [IsAuthenticated, CanManageDevices]

    def patch(self, request, id):
        try:
            device = filter_devices_by_user(Device.objects.all(), request.user).get(id=id, is_active=True)
        except Device.DoesNotExist:
            return Response({"error": "Device not found"}, status=404)

        serializer = DeviceStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        history = change_device_status(
            device=device,
            new_status=serializer.validated_data["status"],
            changed_by=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )

        if history is None:
            return Response({"message": "Status unchanged"})

        return Response({
            "success": True,
            "device_id": str(device.id),
            "new_status": device.status,
            "history_id": history.id,
        })


class DeviceCommentsView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/devices/<id>/comments/
    """
    serializer_class = OperatorCommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        allowed_devices = filter_devices_by_user(Device.objects.all(), self.request.user)
        return OperatorComment.objects.filter(
            device_id=self.kwargs["id"],
            device__in=allowed_devices,
        ).select_related("author")

    def perform_create(self, serializer):
        device = filter_devices_by_user(Device.objects.all(), self.request.user).get(id=self.kwargs["id"], is_active=True)
        serializer.save(device=device, author=self.request.user)


class DeviceRotateKeyView(APIView):
    """
    POST /api/v1/devices/<id>/rotate-key/
    Rotate device auth key (admin only).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        from apps.users.models import UserRole
        if request.user.role != UserRole.ADMIN:
            return Response({"error": "Admin only"}, status=403)

        try:
            device = Device.objects.get(id=id)
        except Device.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        device.rotate_auth_key()

        from apps.common.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.DEVICE_KEY_ROTATED,
            object_type="Device",
            object_id=str(device.id),
            description=f"Auth key rotated for {device.serial_number}",
        )

        return Response({"success": True, "new_auth_key": device.auth_key})


# ---------------------------------------------------------------------------
# URL patterns
# ---------------------------------------------------------------------------
from django.urls import path  # noqa: E402

urlpatterns = [
    path("", DeviceListView.as_view(), name="api-device-list"),
    path("<uuid:id>/", DeviceDetailView.as_view(), name="api-device-detail"),
    path("<uuid:id>/status/", DeviceStatusUpdateView.as_view(), name="api-device-status"),
    path("<uuid:id>/comments/", DeviceCommentsView.as_view(), name="api-device-comments"),
    path("<uuid:id>/rotate-key/", DeviceRotateKeyView.as_view(), name="api-device-rotate-key"),
]
