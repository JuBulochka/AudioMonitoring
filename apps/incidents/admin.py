from django.contrib import admin
from .models import Incident, IncidentComment, MaintenanceTask


class IncidentCommentInline(admin.TabularInline):
    model = IncidentComment
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = [
        "title", "device", "incident_type", "severity",
        "status", "assigned_to", "created_at",
    ]
    list_filter = ["severity", "status", "incident_type"]
    search_fields = ["title", "device__serial_number"]
    date_hierarchy = "created_at"
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [IncidentCommentInline]


@admin.register(MaintenanceTask)
class MaintenanceTaskAdmin(admin.ModelAdmin):
    list_display = ["title", "device", "priority", "status", "assigned_to", "scheduled_date"]
    list_filter = ["priority", "status"]
    search_fields = ["title", "device__serial_number"]
