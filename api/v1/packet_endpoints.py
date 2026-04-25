"""Packet REST API."""
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters import rest_framework as filters

from apps.packets.models import AudioPacket, AudioClassScore, SeverityLevel
from apps.common.pagination import StandardResultsSetPagination


class AudioClassScoreSerializer(serializers.ModelSerializer):
    audio_class_display = serializers.CharField(source="get_audio_class_display", read_only=True)

    class Meta:
        model = AudioClassScore
        fields = ["audio_class", "audio_class_display", "score", "threshold_exceeded"]


class AudioPacketSerializer(serializers.ModelSerializer):
    device_serial = serializers.CharField(source="device.serial_number", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    dominant_class_display = serializers.CharField(source="get_dominant_class_display", read_only=True)
    class_scores = AudioClassScoreSerializer(many=True, read_only=True)
    audio_file_url = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AudioPacket
        fields = [
            "id", "device", "device_serial",
            "recorded_at", "received_at", "duration_seconds",
            "audio_file_url", "audio_format", "audio_sample_rate", "audio_channels",
            "has_anomaly", "severity", "severity_display",
            "dominant_class", "dominant_class_display", "dominant_class_score",
            "status", "operator_status",
            "device_cpu_temp", "device_cpu_usage", "device_memory_usage_pct", "device_disk_usage_pct",
            "device_firmware_version", "device_model_version",
            "class_scores",
            "reviewed_by_name", "reviewed_at", "operator_notes",
        ]

    def get_audio_file_url(self, obj):
        if obj.audio_file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.audio_file.url)
        return None

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


class PacketReviewSerializer(serializers.Serializer):
    operator_status = serializers.ChoiceField(choices=[
        ("reviewed", "Проверено"),
        ("false_positive", "Ложное срабатывание"),
        ("escalated", "Передано"),
    ])
    operator_notes = serializers.CharField(required=False, allow_blank=True, default="")


class PacketFilter(filters.FilterSet):
    device = filters.UUIDFilter(field_name="device__id")
    severity = filters.MultipleChoiceFilter(choices=SeverityLevel.choices)
    has_anomaly = filters.BooleanFilter()
    from_date = filters.DateTimeFilter(field_name="recorded_at", lookup_expr="gte")
    to_date = filters.DateTimeFilter(field_name="recorded_at", lookup_expr="lte")
    dominant_class = filters.CharFilter()
    operator_status = filters.CharFilter()

    class Meta:
        model = AudioPacket
        fields = ["device", "severity", "has_anomaly", "dominant_class", "operator_status"]


class PacketListView(generics.ListAPIView):
    """
    GET /api/v1/packets/?device=<uuid>&severity=critical&has_anomaly=true
    """
    serializer_class = AudioPacketSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_class = PacketFilter
    ordering_fields = ["recorded_at", "severity", "dominant_class_score"]
    ordering = ["-recorded_at"]

    def get_queryset(self):
        return AudioPacket.objects.select_related("device", "reviewed_by").prefetch_related("class_scores")


class PacketDetailView(generics.RetrieveAPIView):
    """GET /api/v1/packets/<id>/"""
    serializer_class = AudioPacketSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return AudioPacket.objects.select_related("device", "reviewed_by").prefetch_related("class_scores")


class PacketReviewView(APIView):
    """PATCH /api/v1/packets/<id>/review/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        from django.utils import timezone
        try:
            packet = AudioPacket.objects.get(id=id)
        except AudioPacket.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        serializer = PacketReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        packet.operator_status = serializer.validated_data["operator_status"]
        packet.operator_notes = serializer.validated_data.get("operator_notes", "")
        packet.reviewed_by = request.user
        packet.reviewed_at = timezone.now()
        packet.save(update_fields=["operator_status", "operator_notes", "reviewed_by", "reviewed_at"])

        return Response({"success": True, "operator_status": packet.operator_status})


from django.urls import path  # noqa: E402

urlpatterns = [
    path("", PacketListView.as_view(), name="api-packet-list"),
    path("<uuid:id>/", PacketDetailView.as_view(), name="api-packet-detail"),
    path("<uuid:id>/review/", PacketReviewView.as_view(), name="api-packet-review"),
]
