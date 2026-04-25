from django.contrib import admin
from .models import Alert, Notification


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["title", "alert_type", "severity", "device", "created_at"]
    list_filter = ["severity", "alert_type"]
    search_fields = ["title", "device__serial_number"]
    date_hierarchy = "created_at"
    readonly_fields = ["id", "created_at", "dedup_key"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "alert", "is_read", "created_at"]
    list_filter = ["is_read"]
    search_fields = ["user__username"]
