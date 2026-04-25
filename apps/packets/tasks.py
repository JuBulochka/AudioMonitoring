"""Packet Celery tasks."""
import logging
from datetime import timedelta, date

from celery import shared_task
from django.db import models
from django.utils import timezone

logger = logging.getLogger("apps.packets")


@shared_task(name="apps.packets.tasks.purge_old_packets")
def purge_old_packets():
    """Delete audio packets and files older than AUDIO_RETENTION_DAYS."""
    from apps.packets.services import purge_old_packets as _purge
    count = _purge()
    return count


@shared_task(name="apps.packets.tasks.aggregate_daily_metrics")
def aggregate_daily_metrics(target_date: str = None):
    """
    Build or refresh DailyDeviceMetrics for target_date (default: yesterday).
    Called nightly at 00:05 UTC.
    """
    from apps.packets.models import AudioPacket, DailyDeviceMetrics
    from apps.devices.models import Device, DeviceHeartbeat

    if target_date:
        from datetime import date as date_cls
        d = date_cls.fromisoformat(target_date)
    else:
        d = (timezone.now() - timedelta(days=1)).date()

    day_start = timezone.datetime.combine(d, timezone.datetime.min.time()).replace(tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    # Get all devices that had packets or heartbeats that day
    device_ids = set(
        AudioPacket.objects.filter(recorded_at__gte=day_start, recorded_at__lt=day_end)
        .values_list("device_id", flat=True)
    )

    created = updated = 0
    for device_id in device_ids:
        qs = AudioPacket.objects.filter(
            device_id=device_id,
            recorded_at__gte=day_start,
            recorded_at__lt=day_end,
        )

        total = qs.count()
        anomaly_count = qs.filter(has_anomaly=True).count()
        critical_count = qs.filter(severity="critical").count()
        warning_count = qs.filter(severity="warning").count()

        # Per-class counts
        class_counts = {}
        from apps.packets.models import AudioClassScore
        for row in (
            AudioClassScore.objects
            .filter(packet__device_id=device_id, packet__recorded_at__gte=day_start, packet__recorded_at__lt=day_end, threshold_exceeded=True)
            .values("audio_class")
            .annotate(cnt=models.Count("id"))
        ):
            class_counts[row["audio_class"]] = row["cnt"]

        # Averages from packets
        aggs = qs.aggregate(
            avg_cpu_temp=models.Avg("device_cpu_temp"),
            avg_cpu_usage=models.Avg("device_cpu_usage"),
            avg_mem=models.Avg("device_memory_usage_pct"),
            avg_disk=models.Avg("device_disk_usage_pct"),
        )

        hb_count = DeviceHeartbeat.objects.filter(
            device_id=device_id,
            received_at__gte=day_start,
            received_at__lt=day_end,
        ).count()

        obj, was_created = DailyDeviceMetrics.objects.update_or_create(
            device_id=device_id,
            date=d,
            defaults={
                "total_packets": total,
                "anomaly_packets": anomaly_count,
                "critical_packets": critical_count,
                "warning_packets": warning_count,
                "class_counts": class_counts,
                "avg_cpu_temp": aggs["avg_cpu_temp"],
                "avg_cpu_usage": aggs["avg_cpu_usage"],
                "avg_memory_usage_pct": aggs["avg_mem"],
                "avg_disk_usage_pct": aggs["avg_disk"],
                "heartbeat_count": hb_count,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    logger.info("Aggregated daily metrics for %s: %d created, %d updated", d, created, updated)
    return {"date": str(d), "created": created, "updated": updated}
