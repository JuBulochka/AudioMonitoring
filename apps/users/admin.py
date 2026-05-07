from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OperatorProfile


class OperatorProfileInline(admin.StackedInline):
    model = OperatorProfile
    can_delete = False
    extra = 0
    filter_horizontal = ["assigned_fields"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [OperatorProfileInline]
    list_display = ["username", "email", "get_full_name", "role", "is_active", "last_activity"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["username", "email", "first_name", "last_name"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Роль и контакты", {"fields": ("role", "phone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Роль", {"fields": ("role", "email")}),
    )
