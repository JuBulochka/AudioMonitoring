"""Dashboard web views."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta


@login_required
def dashboard(request):
    from apps.devices.models import Device, DeviceStatus
    from apps.incidents.models import Incident, IncidentStatus
    from apps.alerts.models import Notification

    now = timezone.now()
    from apps.users.access import filter_devices_by_user, filter_incidents_by_user
    devices_qs = filter_devices_by_user(Device.objects.filter(is_active=True), request.user)
    incidents_base = filter_incidents_by_user(Incident.objects.all(), request.user)

    ctx = {
        "total_devices": devices_qs.count(),
        "online_devices": devices_qs.filter(is_online=True).count(),
        "offline_devices": devices_qs.filter(is_online=False).count(),
        "critical_devices": devices_qs.filter(
            status__in=[DeviceStatus.NEEDS_INSPECTION, DeviceStatus.SITE_VISIT_REQUIRED]
        ).count(),
        "open_incidents": incidents_base.filter(
            status__in=[IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS]
        ).count(),
        "recent_incidents": incidents_base.filter(
            created_at__gte=now - timedelta(hours=24)
        ).select_related("device").order_by("-created_at")[:10],
        "recent_notifications": Notification.objects.filter(
            user=request.user, is_dismissed=False
        ).select_related("alert__device").order_by("-created_at")[:5],
    }
    return render(request, "dashboard/dashboard.html", ctx)
