"""Фоновые задачи по состоянию устройств."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("apps.devices")


@shared_task(name="apps.devices.tasks.check_offline_devices")
def check_offline_devices():
    """Периодически переводит устройства без heartbeat в офлайн и создает тревоги."""
    from apps.devices.services import detect_offline_devices
    from apps.alerts.services import create_device_offline_alert
    from apps.devices.models import Device

    newly_offline_ids = detect_offline_devices()

    for device_id in newly_offline_ids:
        try:
            device = Device.objects.get(id=device_id)
            create_device_offline_alert(device)
            from apps.devices.models import DeviceStatus
            from apps.devices.services import change_device_status
            if device.status == DeviceStatus.NORMAL:
                change_device_status(
                    device=device,
                    new_status=DeviceStatus.OFFLINE,
                    reason="Автоматически: потеря связи",
                    is_automated=True,
                )
        except Exception as e:
            logger.exception("Error processing offline device %s: %s", device_id, e)

    logger.info("Offline check complete: %d devices newly offline", len(newly_offline_ids))
    return len(newly_offline_ids)


@shared_task(name="apps.devices.tasks.device_health_sweep")
def device_health_sweep():
    """Проверяет последние heartbeat на перегрев и заполненный диск."""
    from apps.devices.models import Device, DeviceHeartbeat
    from apps.alerts.services import create_disk_critical_alert, create_high_temp_alert

    DISK_WARN = 85.0
    TEMP_WARN = 75.0

    for hb in DeviceHeartbeat.objects.filter(
        received_at__gte=timezone.now() - timedelta(hours=2)
    ).select_related("device").order_by("device", "-received_at").distinct("device"):
        try:
            if hb.disk_usage_pct and hb.disk_usage_pct >= DISK_WARN:
                create_disk_critical_alert(hb.device, hb.disk_usage_pct)
            if hb.cpu_temp and hb.cpu_temp >= TEMP_WARN:
                create_high_temp_alert(hb.device, hb.cpu_temp)
        except Exception as e:
            logger.exception("Health sweep error for device %s: %s", hb.device_id, e)

    logger.info("Device health sweep complete")


@shared_task(name="apps.devices.tasks.purge_old_heartbeats")
def purge_old_heartbeats():
    """Удаляет старые heartbeat-записи, оставляя только актуальную диагностику."""
    from apps.devices.models import DeviceHeartbeat
    cutoff = timezone.now() - timedelta(days=7)
    count, _ = DeviceHeartbeat.objects.filter(received_at__lt=cutoff).delete()
    logger.info("Purged %d old heartbeat records", count)
    return count
