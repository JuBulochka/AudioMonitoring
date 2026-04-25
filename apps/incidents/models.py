"""
Incident models — tracks detected anomalies requiring operator attention.

An Incident is created automatically when:
- A packet arrives with severity=critical
- Device goes offline for longer than threshold
- Repeated anomalies detected in rolling window (by Celery)

Operators can:
- Add comments
- Change status
- Assign to themselves or colleagues
- Link maintenance tasks
"""
from apps.packets.models import AudioClass  # noqa: E402
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class IncidentType(models.TextChoices):
    AUDIO_ANOMALY = "audio_anomaly", _("Аудиоаномалия")
    DEVICE_OFFLINE = "device_offline", _("Потеря связи")
    HARDWARE_ISSUE = "hardware_issue", _("Проблема оборудования")
    REPEATED_FAULT = "repeated_fault", _("Повторяющийся сбой")
    DISK_FULL = "disk_full", _("Диск заполнен")
    HIGH_TEMPERATURE = "high_temperature", _("Высокая температура")
    MANUAL = "manual", _("Создан вручную")


class IncidentStatus(models.TextChoices):
    OPEN = "open", _("Открыт")
    ACKNOWLEDGED = "acknowledged", _("Принят")
    IN_PROGRESS = "in_progress", _("В работе")
    RESOLVED = "resolved", _("Устранён")
    FALSE_POSITIVE = "false_positive", _("Ложное срабатывание")
    CLOSED = "closed", _("Закрыт")


class IncidentSeverity(models.TextChoices):
    INFO = "info", _("Информация")
    WARNING = "warning", _("Предупреждение")
    CRITICAL = "critical", _("Критично")


class Incident(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="incidents",
    )
    incident_type = models.CharField(
        max_length=30,
        choices=IncidentType.choices,
        db_index=True,
    )
    severity = models.CharField(
        max_length=10,
        choices=IncidentSeverity.choices,
        default=IncidentSeverity.WARNING,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=IncidentStatus.choices,
        default=IncidentStatus.OPEN,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # Link to the triggering packet (if applicable)
    trigger_packet = models.ForeignKey(
        "packets.AudioPacket",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="incidents",
    )
    # Detected audio class that triggered
    trigger_class = models.CharField(
        max_length=20,
        choices=[("", "")] + [(c.value, c.label) for c in AudioClass],
        blank=True,
    )
    trigger_score = models.FloatField(null=True, blank=True)
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assigned_incidents",
    )
    # Resolution
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="resolved_incidents",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    # Auto-close: system may auto-close after device returns to normal
    auto_close = models.BooleanField(default=False)
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Duplicate detection
    is_duplicate = models.BooleanField(default=False)
    parent_incident = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="duplicate_incidents",
    )

    class Meta:
        db_table = "incidents_incident"
        verbose_name = _("Инцидент")
        verbose_name_plural = _("Инциденты")
        indexes = [
            models.Index(fields=["device", "created_at"]),
            models.Index(fields=["device", "status"]),
            models.Index(fields=["severity", "status"]),
            models.Index(fields=["incident_type", "status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title} ({self.device.serial_number})"

    @property
    def is_open(self):
        return self.status in (IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS)


class IncidentComment(models.Model):
    """Operator comment / activity log on an incident."""
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    is_system = models.BooleanField(default=False)  # auto-generated system message
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "incidents_comment"
        verbose_name = _("Комментарий к инциденту")
        verbose_name_plural = _("Комментарии к инцидентам")
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.incident_id}"


class MaintenanceTask(models.Model):
    """Scheduled or unplanned maintenance task linked to a device or incident."""

    class Priority(models.TextChoices):
        LOW = "low", _("Низкий")
        MEDIUM = "medium", _("Средний")
        HIGH = "high", _("Высокий")
        URGENT = "urgent", _("Срочный")

    class TaskStatus(models.TextChoices):
        PLANNED = "planned", _("Запланировано")
        IN_PROGRESS = "in_progress", _("Выполняется")
        DONE = "done", _("Выполнено")
        CANCELLED = "cancelled", _("Отменено")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="maintenance_tasks",
    )
    incident = models.ForeignKey(
        Incident,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="maintenance_tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=TaskStatus.choices, default=TaskStatus.PLANNED)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    scheduled_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "incidents_maintenance_task"
        verbose_name = _("Задача обслуживания")
        verbose_name_plural = _("Задачи обслуживания")
        indexes = [
            models.Index(fields=["device", "status"]),
            models.Index(fields=["scheduled_date"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.device.serial_number})"
