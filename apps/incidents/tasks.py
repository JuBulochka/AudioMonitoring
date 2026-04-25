"""Incident Celery tasks."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("apps.incidents")


@shared_task(name="apps.incidents.tasks.process_anomalous_packet")
def process_anomalous_packet(packet_id: str):
    """
    Called after an anomalous packet is ingested.
    Creates an Incident if severity is warning/critical and no open incident exists.
    """
    from apps.packets.models import AudioPacket, SeverityLevel
    from apps.incidents.models import Incident, IncidentType, IncidentStatus, IncidentSeverity
    from apps.alerts.services import create_critical_anomaly_alert

    try:
        packet = AudioPacket.objects.select_related("device").get(id=packet_id)
    except AudioPacket.DoesNotExist:
        logger.warning("process_anomalous_packet: packet %s not found", packet_id)
        return

    if packet.severity == SeverityLevel.INFO:
        return

    device = packet.device
    incident_severity = (
        IncidentSeverity.CRITICAL if packet.severity == SeverityLevel.CRITICAL
        else IncidentSeverity.WARNING
    )

    # Check for existing open incident of same type to avoid duplicates
    existing = Incident.objects.filter(
        device=device,
        incident_type=IncidentType.AUDIO_ANOMALY,
        status__in=[IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS],
        trigger_class=packet.dominant_class,
        created_at__gte=timezone.now() - timedelta(hours=4),
    ).first()

    if existing:
        # Link packet to existing incident via comment
        from apps.incidents.models import IncidentComment
        IncidentComment.objects.create(
            incident=existing,
            text=(
                f"Повторная аномалия: {packet.get_dominant_class_display()} "
                f"({packet.dominant_class_score:.1%}), пакет {packet.id}"
            ),
            is_system=True,
        )
        logger.info("Linked packet %s to existing incident %s", packet_id, existing.id)
        return

    incident = Incident.objects.create(
        device=device,
        incident_type=IncidentType.AUDIO_ANOMALY,
        severity=incident_severity,
        status=IncidentStatus.OPEN,
        title=f"Аномалия «{packet.get_dominant_class_display()}» на {device.serial_number}",
        description=(
            f"Обнаружена аудиоаномалия класса «{packet.get_dominant_class_display()}» "
            f"с уверенностью {packet.dominant_class_score:.1%}. "
            f"Запись: {packet.recorded_at.strftime('%Y-%m-%d %H:%M UTC')}."
        ),
        trigger_packet=packet,
        trigger_class=packet.dominant_class,
        trigger_score=packet.dominant_class_score,
    )

    if packet.severity == SeverityLevel.CRITICAL:
        create_critical_anomaly_alert(device, packet)

    logger.info(
        "Incident created: %s [%s] for device %s",
        incident.id, incident_severity, device.serial_number,
    )
    return str(incident.id)


@shared_task(name="apps.incidents.tasks.detect_frequent_anomalies")
def detect_frequent_anomalies():
    """
    Hourly: detect devices with ≥5 anomalous packets in last 24h.
    Create REPEATED_FAULT incident if not already open.
    """
    from apps.packets.models import AudioPacket
    from apps.incidents.models import Incident, IncidentType, IncidentStatus, IncidentSeverity
    from apps.alerts.services import create_alert
    from apps.alerts.models import AlertType, AlertSeverity

    cutoff = timezone.now() - timedelta(hours=24)
    from django.db import models as dj_models

    problem_devices = (
        AudioPacket.objects
        .filter(has_anomaly=True, recorded_at__gte=cutoff)
        .values("device")
        .annotate(cnt=dj_models.Count("id"))
        .filter(cnt__gte=5)
    )

    for row in problem_devices:
        device_id = row["device"]
        cnt = row["cnt"]

        existing = Incident.objects.filter(
            device_id=device_id,
            incident_type=IncidentType.REPEATED_FAULT,
            status__in=[IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED],
            created_at__gte=timezone.now() - timedelta(hours=12),
        ).exists()

        if not existing:
            from apps.devices.models import Device
            try:
                device = Device.objects.get(id=device_id)
            except Device.DoesNotExist:
                continue

            Incident.objects.create(
                device=device,
                incident_type=IncidentType.REPEATED_FAULT,
                severity=IncidentSeverity.WARNING,
                status=IncidentStatus.OPEN,
                title=f"Частые аномалии: {device.serial_number} ({cnt} за 24ч)",
                description=f"За последние 24 часа зафиксировано {cnt} аномальных пакетов.",
            )

            create_alert(
                alert_type=AlertType.REPEATED_ANOMALY,
                severity=AlertSeverity.WARNING,
                title=f"Частые аномалии: {device.serial_number}",
                message=f"{cnt} аномальных пакетов за 24 часа.",
                device=device,
                dedup_window_minutes=180,
            )

    logger.info("Frequent anomaly detection: checked %d devices", len(problem_devices))
