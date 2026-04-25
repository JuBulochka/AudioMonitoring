"""
Remote Access models.

RemoteAccessSession — audit record for every web terminal SSH session.
DeviceCommand       — operator-dispatched command sent to a Pi device.
"""
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# ---------------------------------------------------------------------------
# Command catalog
# Commands are defined HERE (server-side) and also mirrored on the Pi.
# The Pi receives only the command_key; it looks up the shell script locally.
# ---------------------------------------------------------------------------

COMMAND_CATALOG = {
    # 1. Просмотр логов и статуса
    "view_logs": {
        "label": "Логи и статус сервиса",
        "description": "systemctl status + последние 100 строк журнала",
        "category": "monitoring",
        "timeout": 15,
        "requires_confirm": False,
        "icon": "bi-journal-text",
    },
    # 2. Выключение аудио
    "disable_audio": {
        "label": "Отключить отправку аудио",
        "description": "Устройство будет присылать только аналитику без аудиофайла",
        "category": "config",
        "timeout": 25,
        "requires_confirm": True,
        "icon": "bi-mic-mute",
    },
    # 3. Ручной старт записи прямо сейчас
    "record_now": {
        "label": "Записать прямо сейчас",
        "description": "Немедленно запустить цикл записи без ожидания таймера",
        "category": "control",
        "timeout": 30,
        "requires_confirm": False,
        "icon": "bi-record-circle",
    },
    # 4. Диагностика звука (USB-камера)
    "audio_diagnostics": {
        "label": "Диагностика звука (USB)",
        "description": "Найти USB-устройство захвата, проверить тестовую запись 3 сек.",
        "category": "diagnostics",
        "timeout": 35,
        "requires_confirm": False,
        "icon": "bi-usb-symbol",
    },
}


class RemoteAccessStatus(models.TextChoices):
    ACTIVE = "active", _("Активно")
    COMPLETED = "completed", _("Завершено")
    EXPIRED = "expired", _("Истекло")


class RemoteAccessSession(models.Model):
    """
    Audit record for a web-terminal SSH session.
    Created when the browser opens the terminal; ended when WebSocket closes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="remote_sessions",
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="remote_sessions",
    )
    status = models.CharField(
        max_length=20,
        choices=RemoteAccessStatus.choices,
        default=RemoteAccessStatus.ACTIVE,
        db_index=True,
    )
    # Filled in when SSH tunnel is confirmed active
    tunnel_host = models.CharField(max_length=255, blank=True)
    tunnel_port = models.IntegerField(null=True, blank=True)
    # Session lifecycle
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    # Audit
    operator_ip = models.GenericIPAddressField(null=True, blank=True)
    device_reported_ip = models.GenericIPAddressField(null=True, blank=True)
    session_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "remote_access_session"
        verbose_name = _("Сессия удалённого доступа")
        verbose_name_plural = _("Сессии удалённого доступа")
        indexes = [
            models.Index(fields=["device", "created_at"]),
            models.Index(fields=["operator", "created_at"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Session({self.device.serial_number}, {self.operator.username}, {self.status})"

    @property
    def duration_seconds(self):
        if self.started_at and self.ended_at:
            return int((self.ended_at - self.started_at).total_seconds())
        return None

    def start(self, tunnel_host="", tunnel_port=None, device_ip=None):
        self.status = RemoteAccessStatus.ACTIVE
        self.started_at = timezone.now()
        if tunnel_host:
            self.tunnel_host = tunnel_host
        if tunnel_port:
            self.tunnel_port = tunnel_port
        if device_ip:
            self.device_reported_ip = device_ip
        self.save(update_fields=["status", "started_at", "tunnel_host", "tunnel_port", "device_reported_ip"])

    def end(self, notes=""):
        self.status = RemoteAccessStatus.COMPLETED
        self.ended_at = timezone.now()
        if notes:
            self.session_notes = notes
        self.save(update_fields=["status", "ended_at", "session_notes"])


# ---------------------------------------------------------------------------
# Device Command
# ---------------------------------------------------------------------------

class CommandStatus(models.TextChoices):
    PENDING   = "pending",   _("Ожидает выполнения")
    RUNNING   = "running",   _("Выполняется")
    COMPLETED = "completed", _("Выполнено")
    FAILED    = "failed",    _("Ошибка")
    TIMEOUT   = "timeout",   _("Таймаут")
    CANCELLED = "cancelled", _("Отменено")


class DeviceCommand(models.Model):
    """
    A pre-defined command dispatched by an operator to a specific Pi device.

    Lifecycle:
      operator creates → status=pending
      Pi polls and picks it up → status=running
      Pi finishes → status=completed/failed/timeout
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="commands",
        verbose_name=_("Устройство"),
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_commands",
        verbose_name=_("Кто отправил"),
    )

    # Command identification
    command_key = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name=_("Ключ команды"),
        help_text=_("Slug из каталога команд, напр. system_info"),
    )
    params = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("Параметры"),
    )

    # Status lifecycle
    status = models.CharField(
        max_length=20,
        choices=CommandStatus.choices,
        default=CommandStatus.PENDING,
        db_index=True,
        verbose_name=_("Статус"),
    )

    # Result (filled in by Pi)
    output = models.TextField(blank=True, verbose_name=_("Вывод"))
    exit_code = models.IntegerField(null=True, blank=True, verbose_name=_("Код выхода"))
    error_message = models.TextField(blank=True, verbose_name=_("Сообщение об ошибке"))

    # Timing
    created_at    = models.DateTimeField(auto_now_add=True, verbose_name=_("Создано"))
    picked_up_at  = models.DateTimeField(null=True, blank=True, verbose_name=_("Получено устройством"))
    completed_at  = models.DateTimeField(null=True, blank=True, verbose_name=_("Выполнено"))

    class Meta:
        db_table = "remote_access_device_command"
        verbose_name = _("Команда устройству")
        verbose_name_plural = _("Команды устройствам")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["device", "status"]),
            models.Index(fields=["device", "created_at"]),
        ]

    def __str__(self):
        return f"{self.command_key} → {self.device.serial_number} [{self.status}]"

    @property
    def catalog_entry(self):
        return COMMAND_CATALOG.get(self.command_key, {})

    @property
    def label(self):
        return self.catalog_entry.get("label", self.command_key)

    @property
    def duration_seconds(self):
        if self.picked_up_at and self.completed_at:
            return round((self.completed_at - self.picked_up_at).total_seconds(), 1)
        return None

    def mark_running(self):
        self.status = CommandStatus.RUNNING
        self.picked_up_at = timezone.now()
        self.save(update_fields=["status", "picked_up_at"])

    def mark_completed(self, output: str, exit_code: int = 0):
        self.status = CommandStatus.COMPLETED if exit_code == 0 else CommandStatus.FAILED
        self.output = output
        self.exit_code = exit_code
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "output", "exit_code", "completed_at"])

    def mark_failed(self, error: str):
        self.status = CommandStatus.FAILED
        self.error_message = error
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "error_message", "completed_at"])

    def mark_timeout(self):
        self.status = CommandStatus.TIMEOUT
        self.error_message = "Command timed out on device"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "error_message", "completed_at"])
