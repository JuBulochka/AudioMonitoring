"""
Packet domain services — ingest, validate, classify, trigger incidents.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AudioPacket, AudioClassScore, SeverityLevel, AudioClass

logger = logging.getLogger("apps.packets")

# Thresholds for anomaly → severity mapping
CRITICAL_CLASSES = {AudioClass.GRINDING, AudioClass.KNOCK, AudioClass.WHISTLE}
WARNING_CLASSES = {AudioClass.SQUEAK, AudioClass.FOREIGN_SOUNDS, AudioClass.OTHER_ANOMALY}

CRITICAL_SCORE_THRESHOLD = 0.65
WARNING_SCORE_THRESHOLD = 0.45


def compute_severity(class_scores: dict[str, float]) -> tuple[str, str, float]:
    """
    Given a dict {class_name: score}, determine:
    - severity level (info/warning/critical)
    - dominant class
    - dominant score

    Returns (severity, dominant_class, dominant_score)
    """
    if not class_scores:
        return SeverityLevel.INFO, AudioClass.NORMAL, 0.0

    dominant_class = max(class_scores, key=class_scores.get)
    dominant_score = class_scores[dominant_class]

    # Critical: any critical-class exceeds threshold
    for cls in CRITICAL_CLASSES:
        if class_scores.get(cls, 0) >= CRITICAL_SCORE_THRESHOLD:
            return SeverityLevel.CRITICAL, cls, class_scores[cls]

    # Warning: any warning-class or high normal deviation
    for cls in WARNING_CLASSES:
        if class_scores.get(cls, 0) >= WARNING_SCORE_THRESHOLD:
            return SeverityLevel.WARNING, cls, class_scores[cls]

    # Speech/noise with high confidence = warning
    if class_scores.get(AudioClass.SPEECH, 0) >= WARNING_SCORE_THRESHOLD:
        return SeverityLevel.WARNING, AudioClass.SPEECH, class_scores[AudioClass.SPEECH]

    if class_scores.get(AudioClass.NOISE, 0) >= WARNING_SCORE_THRESHOLD:
        return SeverityLevel.WARNING, AudioClass.NOISE, class_scores[AudioClass.NOISE]

    # Normal
    if dominant_class == AudioClass.NORMAL:
        return SeverityLevel.INFO, AudioClass.NORMAL, dominant_score

    return SeverityLevel.INFO, dominant_class, dominant_score


@transaction.atomic
def ingest_packet(device, data: dict, audio_file=None) -> AudioPacket:
    """
    Create AudioPacket and AudioClassScore rows from device submission.

    data dict structure (mirrors device JSON payload):
    {
        "recorded_at": "2024-01-15T10:00:00Z",
        "duration_seconds": 30.0,
        "analysis": {
            "normal": 0.05,
            "noise": 0.10,
            "grinding": 0.75,
            ...
        },
        "device_state": {
            "cpu_temp": 52.3,
            "cpu_usage": 18.5,
            "memory_usage_pct": 45.2,
            "disk_usage_pct": 23.1,
            "firmware_version": "1.2.3",
            "model_version": "0.9.1"
        },
        "audio_meta": {
            "sample_rate": 44100,
            "channels": 1,
            "format": "wav",
            "file_size_bytes": 1234567
        }
    }
    """
    from django.utils.dateparse import parse_datetime

    class_scores = data.get("analysis", {})
    severity, dominant_class, dominant_score = compute_severity(class_scores)
    has_anomaly = dominant_class != AudioClass.NORMAL or severity != SeverityLevel.INFO

    device_state = data.get("device_state", {})
    audio_meta = data.get("audio_meta", {})

    recorded_at = data.get("recorded_at")
    if isinstance(recorded_at, str):
        recorded_at = parse_datetime(recorded_at) or timezone.now()

    packet = AudioPacket.objects.create(
        device=device,
        recorded_at=recorded_at,
        duration_seconds=data.get("duration_seconds"),
        audio_file=audio_file,
        audio_file_size_bytes=audio_meta.get("file_size_bytes"),
        audio_sample_rate=audio_meta.get("sample_rate"),
        audio_channels=audio_meta.get("channels"),
        audio_format=audio_meta.get("format", "wav"),
        has_anomaly=has_anomaly,
        severity=severity,
        dominant_class=dominant_class,
        dominant_class_score=dominant_score,
        status="processed",
        device_cpu_temp=device_state.get("cpu_temp"),
        device_cpu_usage=device_state.get("cpu_usage"),
        device_memory_usage_pct=device_state.get("memory_usage_pct"),
        device_disk_usage_pct=device_state.get("disk_usage_pct"),
        device_firmware_version=device_state.get("firmware_version", ""),
        device_model_version=device_state.get("model_version", ""),
        raw_analysis=data,
    )

    # Bulk-create class scores
    score_objects = [
        AudioClassScore(
            packet=packet,
            audio_class=cls,
            score=score,
            threshold_exceeded=(
                (cls in CRITICAL_CLASSES and score >= CRITICAL_SCORE_THRESHOLD)
                or (cls in WARNING_CLASSES and score >= WARNING_SCORE_THRESHOLD)
                or (cls == AudioClass.SPEECH and score >= WARNING_SCORE_THRESHOLD)
            ),
        )
        for cls, score in class_scores.items()
        if cls in AudioClass.values
    ]
    AudioClassScore.objects.bulk_create(score_objects, ignore_conflicts=True)

    # Update device.last_packet_at
    device.last_packet_at = packet.recorded_at
    device.is_online = True
    device.last_seen_at = timezone.now()
    device.save(update_fields=["last_packet_at", "is_online", "last_seen_at", "updated_at"])

    logger.info(
        "Packet ingested: device=%s severity=%s class=%s score=%.3f",
        device.serial_number, severity, dominant_class, dominant_score,
    )

    # Trigger incident creation asynchronously
    if has_anomaly:
        from apps.incidents.tasks import process_anomalous_packet
        process_anomalous_packet.delay(str(packet.id))

    return packet


def get_packet_history(device_id, days=90, page=1, page_size=50, severity=None, has_anomaly=None):
    """Paginated packet history for a device."""
    from_date = timezone.now() - timedelta(days=days)
    qs = AudioPacket.objects.filter(
        device_id=device_id,
        recorded_at__gte=from_date,
    ).select_related("device")

    if severity:
        qs = qs.filter(severity=severity)
    if has_anomaly is not None:
        qs = qs.filter(has_anomaly=has_anomaly)

    total = qs.count()
    offset = (page - 1) * page_size
    packets = qs[offset: offset + page_size]
    return packets, total


def purge_old_packets():
    """Delete packets and audio files older than AUDIO_RETENTION_DAYS."""
    cutoff = timezone.now() - timedelta(days=settings.AUDIO_RETENTION_DAYS)
    old_packets = AudioPacket.objects.filter(recorded_at__lt=cutoff)
    count = old_packets.count()
    # django-cleanup handles file deletion on model delete
    old_packets.delete()
    logger.info("Purged %d old audio packets (cutoff: %s)", count, cutoff.date())
    return count
