"""Incident REST API."""
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.incidents.models import Incident, IncidentComment, IncidentStatus, MaintenanceTask
from apps.common.pagination import StandardResultsSetPagination
from apps.common.permissions import IsOperatorOrAbove


# ── Nested reference serializers ───────────────────────────────────────────────

class DeviceRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    serial_number = serializers.CharField()
    name = serializers.CharField()


class UserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


# ── Incident serializer ────────────────────────────────────────────────────────

class IncidentSerializer(serializers.ModelSerializer):
    device = DeviceRefSerializer(read_only=True)
    assigned_to = UserRefSerializer(read_only=True, allow_null=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    incident_type_display = serializers.CharField(source="get_incident_type_display", read_only=True)
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            "id", "device",
            "incident_type", "incident_type_display",
            "severity", "severity_display",
            "status", "status_display",
            "title", "description",
            "trigger_class", "trigger_score",
            "assigned_to",
            "resolution_notes", "resolved_at",
            "created_at", "updated_at",
            "comment_count",
        ]

    def get_comment_count(self, obj):
        return obj.comments.count()


class IncidentCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = IncidentComment
        fields = ["id", "text", "is_system", "author_name", "created_at"]
        read_only_fields = ["id", "is_system", "author_name", "created_at"]

    def get_author_name(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return "System"


class IncidentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=IncidentStatus.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    resolution_notes = serializers.CharField(required=False, allow_blank=True, default="")


class IncidentFilter(filters.FilterSet):
    device = filters.UUIDFilter(field_name="device__id")
    severity = filters.MultipleChoiceFilter(choices=[
        ("info", "Info"), ("warning", "Warning"), ("critical", "Critical")
    ])
    status = filters.MultipleChoiceFilter(choices=IncidentStatus.choices)
    incident_type = filters.CharFilter()
    from_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    to_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    assigned_to_me = filters.BooleanFilter(method="filter_assigned_to_me")

    def filter_assigned_to_me(self, queryset, name, value):
        if value:
            return queryset.filter(assigned_to=self.request.user)
        return queryset

    class Meta:
        model = Incident
        fields = ["device", "severity", "status", "incident_type"]


class IncidentListView(generics.ListAPIView):
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_class = IncidentFilter
    ordering_fields = ["created_at", "severity", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Incident.objects.select_related(
            "device", "assigned_to", "resolved_by"
        ).prefetch_related("comments")


class IncidentDetailView(generics.RetrieveAPIView):
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return Incident.objects.select_related("device", "assigned_to", "trigger_packet")


class IncidentStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAbove]

    def patch(self, request, id):
        try:
            incident = Incident.objects.get(id=id)
        except Incident.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        ser = IncidentStatusUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        old_status = incident.status
        incident.status = data["status"]

        if data.get("assigned_to_id"):
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                incident.assigned_to = User.objects.get(id=data["assigned_to_id"])
            except User.DoesNotExist:
                pass

        if data["status"] in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
            incident.resolved_by = request.user
            incident.resolved_at = timezone.now()
            if data.get("resolution_notes"):
                incident.resolution_notes = data["resolution_notes"]

        incident.save()

        # Auto-add a system comment
        comment_text = data.get("comment") or f"Статус изменён: {old_status} → {data['status']}"
        IncidentComment.objects.create(
            incident=incident,
            author=request.user,
            text=comment_text,
            is_system=False,
        )

        return Response({"success": True, "new_status": incident.status})


class IncidentCommentsView(generics.ListCreateAPIView):
    serializer_class = IncidentCommentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # comments are always a short list

    def get_queryset(self):
        return IncidentComment.objects.filter(incident_id=self.kwargs["id"]).select_related("author")

    def perform_create(self, serializer):
        incident = Incident.objects.get(id=self.kwargs["id"])
        serializer.save(incident=incident, author=self.request.user)


class MaintenanceTaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    device_serial = serializers.CharField(source="device.serial_number", read_only=True)

    class Meta:
        model = MaintenanceTask
        fields = [
            "id", "device", "device_serial", "incident",
            "title", "description",
            "priority", "priority_display",
            "status", "status_display",
            "assigned_to", "assigned_to_name",
            "scheduled_date", "completed_at", "result_notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "completed_at"]

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return None


class MaintenanceTaskCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(choices=MaintenanceTask.Priority.choices, default="medium")
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    scheduled_date = serializers.DateTimeField(required=False, allow_null=True)
    # For standalone creation (not from incident)
    device_id = serializers.UUIDField(required=False, allow_null=True)


class IncidentTasksView(APIView):
    """GET/POST /api/v1/incidents/<id>/tasks/"""
    permission_classes = [IsAuthenticated, IsOperatorOrAbove]

    def get(self, request, id):
        tasks = MaintenanceTask.objects.filter(incident_id=id).select_related("assigned_to", "device")
        return Response(MaintenanceTaskSerializer(tasks, many=True).data)

    def post(self, request, id):
        try:
            incident = Incident.objects.select_related("device").get(id=id)
        except Incident.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        ser = MaintenanceTaskCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        assigned_to = None
        if data.get("assigned_to_id"):
            from django.contrib.auth import get_user_model
            try:
                assigned_to = get_user_model().objects.get(id=data["assigned_to_id"])
            except Exception:
                pass

        task = MaintenanceTask.objects.create(
            device=incident.device,
            incident=incident,
            title=data["title"],
            description=data.get("description", ""),
            priority=data["priority"],
            assigned_to=assigned_to,
            scheduled_date=data.get("scheduled_date"),
            created_by=request.user,
        )
        return Response(MaintenanceTaskSerializer(task).data, status=status.HTTP_201_CREATED)


class MaintenanceTaskListCreateView(APIView):
    """GET/POST /api/v1/tasks/  — standalone (not tied to specific incident)"""
    permission_classes = [IsAuthenticated, IsOperatorOrAbove]

    def get(self, request):
        qs = MaintenanceTask.objects.select_related("device", "assigned_to", "incident")
        status_f = request.query_params.get("status")
        device_f = request.query_params.get("device")
        if status_f:
            qs = qs.filter(status=status_f)
        if device_f:
            qs = qs.filter(device_id=device_f)
        return Response(MaintenanceTaskSerializer(qs[:200], many=True).data)

    def post(self, request):
        ser = MaintenanceTaskCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        device_id = data.get("device_id")
        if not device_id:
            return Response({"error": "device_id is required"}, status=400)

        from apps.devices.models import Device
        try:
            device = Device.objects.get(id=device_id, is_active=True)
        except Device.DoesNotExist:
            return Response({"error": "Device not found"}, status=404)

        assigned_to = None
        if data.get("assigned_to_id"):
            from django.contrib.auth import get_user_model
            try:
                assigned_to = get_user_model().objects.get(id=data["assigned_to_id"])
            except Exception:
                pass

        task = MaintenanceTask.objects.create(
            device=device,
            title=data["title"],
            description=data.get("description", ""),
            priority=data["priority"],
            assigned_to=assigned_to,
            scheduled_date=data.get("scheduled_date"),
            created_by=request.user,
        )
        return Response(MaintenanceTaskSerializer(task).data, status=status.HTTP_201_CREATED)


class MaintenanceTaskStatusView(APIView):
    """PATCH /api/v1/tasks/<id>/status/"""
    permission_classes = [IsAuthenticated, IsOperatorOrAbove]

    def patch(self, request, id):
        try:
            task = MaintenanceTask.objects.get(id=id)
        except MaintenanceTask.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        new_status = request.data.get("status")
        if new_status not in dict(MaintenanceTask.TaskStatus.choices):
            return Response({"error": "Invalid status"}, status=400)

        task.status = new_status
        if new_status == MaintenanceTask.TaskStatus.DONE:
            task.completed_at = timezone.now()
            result_notes = request.data.get("result_notes", "")
            if result_notes:
                task.result_notes = result_notes
        task.save()
        return Response(MaintenanceTaskSerializer(task).data)


from django.urls import path  # noqa: E402

urlpatterns = [
    path("", IncidentListView.as_view(), name="api-incident-list"),
    path("<uuid:id>/", IncidentDetailView.as_view(), name="api-incident-detail"),
    path("<uuid:id>/status/", IncidentStatusUpdateView.as_view(), name="api-incident-status"),
    path("<uuid:id>/comments/", IncidentCommentsView.as_view(), name="api-incident-comments"),
    path("<uuid:id>/tasks/", IncidentTasksView.as_view(), name="api-incident-tasks"),
]
