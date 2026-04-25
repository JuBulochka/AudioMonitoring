"""
Device domain services — business logic, decoupled from views.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.models import AuditLog
from .models import Device, DeviceStatus, DeviceStatusHistory

logger = logging.getLogger("apps.devices")


def authenticate_device(auth_key: str) -> Device | None:
    """
    Validate device auth key and return Device or None.
    Used by device API authentication.
    """
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
    """
    Change device status and create an immutable history record.
    Emits an audit log entry for manual changes.
    """
    if device.status == new_status:
        return None  # No-op

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
    """
    Update device's live fields after receiving a heartbeat.
    Also updates the firmware/model version if changed.
    """
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
    region_ids=None,
    status_filter=None,
    online_only=False,
    anomaly_only=False,
    bbox=None,
) -> list[dict]:
    """
    Return lightweight device data for map rendering.
    Filtered by viewport bbox (sw_lat, sw_lng, ne_lat, ne_lng) when provided.
    Returns only fields needed for map markers — avoids loading full objects.
    """
    qs = Device.objects.filter(is_active=True).select_related(
        "pump_jack__site__field__region"
    )

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
    return timezone.now() - timedelta(minutes=settings.OFFLINE_THRESHOLD_MINUTES)


def detect_offline_devices():
    """
    Called by Celery task every 5 minutes.
    Marks devices offline if no heartbeat within threshold.
    Returns list of newly-offline device IDs.
    """
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
