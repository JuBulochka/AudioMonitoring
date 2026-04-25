"""Dashboard summary API — aggregated stats for the main dashboard."""
from datetime import timedelta

from django.db import models
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """
    GET /api/v1/dashboard/summary/
    Returns key metrics for the operator dashboard.
    """
    from apps.devices.models import Device, DeviceStatus
    from apps.packets.models import AudioPacket, SeverityLevel
    from apps.incidents.models import Incident, IncidentStatus
    from apps.alerts.models import Notification

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    devices_qs = Device.objects.filter(is_active=True)
    total_devices = devices_qs.count()
    online_devices = devices_qs.filter(is_online=True).count()
    offline_devices = total_devices - online_devices

    critical_devices = devices_qs.filter(
        status__in=[DeviceStatus.NEEDS_INSPECTION, DeviceStatus.SITE_VISIT_REQUIRED]
    ).count()

    packets_today = AudioPacket.objects.filter(recorded_at__gte=last_24h).count()
    anomalies_today = AudioPacket.objects.filter(recorded_at__gte=last_24h, has_anomaly=True).count()
    critical_today = AudioPacket.objects.filter(recorded_at__gte=last_24h, severity=SeverityLevel.CRITICAL).count()

    open_incidents = Incident.objects.filter(
        status__in=[IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS]
    ).count()
    critical_incidents = Incident.objects.filter(
        severity="critical",
        status__in=[IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED],
    ).count()

    unread_notifications = Notification.objects.filter(
        user=request.user, is_read=False, is_dismissed=False
    ).count()

    # Top 5 most problematic devices in last 7 days
    top_devices = list(
        AudioPacket.objects
        .filter(has_anomaly=True, recorded_at__gte=last_7d)
        .values("device__id", "device__serial_number", "device__name")
        .annotate(anomaly_count=models.Count("id"))
        .order_by("-anomaly_count")[:5]
    )

    # Hourly packet counts for last 24h chart
    hourly_counts = []
    for i in range(24):
        hour_start = last_24h + timedelta(hours=i)
        hour_end = hour_start + timedelta(hours=1)
        total_h = AudioPacket.objects.filter(recorded_at__gte=hour_start, recorded_at__lt=hour_end).count()
        anomaly_h = AudioPacket.objects.filter(
            recorded_at__gte=hour_start, recorded_at__lt=hour_end, has_anomaly=True
        ).count()
        hourly_counts.append({
            "hour": hour_start.strftime("%H:%M"),
            "total": total_h,
            "anomaly": anomaly_h,
        })

    return Response({
        "devices": {
            "total": total_devices,
            "online": online_devices,
            "offline": offline_devices,
            "critical": critical_devices,
        },
        "packets_24h": {
            "total": packets_today,
            "anomalies": anomalies_today,
            "critical": critical_today,
        },
        "incidents": {
            "open": open_incidents,
            "critical": critical_incidents,
        },
        "unread_notifications": unread_notifications,
        "top_problem_devices": top_devices,
        "hourly_chart": hourly_counts,
    })


from django.urls import path  # noqa: E402

urlpatterns = [
    path("summary/", dashboard_summary, name="api-dashboard-summary"),
]
