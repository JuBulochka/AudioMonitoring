from django.contrib import admin
from .models import RemoteAccessSession


@admin.register(RemoteAccessSession)
class RemoteAccessSessionAdmin(admin.ModelAdmin):
    list_display = ["device", "operator", "status", "tunnel_port", "started_at", "ended_at", "duration_seconds"]
    list_filter = ["status"]
    search_fields = ["device__serial_number", "operator__username"]
    readonly_fields = ["id", "created_at"]
