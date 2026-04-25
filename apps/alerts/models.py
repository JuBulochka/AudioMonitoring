"""
Alert and Notification models.

Alert  — a platform-level event (e.g., device offline, critical anomaly).
         One Alert can trigger many Notifications (one per target user).
Notification — per-user inbox entry derived from an Alert.

This separation allows:
- Bulk sending to all operators in a region.
- Individual read/acknowledged tracking per user.
- WebSocket push to connected browsers via Django Channels.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AlertType(models.TextChoices):
    CRITICAL_ANOMALY = "critical_anomaly", _("Критическая аномалия")
    DEVICE_OFFLINE = "device_offline", _("Устройство оффлайн")
    DEVICE_RECOVERED = "device_recovered", _("Устройство восстановило связь")
    DISK_CRITICAL = "disk_critical", _("Критическое заполнение диска")
    HIGH_TEMPERATURE = "high_temperature", _("Высокая температура CPU")
    MEMORY_CRITICAL = "memory_critical", _("Критическое заполнение памяти")
    REPEATED_ANOMALY = "repeated_anomaly", _("Повторяющиеся аномалии")
    INCIDENT_CREATED = "incident_created", _("Создан инцидент")
    INCIDENT_ESCALATED = "incident_escalated", _("Инцидент эскалирован")
    REMOTE_ACCESS_STARTED = "remote_access_started", _("Начат удалённый доступ")
    SYSTEM = "system", _("Системное")


class AlertSeverity(models.TextChoices):
    INFO = "info", _("Информация")
    WARNING = "warning", _("Предупреждение")
    CRITICAL = "critical", _("Критично")


class Alert(models.Model):
    """Platform-level event. Triggers Notifications to relevant users."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="alerts",
        null=True, blank=True,
    )
    incident = models.ForeignKey(
        "incidents.Incident",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="alerts",
    )
    alert_type = models.CharField(max_length=30, choices=AlertType.choices, db_index=True)
    severity = models.CharField(max_length=10, choices=AlertSeverity.choices, db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    payload = models.JSONField(default=dict)  # extra context for frontend rendering
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Dedup: prevent duplicate alerts within time window
    dedup_key = models.CharField(max_length=128, blank=True, db_index=True)

    class Meta:
        db_table = "alerts_alert"
        verbose_name = _("Оповещение")
        verbose_name_plural = _("Оповещения")
        indexes = [
            models.Index(fields=["device", "created_at"]),
            models.Index(fields=["alert_type", "created_at"]),
            models.Index(fields=["severity", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.severity}] {self.title}"


class Notification(models.Model):
    """Per-user inbox entry. One Alert → many Notifications."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="notifications")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    is_dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "alerts_notification"
        verbose_name = _("Уведомление")
        verbose_name_plural = _("Уведомления")
        unique_together = [("user", "alert")]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notif({self.user.username}, {self.alert.title[:40]}, read={self.is_read})"

    def mark_read(self):
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])
