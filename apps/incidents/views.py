"""Incident web views."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404

from .models import Incident, IncidentStatus, IncidentSeverity, IncidentType, MaintenanceTask


@login_required
def incident_list(request):
    from apps.users.access import filter_incidents_by_user
    qs = filter_incidents_by_user(
        Incident.objects.select_related("device", "assigned_to"),
        request.user,
    ).order_by("-created_at")

    status_f = request.GET.get("status")
    severity_f = request.GET.get("severity")
    type_f = request.GET.get("type")
    search = request.GET.get("q", "").strip()

    if status_f:
        qs = qs.filter(status=status_f)
    if severity_f:
        qs = qs.filter(severity=severity_f)
    if type_f:
        qs = qs.filter(incident_type=type_f)
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(title__icontains=search) | Q(device__serial_number__icontains=search))

    paginator = Paginator(qs, 30)
    page_number = request.GET.get("page", 1)
    incidents_page = paginator.get_page(page_number)

    ctx = {
        "incidents": incidents_page,
        "paginator": paginator,
        "statuses": IncidentStatus.choices,
        "severities": IncidentSeverity.choices,
        "types": IncidentType.choices,
        "filter_status": status_f or "",
        "filter_severity": severity_f or "",
        "filter_type": type_f or "",
        "filter_q": search,
    }
    return render(request, "incidents/incident_list.html", ctx)


@login_required
def incident_detail(request, incident_id):
    incident = get_object_or_404(
        Incident.objects.select_related("device", "assigned_to", "trigger_packet", "resolved_by"),
        id=incident_id,
    )
    comments = incident.comments.select_related("author").order_by("created_at")
    tasks = incident.maintenance_tasks.select_related("assigned_to").order_by("-created_at")

    ctx = {
        "incident": incident,
        "comments": comments,
        "tasks": tasks,
        "statuses": IncidentStatus.choices,
    }
    return render(request, "incidents/incident_detail.html", ctx)


@login_required
def maintenance_list(request):
    from apps.devices.models import Device

    qs = MaintenanceTask.objects.select_related(
        "device", "assigned_to", "incident", "created_by"
    ).order_by("-created_at")

    status_f = request.GET.get("status", "")
    device_f = request.GET.get("device", "")
    if status_f:
        qs = qs.filter(status=status_f)
    if device_f:
        qs = qs.filter(device_id=device_f)

    devices = Device.objects.filter(is_active=True).order_by("serial_number")

    ctx = {
        "tasks": qs[:300],
        "statuses": MaintenanceTask.TaskStatus.choices,
        "priorities": MaintenanceTask.Priority.choices,
        "devices": devices,
        "filter_status": status_f,
        "filter_device": device_f,
        "counts": {
            "planned": MaintenanceTask.objects.filter(status="planned").count(),
            "in_progress": MaintenanceTask.objects.filter(status="in_progress").count(),
            "done": MaintenanceTask.objects.filter(status="done").count(),
        },
    }
    return render(request, "incidents/maintenance_list.html", ctx)
