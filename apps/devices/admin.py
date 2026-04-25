from django.contrib import admin
from .models import (
    Region, Field, Site, PumpJack, Device,
    DeviceHeartbeat, DeviceStatusHistory, SoftwareVersion, OperatorComment,
)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ["name", "code"]
    search_fields = ["name", "code"]


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "region"]
    list_filter = ["region"]
    search_fields = ["name", "code"]


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "field"]
    list_filter = ["field__region"]
    search_fields = ["name", "code"]


@admin.register(PumpJack)
class PumpJackAdmin(admin.ModelAdmin):
    list_display = ["well_number", "name", "site", "is_active"]
    list_filter = ["site__field__region", "is_active"]
    search_fields = ["well_number", "name"]


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = [
        "serial_number", "name", "status", "is_online", "is_active",
        "tunnel_port", "last_seen_at", "firmware_version", "pump_jack",
    ]
    list_filter = ["status", "is_online", "is_active"]
    search_fields = ["serial_number", "name"]
    readonly_fields = [
        "id", "auth_key", "auth_key_created_at",
        "tunnel_port", "created_at", "updated_at",
    ]
    fieldsets = (
        (None, {"fields": ("id", "serial_number", "name", "pump_jack", "assigned_operator")}),
        ("Auth", {"fields": ("auth_key", "auth_key_created_at"), "classes": ("collapse",)}),
        ("Remote Access", {"fields": ("tunnel_port",), "description":
            "Порт обратного SSH-туннеля — назначается автоматически. "
            "Оператор подключается: ssh pi@&lt;server&gt; -p &lt;tunnel_port&gt;"}),
        ("Status", {"fields": ("status", "is_active", "is_online", "last_seen_at",
                               "last_heartbeat_at", "last_packet_at")}),
        ("Software", {"fields": ("firmware_version", "model_version")}),
        ("Meta", {"fields": ("tags", "notes", "created_at", "updated_at"), "classes": ("collapse",)}),
    )
    actions = ["rotate_keys"]

    def rotate_keys(self, request, queryset):
        for device in queryset:
            device.rotate_auth_key()
        self.message_user(request, f"Ключи ротированы для {queryset.count()} устройств.")
    rotate_keys.short_description = "Ротировать auth keys"


@admin.register(DeviceHeartbeat)
class DeviceHeartbeatAdmin(admin.ModelAdmin):
    list_display = ["device", "received_at", "cpu_temp", "cpu_usage", "disk_usage_pct"]
    list_filter = ["device"]
    date_hierarchy = "received_at"
    readonly_fields = ["received_at"]


@admin.register(DeviceStatusHistory)
class DeviceStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ["device", "previous_status", "new_status", "changed_by", "changed_at", "is_automated"]
    list_filter = ["new_status", "is_automated"]
    date_hierarchy = "changed_at"
    readonly_fields = ["changed_at"]


@admin.register(OperatorComment)
class OperatorCommentAdmin(admin.ModelAdmin):
    list_display = ["device", "author", "text", "created_at"]
    list_filter = ["device"]
    search_fields = ["text"]
