"""
Device models — geographic hierarchy + device management.

Hierarchy: Region → Field → Site → PumpJack → Device

A Device is the Raspberry Pi unit physically attached to a PumpJack.
Each Device authenticates via a pre-shared token (DeviceToken).

Design decisions:
- Soft delete on Device (is_active) so history is preserved.
- DeviceHeartbeat is an append-only log; old entries pruned by Celery.
- DeviceStatusHistory tracks every manual/automated status change.
- SoftwareVersion tracks what code is running on each device.
"""
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _



class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "devices_region"
        verbose_name = _("Регион")
        verbose_name_plural = _("Регионы")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Field(models.Model):
    """Oil field (месторождение)."""
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="fields")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "devices_field"
        verbose_name = _("Месторождение")
        verbose_name_plural = _("Месторождения")
        unique_together = [("region", "name")]

    def __str__(self):
        return f"{self.region.code} / {self.name}"


class Site(models.Model):
    """Production site / cluster (куст скважин)."""
    field = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="sites")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "devices_site"
        verbose_name = _("Куст скважин")
        verbose_name_plural = _("Кусты скважин")

    def __str__(self):
        return f"{self.field.code} / {self.name}"


class PumpJack(models.Model):
    """Physical oil pump jack unit."""
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="pump_jacks")
    well_number = models.CharField(max_length=50)  # Номер скважины
    name = models.CharField(max_length=150)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    installation_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "devices_pump_jack"
        verbose_name = _("Нефтяная качалка")
        verbose_name_plural = _("Нефтяные качалки")
        unique_together = [("site", "well_number")]
        indexes = [
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["site"]),
        ]

    def __str__(self):
        return f"Скв.{self.well_number} / {self.name}"



class DeviceStatus(models.TextChoices):
    NORMAL = "normal", _("Норма")
    NEEDS_INSPECTION = "needs_inspection", _("Требует проверки")
    NEEDS_RECONFIGURATION = "needs_reconfiguration", _("Требует перенастройки")
    SITE_VISIT_REQUIRED = "site_visit_required", _("Требуется выезд")
    IN_PROGRESS = "in_progress", _("В работе")
    RESOLVED = "resolved", _("Устранено")
    FALSE_POSITIVE = "false_positive", _("Ложное срабатывание")
    OFFLINE = "offline", _("Отключено / нет связи")



