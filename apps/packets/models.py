"""
Packet models — audio data received from devices.

Design decisions:
- AudioPacket is the central time-series table. At 1 packet/hour/device,
  1000 devices × 24h × 90d = 2,160,000 rows — manageable with good indexes.
  For >10k devices, recommend PostgreSQL range partitioning by recorded_at
  (monthly partitions). Partition creation can be scripted as a migration.
- AudioClassScore stores per-class scores as normalized rows for flexible
  querying and charting without JSON traversal.
- DailyDeviceMetrics is a pre-aggregated rollup table updated by Celery
  each night — used for dashboard charts and device health scoring.

Audio file storage:
  Files are stored under MEDIA_ROOT/audio/<device_id>/<date>/<uuid>.wav
  The abstract storage backend (FileSystemStorage or S3Boto3Storage) is
  configured at settings level — code is storage-agnostic.
"""
import os
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


def audio_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or ".wav"
    date_str = instance.recorded_at.strftime("%Y/%m/%d") if instance.recorded_at else "unknown"
    return f"audio/{instance.device_id}/{date_str}/{uuid.uuid4().hex}{ext}"



class AudioClass(models.TextChoices):
    NORMAL = "normal", _("Норма")
    NOISE = "noise", _("Шум")
    GRINDING = "grinding", _("Скрежет")
    SQUEAK = "squeak", _("Скрип")
    KNOCK = "knock", _("Стук")
    WHISTLE = "whistle", _("Свист")
    FOREIGN_SOUNDS = "foreign_sounds", _("Посторонние звуки")
    SPEECH = "speech", _("Разговоры / речь")
    OTHER_ANOMALY = "other_anomaly", _("Иная аномалия")


class PacketStatus(models.TextChoices):
    RECEIVED = "received", _("Получен")
    PROCESSING = "processing", _("Обрабатывается")
    PROCESSED = "processed", _("Обработан")
    ERROR = "error", _("Ошибка обработки")


class SeverityLevel(models.TextChoices):
    INFO = "info", _("Информация")
    WARNING = "warning", _("Предупреждение")
    CRITICAL = "critical", _("Критично")



class AudioPacket(models.Model):
    """
    One packet = one recording session on the edge device.
    Sent approximately every hour.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="audio_packets",
    )
    recorded_at = models.DateTimeField(db_index=True)  # When recording started on device
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    audio_file = models.FileField(
        upload_to=audio_upload_path,
        null=True, blank=True,
        max_length=512,
    )
    audio_file_size_bytes = models.BigIntegerField(null=True, blank=True)
    audio_sample_rate = models.IntegerField(null=True, blank=True)
    audio_channels = models.SmallIntegerField(null=True, blank=True)
    audio_format = models.CharField(max_length=20, blank=True)
    has_anomaly = models.BooleanField(default=False, db_index=True)
    severity = models.CharField(
        max_length=10,
        choices=SeverityLevel.choices,
        default=SeverityLevel.INFO,
        db_index=True,
    )
    dominant_class = models.CharField(
        max_length=20,
        choices=AudioClass.choices,
        default=AudioClass.NORMAL,
        db_index=True,
    )
    dominant_class_score = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    status = models.CharField(
        max_length=15,
        choices=PacketStatus.choices,
        default=PacketStatus.RECEIVED,
    )
    device_cpu_temp = models.FloatField(null=True, blank=True)
    device_cpu_usage = models.FloatField(null=True, blank=True)
    device_memory_usage_pct = models.FloatField(null=True, blank=True)
    device_disk_usage_pct = models.FloatField(null=True, blank=True)
    device_firmware_version = models.CharField(max_length=50, blank=True)
    device_model_version = models.CharField(max_length=50, blank=True)
    raw_analysis = models.JSONField(default=dict)
    operator_status = models.CharField(
        max_length=30,
        choices=[
            ("pending", _("Ожидает проверки")),
            ("reviewed", _("Проверено")),
            ("false_positive", _("Ложное срабатывание")),
            ("escalated", _("Передано")),
        ],
        default="pending",
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reviewed_packets",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    operator_notes = models.TextField(blank=True)

    class Meta:
        db_table = "packets_audio_packet"
        verbose_name = _("Аудиопакет")
        verbose_name_plural = _("Аудиопакеты")
        indexes = [
            models.Index(fields=["device", "recorded_at"]),
            models.Index(fields=["device", "has_anomaly"]),
            models.Index(fields=["device", "severity"]),
            models.Index(fields=["recorded_at", "has_anomaly"]),
            models.Index(fields=["device", "operator_status"]),
        ]
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"Packet({self.device.serial_number}, {self.recorded_at:%Y-%m-%d %H:%M})"

    @property
    def audio_file_url(self):
        if self.audio_file:
            return self.audio_file.url
        return None



class AudioClassScore(models.Model):
    """One row per audio class per packet. Enables flexible per-class queries."""
    packet = models.ForeignKey(
        AudioPacket,
        on_delete=models.CASCADE,
        related_name="class_scores",
    )
    audio_class = models.CharField(max_length=20, choices=AudioClass.choices, db_index=True)
    score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    threshold_exceeded = models.BooleanField(default=False)

    class Meta:
        db_table = "packets_class_score"
        verbose_name = _("Оценка класса аудио")
        verbose_name_plural = _("Оценки классов аудио")
        unique_together = [("packet", "audio_class")]
        indexes = [
            models.Index(fields=["audio_class", "threshold_exceeded"]),
        ]

    def __str__(self):
        return f"{self.audio_class}: {self.score:.3f}"



class DailyDeviceMetrics(models.Model):
    """
    Pre-aggregated daily stats per device.
    Populated nightly by Celery task aggregate_daily_metrics.
    Used for dashboard charts and device health scoring.
    """
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="daily_metrics",
    )
    date = models.DateField(db_index=True)
    total_packets = models.IntegerField(default=0)
    anomaly_packets = models.IntegerField(default=0)
    critical_packets = models.IntegerField(default=0)
    warning_packets = models.IntegerField(default=0)
    class_counts = models.JSONField(default=dict)
    avg_cpu_temp = models.FloatField(null=True, blank=True)
    avg_cpu_usage = models.FloatField(null=True, blank=True)
    avg_memory_usage_pct = models.FloatField(null=True, blank=True)
    avg_disk_usage_pct = models.FloatField(null=True, blank=True)
    online_minutes = models.IntegerField(default=0)
    heartbeat_count = models.IntegerField(default=0)

    class Meta:
        db_table = "packets_daily_metrics"
        verbose_name = _("Дневные метрики устройства")
        verbose_name_plural = _("Дневные метрики устройств")
        unique_together = [("device", "date")]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["device", "date"]),
        ]
        ordering = ["-date"]

    def __str__(self):
        return f"DailyMetrics({self.device.serial_number}, {self.date})"

    @property
    def anomaly_rate(self):
        if self.total_packets > 0:
            return round(self.anomaly_packets / self.total_packets, 4)
        return 0.0
