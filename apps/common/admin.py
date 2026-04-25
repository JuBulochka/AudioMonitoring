from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "user", "object_type", "object_id", "ip_address", "created_at"]
    list_filter = ["action", "object_type"]
    search_fields = ["user__username", "object_id", "description"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
