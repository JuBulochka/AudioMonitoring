"""
Alert / Notification services — create alerts, fan out to users, push via WebSocket.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

from .models import Alert, AlertType, AlertSeverity, Notification

logger = logging.getLogger("apps.alerts")


def _get_target_users(device=None):
    """
    Return users who should receive notifications for a given device.
    - Admins and supervisors: always.
    - Operators: if assigned to the device's region or directly to device.
    """
    from apps.users.models import User, UserRole

    qs = User.objects.filter(is_active=True)

    always_notified = qs.filter(role=UserRole.ADMIN)

    if device:
        # Operators assigned to the field that contains this device
        field = device.pump_jack.site.field if device.pump_jack_id else None
        field_operators = (
            qs.filter(role=UserRole.OPERATOR, profile__assigned_fields=field)
            if field else qs.none()
        )
        assigned_directly = qs.filter(id=device.assigned_operator_id) if device.assigned_operator_id else qs.none()
        return (always_notified | field_operators | assigned_directly).distinct()

    return always_notified


def _dedup_key(alert_type: str, device_id=None, extra: str = "") -> str:
    """Create a deduplication key. Prevents duplicate alerts within a time window."""
    parts = [alert_type]
    if device_id:
        parts.append(str(device_id))
    if extra:
        parts.append(extra)
    return ":".join(parts)


def alert_exists_recently(dedup_key: str, window_minutes: int = 30) -> bool:
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(minutes=window_minutes)
    return Alert.objects.filter(dedup_key=dedup_key, created_at__gte=cutoff).exists()


@transaction.atomic
def create_alert(
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    device=None,
    incident=None,
    payload: dict = None,
    dedup_window_minutes: int = 30,
) -> Alert | None:
    """
    Create an Alert and fan out Notifications to all relevant users.
    Returns None if a duplicate alert was already sent within the window.
    """
    key = _dedup_key(alert_type, device.id if device else None)
    if dedup_window_minutes and alert_exists_recently(key, dedup_window_minutes):
        logger.debug("Alert deduped: %s", key)
        return None

    alert = Alert.objects.create(
        device=device,
        incident=incident,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        payload=payload or {},
        dedup_key=key,
    )

    # Fan out to users
    target_users = _get_target_users(device)
    notifications = [
        Notification(user=user, alert=alert)
        for user in target_users
    ]
    Notification.objects.bulk_create(notifications, ignore_conflicts=True)

    logger.info("Alert created: %s [%s] → %d notifications", title, severity, len(notifications))

    # Push via WebSocket to connected browsers
    _push_ws_alert(alert, target_users)

    return alert


def _push_ws_alert(alert: Alert, users):
    """Push alert to all connected WebSocket clients for target users."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    payload = {
        "type": "alert.new",
        "alert_id": str(alert.id),
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "device_id": str(alert.device_id) if alert.device_id else None,
        "created_at": alert.created_at.isoformat(),
    }

    for user in users:
        group_name = f"user_{user.id}_alerts"
        try:
            async_to_sync(channel_layer.group_send)(group_name, payload)
        except Exception as e:
            logger.warning("WS push failed for user %s: %s", user.id, e)


def create_device_offline_alert(device) -> Alert | None:
    return create_alert(
        alert_type=AlertType.DEVICE_OFFLINE,
        severity=AlertSeverity.CRITICAL,
        title=f"Устройство оффлайн: {device.serial_number}",
        message=(
            f"Устройство {device.name} ({device.serial_number}) "
            f"не выходило на связь более {settings.OFFLINE_THRESHOLD_MINUTES} минут."
        ),
        device=device,
        payload={"last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None},
        dedup_window_minutes=60,
    )


def create_critical_anomaly_alert(device, packet) -> Alert | None:
    return create_alert(
        alert_type=AlertType.CRITICAL_ANOMALY,
        severity=AlertSeverity.CRITICAL,
        title=f"Критическая аномалия: {device.serial_number}",
        message=(
            f"Обнаружена аномалия «{packet.get_dominant_class_display()}» "
            f"(уверенность: {packet.dominant_class_score:.1%}) "
            f"на устройстве {device.serial_number}."
        ),
        device=device,
        payload={
            "packet_id": str(packet.id),
            "dominant_class": packet.dominant_class,
            "score": packet.dominant_class_score,
        },
        dedup_window_minutes=30,
    )


def create_disk_critical_alert(device, disk_pct: float) -> Alert | None:
    return create_alert(
        alert_type=AlertType.DISK_CRITICAL,
        severity=AlertSeverity.WARNING,
        title=f"Диск почти заполнен: {device.serial_number}",
        message=f"Диск устройства {device.serial_number} заполнен на {disk_pct:.0f}%.",
        device=device,
        payload={"disk_usage_pct": disk_pct},
        dedup_window_minutes=120,
    )


def create_high_temp_alert(device, temp: float) -> Alert | None:
    return create_alert(
        alert_type=AlertType.HIGH_TEMPERATURE,
        severity=AlertSeverity.WARNING,
        title=f"Высокая температура: {device.serial_number}",
        message=f"Температура CPU устройства {device.serial_number} достигла {temp:.1f}°C.",
        device=device,
        payload={"cpu_temp": temp},
        dedup_window_minutes=60,
    )
