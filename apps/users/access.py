"""Общие правила доступа для админов и операторов."""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect



def admin_required(view_func):
    """Ограничивает страницу только администраторами."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_admin:
            messages.error(request, 'Недостаточно прав. Этот раздел доступен только администраторам.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper



def filter_devices_by_user(qs, user):
    """Возвращает устройства только из месторождений, доступных пользователю."""
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return qs
    if not field_ids:
        return qs.none()
    return qs.filter(pump_jack__site__field_id__in=field_ids)


def filter_regions_by_user(qs, user):
    """Оставляет регионы, в которых есть закрепленные за оператором месторождения."""
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return qs
    if not field_ids:
        return qs.none()
    return qs.filter(fields__id__in=field_ids).distinct()


def user_can_access_device(user, device) -> bool:
    """Проверяет доступ к конкретному устройству без отдельного запроса списка."""
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return True
    if not field_ids or not device.pump_jack_id:
        return False
    return device.pump_jack.site.field_id in field_ids


def filter_incidents_by_user(qs, user):
    """Фильтрует инциденты по тем же месторождениям, что и устройства."""
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return qs
    if not field_ids:
        return qs.none()
    return qs.filter(device__pump_jack__site__field_id__in=field_ids)


def filter_packets_by_user(qs, user):
    """Ограничивает историю аудиопакетов доступными месторождениями."""
    field_ids = user.get_allowed_field_ids()
    if field_ids is None:
        return qs
    if not field_ids:
        return qs.none()
    return qs.filter(device__pump_jack__site__field_id__in=field_ids)
