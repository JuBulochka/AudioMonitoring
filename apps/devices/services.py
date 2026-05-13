"""Сервисный слой устройств: авторизация, статусы, heartbeat и данные для карты."""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.models import AuditLog
from .models import Device, DeviceStatus, DeviceStatusHistory

logger = logging.getLogger("apps.devices")


def authenticate_device(auth_key: str) -> Device | None:
    """Проверяет ключ устройства и переводит найденное устройство в онлайн."""
    try:
        device = Device.objects.select_related("pump_jack__site__field__region").get(
            auth_key=auth_key,
            is_active=True,
        )
        device.mark_online()
        return device
    except Device.DoesNotExist:
        logger.warning("Device authentication failed — key not found or device inactive")
        return None


@transaction.atomic
def change_device_status(
    device: Device,
    new_status: str,
    changed_by=None,
    reason: str = "",
    is_automated: bool = False,
) -> DeviceStatusHistory:
    """Меняет статус устройства и сохраняет запись истории для аудита."""
    if device.status == new_status:
        return None

    history = DeviceStatusHistory.objects.create(
        device=device,
        previous_status=device.status,
        new_status=new_status,
        changed_by=changed_by,
        reason=reason,
        is_automated=is_automated,
    )

    device.status = new_status
    device.save(update_fields=["status", "updated_at"])

    if not is_automated and changed_by:
        AuditLog.objects.create(
            user=changed_by,
            action=AuditLog.Action.DEVICE_STATUS_CHANGED,
            object_type="Device",
            object_id=str(device.id),
            description=f"Status changed to {new_status}. Reason: {reason}",
        )

    logger.info(
        "Device %s status: %s → %s (by %s, automated=%s)",
        device.serial_number,
        history.previous_status,
        new_status,
        changed_by,
        is_automated,
    )
    return history


def update_device_from_heartbeat(device: Device, heartbeat) -> None:
    """Обновляет последние признаки жизни устройства после heartbeat."""
    updates = {
        "last_heartbeat_at": timezone.now(),
        "last_seen_at": timezone.now(),
        "is_online": True,
    }

    if heartbeat.firmware_version and heartbeat.firmware_version != device.firmware_version:
        updates["firmware_version"] = heartbeat.firmware_version

    if heartbeat.model_version and heartbeat.model_version != device.model_version:
        updates["model_version"] = heartbeat.model_version

    Device.objects.filter(pk=device.pk).update(**updates)


def get_devices_for_map(
    user=None,
    region_ids=None,
    status_filter=None,
    online_only=False,
    anomaly_only=False,
    bbox=None,
) -> list[dict]:
    """
    Готовит облегченный список устройств для карты.

    Здесь намеренно используется values(), чтобы не тащить в память полные модели:
    карте нужны только координаты, статус и несколько полей для подписи маркера.
    """
    qs = Device.objects.filter(is_active=True).select_related(
        "pump_jack__site__field__region"
    )

    if user is not None:
        from apps.users.access import filter_devices_by_user
        qs = filter_devices_by_user(qs, user)

    if region_ids:
        qs = qs.filter(pump_jack__site__field__region_id__in=region_ids)
    if status_filter:
        qs = qs.filter(status__in=status_filter)
    if online_only:
        qs = qs.filter(is_online=True)
    if anomaly_only:
        qs = qs.filter(status__in=[DeviceStatus.NEEDS_INSPECTION, DeviceStatus.SITE_VISIT_REQUIRED])
    if bbox:
        sw_lat, sw_lng, ne_lat, ne_lng = bbox
        qs = qs.filter(
            pump_jack__latitude__gte=sw_lat,
            pump_jack__latitude__lte=ne_lat,
            pump_jack__longitude__gte=sw_lng,
            pump_jack__longitude__lte=ne_lng,
        )

    return list(
        qs.values(
            "id",
            "serial_number",
            "name",
            "status",
            "is_online",
            "last_seen_at",
            "pump_jack__latitude",
            "pump_jack__longitude",
            "pump_jack__well_number",
            "pump_jack__site__field__region__name",
        )
    )


def get_offline_threshold():
    """Возвращает границу времени, после которой устройство считается офлайн."""
    return timezone.now() - timedelta(minutes=settings.OFFLINE_THRESHOLD_MINUTES)


def detect_offline_devices():
    """Находит устройства без свежего heartbeat и переводит их в офлайн."""
    threshold = get_offline_threshold()
    newly_offline = []

    candidates = Device.objects.filter(
        is_active=True,
        is_online=True,
    ).filter(
        last_seen_at__lt=threshold,
    )

    for device in candidates:
        device.mark_offline()
        newly_offline.append(device.id)
        logger.warning("Device %s marked offline (last seen: %s)", device.serial_number, device.last_seen_at)

    return newly_offline
