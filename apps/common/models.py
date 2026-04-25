"""Common models — AuditLog shared across apps."""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """
    Append-only audit trail for critical actions.
    Written by AuditLogMiddleware and explicit service calls.
    Retained for 1 year (cleaned by weekly Celery task).
    """

    class Action(models.TextChoices):
        LOGIN = "login", _("Вход в систему")
        LOGOUT = "logout", _("Выход из системы")
        LOGIN_FAILED = "login_failed", _("Неудачный вход")
        DEVICE_STATUS_CHANGED = "device_status_changed", _("Смена статуса устройства")
        INCIDENT_CREATED = "incident_created", _("Инцидент создан")
        INCIDENT_STATUS_CHANGED = "incident_status_changed", _("Смена статуса инцидента")
        PACKET_REVIEWED = "packet_reviewed", _("Пакет проверен")
        REMOTE_ACCESS_REQUESTED = "remote_access_requested", _("Запрос удалённого доступа")
        REMOTE_ACCESS_APPROVED = "remote_access_approved", _("Удалённый доступ одобрен")
        REMOTE_ACCESS_REJECTED = "remote_access_rejected", _("Удалённый доступ отклонён")
        REMOTE_SESSION_STARTED = "remote_session_started", _("Сессия удалённого доступа начата")
        REMOTE_SESSION_ENDED = "remote_session_ended", _("Сессия удалённого доступа завершена")
        DEVICE_KEY_ROTATED = "device_key_rotated", _("Ключ устройства ротирован")
        USER_CREATED = "user_created", _("Пользователь создан")
        USER_ROLE_CHANGED = "user_role_changed", _("Роль пользователя изменена")
        EXPORT = "export", _("Экспорт данных")
        ADMIN_ACTION = "admin_action", _("Действие администратора")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=50, choices=Action.choices, db_index=True)
    object_type = models.CharField(max_length=100, blank=True, db_index=True)
    object_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    extra_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "common_audit_log"
        verbose_name = _("Журнал аудита")
        verbose_name_plural = _("Журнал аудита")
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"AuditLog({self.action}, {self.user}, {self.created_at:%Y-%m-%d %H:%M})"