class Device(models.Model):
    """
    Raspberry Pi unit on a pump jack.

    auth_key is a random 64-char hex token used for device API authentication.
    It is generated on creation and can be rotated by admins.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pump_jack = models.OneToOneField(PumpJack, on_delete=models.PROTECT, related_name="device")
    serial_number = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    auth_key = models.CharField(max_length=128, unique=True, editable=False)
    auth_key_created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=30,
        choices=DeviceStatus.choices,
        default=DeviceStatus.NORMAL,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_online = models.BooleanField(default=False, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_packet_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    model_version = models.CharField(max_length=50, blank=True)
    assigned_operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assigned_devices",
    )
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    tunnel_port = models.IntegerField(
        null=True, blank=True, unique=True,
        help_text=_("Порт обратного SSH-туннеля (30001-30020). Назначается автоматически."),
    )
    vnc_tunnel_port = models.IntegerField(
        null=True, blank=True, unique=True,
        help_text=_("Порт обратного VNC-туннеля (31001-31020). Назначается автоматически."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "devices_device"
        verbose_name = _("Устройство")
        verbose_name_plural = _("Устройства")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["is_online"]),
            models.Index(fields=["last_seen_at"]),
            models.Index(fields=["is_active", "is_online"]),
        ]

    def __str__(self):
        return f"{self.serial_number} / {self.name}"

    def save(self, *args, **kwargs):
        if not self.auth_key:
            self.auth_key = secrets.token_hex(64)
        if self.tunnel_port is None:
            used = set(
                Device.objects.filter(tunnel_port__isnull=False)
                .exclude(pk=self.pk)
                .values_list("tunnel_port", flat=True)
            )
            for port in range(30001, 30021):
                if port not in used:
                    self.tunnel_port = port
                    break
        if self.vnc_tunnel_port is None:
            used_vnc = set(
                Device.objects.filter(vnc_tunnel_port__isnull=False)
                .exclude(pk=self.pk)
                .values_list("vnc_tunnel_port", flat=True)
            )
            for port in range(31001, 31021):
                if port not in used_vnc:
                    self.vnc_tunnel_port = port
                    break
        super().save(*args, **kwargs)

    def rotate_auth_key(self):
        self.auth_key = secrets.token_hex(64)
        self.auth_key_created_at = timezone.now()
        self.save(update_fields=["auth_key", "auth_key_created_at"])

    def mark_online(self):
        self.is_online = True
        self.last_seen_at = timezone.now()
        update_fields = ["is_online", "last_seen_at"]

        if self.status == DeviceStatus.OFFLINE:
            self.status = DeviceStatus.NORMAL
            update_fields.append("status")

        self.save(update_fields=update_fields)

    def mark_offline(self):
        if self.is_online:
            self.is_online = False
            self.save(update_fields=["is_online"])

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])

    @property
    def region(self):
        return self.pump_jack.site.field.region

    @property
    def field(self):
        return self.pump_jack.site.field

    @property
    def site(self):
        return self.pump_jack.site

    @property
    def latitude(self):
        return float(self.pump_jack.latitude)

    @property
    def longitude(self):
        return float(self.pump_jack.longitude)



class DeviceHeartbeat(models.Model):
    """Periodic health ping from device — append-only, pruned by Celery."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="heartbeats")
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    cpu_temp = models.FloatField(null=True, blank=True)
    cpu_usage = models.FloatField(null=True, blank=True)
    memory_total_mb = models.IntegerField(null=True, blank=True)
    memory_used_mb = models.IntegerField(null=True, blank=True)
    disk_total_gb = models.FloatField(null=True, blank=True)
    disk_used_gb = models.FloatField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    model_version = models.CharField(max_length=50, blank=True)
    uptime_seconds = models.BigIntegerField(null=True, blank=True)
    network_ssid = models.CharField(max_length=100, blank=True)
    signal_strength_dbm = models.IntegerField(null=True, blank=True)
    raw_data = models.JSONField(default=dict)

    class Meta:
        db_table = "devices_heartbeat"
        verbose_name = _("Heartbeat")
        verbose_name_plural = _("Heartbeats")
        indexes = [
            models.Index(fields=["device", "received_at"]),
        ]
        ordering = ["-received_at"]

    def __str__(self):
        return f"HB({self.device.serial_number}, {self.received_at:%Y-%m-%d %H:%M})"

    @property
    def disk_usage_pct(self):
        if self.disk_total_gb and self.disk_total_gb > 0:
            return round(self.disk_used_gb / self.disk_total_gb * 100, 1)
        return None

    @property
    def memory_usage_pct(self):
        if self.memory_total_mb and self.memory_total_mb > 0:
            return round(self.memory_used_mb / self.memory_total_mb * 100, 1)
        return None



class DeviceStatusHistory(models.Model):
    """Immutable record of every status change on a device."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="status_history")
    previous_status = models.CharField(max_length=30, choices=DeviceStatus.choices, blank=True)
    new_status = models.CharField(max_length=30, choices=DeviceStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    is_automated = models.BooleanField(default=False)

    class Meta:
        db_table = "devices_status_history"
        verbose_name = _("История статусов устройства")
        verbose_name_plural = _("История статусов устройств")
        indexes = [
            models.Index(fields=["device", "changed_at"]),
        ]
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.device.serial_number}: {self.previous_status} → {self.new_status}"



class SoftwareVersion(models.Model):
    """Tracks software/firmware versions deployed to devices."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="software_versions")
    firmware_version = models.CharField(max_length=50)
    model_version = models.CharField(max_length=50)
    os_version = models.CharField(max_length=100, blank=True)
    python_version = models.CharField(max_length=30, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    raw_info = models.JSONField(default=dict)

    class Meta:
        db_table = "devices_software_version"
        verbose_name = _("Версия ПО")
        verbose_name_plural = _("Версии ПО")
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.device.serial_number} fw:{self.firmware_version} model:{self.model_version}"



class OperatorComment(models.Model):
    """Free-text comment left by an operator on a device."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devices_operator_comment"
        verbose_name = _("Комментарий оператора")
        verbose_name_plural = _("Комментарии операторов")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.device.serial_number}"
