"""
Access control helpers for role-based view filtering.

Usage in views:
    from apps.users.access import admin_required, filter_devices_by_user

    @admin_required
    def device_create(request): ...

    qs = filter_devices_by_user(Device.objects.all(), request.user)
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


# ── Decorators ─────────────────────────────────────────────────────────────────

def admin_required(view_func):
    """Redirect non-admins to dashboard with an error message."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_admin:
            messages.error(request, 'Недостаточно прав. Этот раздел доступен только администраторам.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Queryset filters ───────────────────────────────────────────────────────────

def filter_devices_by_user(qs, user):
    """
    Filter a Device queryset to only devices in user's allowed fields.
    Admin sees all. Operator without assignments sees nothing.
    """
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return qs   # admin — all devices
    if not field_ids:
        return qs.none()
    return qs.filter(pump_jack__site__field_id__in=field_ids)


def filter_regions_by_user(qs, user):
    """Filter Region queryset to regions that contain user's assigned fields."""
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return qs
    if not field_ids:
        return qs.none()
    return qs.filter(fields__id__in=field_ids).distinct()


def user_can_access_device(user, device) -> bool:
    """Return whether user may access a concrete Device instance."""
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return True
    if not field_ids or not device.pump_jack_id:
        return False
    return device.pump_jack.site.field_id in field_ids


def filter_incidents_by_user(qs, user):
    """Filter Incident queryset by user's allowed fields."""
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return qs
    if not field_ids:
        return qs.none()
    return qs.filter(device__pump_jack__site__field_id__in=field_ids)


def filter_packets_by_user(qs, user):
    """Filter AudioPacket queryset by user's allowed fields."""
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return qs
    if not field_ids:
        return qs.none()
    return qs.filter(device__pump_jack__site__field_id__in=field_ids)
