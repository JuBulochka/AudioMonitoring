"""Фоновые задачи анализа и агрегации аудиопакетов."""
import logging
from datetime import timedelta, date

import requests
from celery import shared_task
from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger("apps.packets")


@shared_task(
    name="apps.packets.tasks.analyze_audio_packet",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def analyze_audio_packet(self, packet_id: str):
    """
    Отправляет аудиофайл в ML-сервис и обновляет пакет результатами анализа.

    При временной недоступности ML-сервиса задача повторяется автоматически.
    """
    from apps.packets.models import AudioPacket, AudioClassScore, PacketStatus
    from apps.packets.services import compute_severity

    try:
        packet = AudioPacket.objects.get(id=packet_id)
    except AudioPacket.DoesNotExist:
        logger.warning("analyze_audio_packet: packet %s not found", packet_id)
        return

    if not packet.audio_file:
        logger.info("analyze_audio_packet: packet %s has no audio file, skipping", packet_id)
        packet.status = PacketStatus.PROCESSED
        packet.save(update_fields=["status"])
        return

    file_path = f"/app/media/{packet.audio_file.name}"
    ml_url    = getattr(settings, "ML_SERVICE_URL", "http://ml-service:8001")
    timeout   = getattr(settings, "ML_SERVICE_TIMEOUT", 60)

    try:
        resp = requests.post(
            f"{ml_url}/analyze",
            json={"file_path": file_path},
            timeout=timeout,
        )
        resp.raise_for_status()
        result = resp.json()

    except requests.exceptions.ConnectionError as exc:
        logger.warning("ML service unavailable, retrying... (%s)", exc)
        raise self.retry(exc=exc)

    except requests.exceptions.RequestException as exc:
        logger.error("ML service error for packet %s: %s", packet_id, exc)
        packet.status = PacketStatus.ERROR
        packet.save(update_fields=["status"])
        return

    class_scores   = result.get("class_scores", {})
    severity, dominant_class, dominant_score = compute_severity(class_scores)
    is_anomaly = result.get("is_anomaly", False) or dominant_class != "normal"

    packet.has_anomaly          = is_anomaly
    packet.severity             = severity
    packet.dominant_class       = dominant_class
    packet.dominant_class_score = dominant_score
    packet.status               = PacketStatus.PROCESSED
    packet.raw_analysis         = {
        **packet.raw_analysis,
        "ml_result": {
            "anomaly_pct":   result.get("anomaly_pct"),
            "raw_score":     result.get("raw_score"),
            "yamnet_groups": result.get("yamnet_groups", {}),
            "yamnet_top5":   result.get("yamnet_top5", []),
        },
    }
    packet.save(update_fields=[
        "has_anomaly", "severity", "dominant_class",
        "dominant_class_score", "status", "raw_analysis",
    ])

    from apps.packets.services import CRITICAL_CLASSES, WARNING_CLASSES
    from apps.packets.models import AudioClass

    CRITICAL_THR = 0.65
    WARNING_THR  = 0.45

    score_objs = []
    for cls, score in class_scores.items():
        if cls not in AudioClass.values:
            continue
        exceeded = (
            (cls in CRITICAL_CLASSES and score >= CRITICAL_THR)
            or (cls in WARNING_CLASSES and score >= WARNING_THR)
        )
        score_objs.append(AudioClassScore(
            packet=packet,
            audio_class=cls,
            score=score,
            threshold_exceeded=exceeded,
        ))

    AudioClassScore.objects.filter(packet=packet).delete()
    AudioClassScore.objects.bulk_create(score_objs, ignore_conflicts=True)

    logger.info(
        "ML analysis done: packet=%s anomaly=%s severity=%s class=%s score=%.3f",
        packet_id, is_anomaly, severity, dominant_class, dominant_score,
    )

    if is_anomaly:
        try:
            from apps.incidents.tasks import process_anomalous_packet
            process_anomalous_packet.delay(str(packet.id))
        except Exception as exc:
            logger.warning("Could not trigger incident task: %s", exc)


@shared_task(name="apps.packets.tasks.purge_old_packets")
def purge_old_packets():
    """Удаляет аудиопакеты старше настроенного срока хранения."""
    from apps.packets.services import purge_old_packets as _purge
    count = _purge()
    return count


@shared_task(name="apps.packets.tasks.aggregate_daily_metrics")
def aggregate_daily_metrics(target_date: str = None):
    """Пересчитывает дневные агрегаты по устройствам для отчетов и дашборда."""
    from apps.packets.models import AudioPacket, DailyDeviceMetrics
    from apps.devices.models import Device, DeviceHeartbeat

    if target_date:
        from datetime import date as date_cls
        d = date_cls.fromisoformat(target_date)
    else:
        d = (timezone.now() - timedelta(days=1)).date()

    day_start = timezone.datetime.combine(d, timezone.datetime.min.time()).replace(tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

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

        class_counts = {}
        from apps.packets.models import AudioClassScore
        for row in (
            AudioClassScore.objects
            .filter(packet__device_id=device_id, packet__recorded_at__gte=day_start, packet__recorded_at__lt=day_end, threshold_exceeded=True)
            .values("audio_class")
            .annotate(cnt=models.Count("id"))
        ):
            class_counts[row["audio_class"]] = row["cnt"]

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
