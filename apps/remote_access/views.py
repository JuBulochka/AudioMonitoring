"""Страницы удаленного доступа: проверка пароля, терминал и команды."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages

from .models import RemoteAccessSession, COMMAND_CATALOG

_TOKEN_KEY = "ra_token_{device_id}"


def _consume_token(request, device_id):
    """Забирает одноразовый токен доступа из сессии."""
    key = _TOKEN_KEY.format(device_id=device_id)
    token = request.session.pop(key, None)
    return bool(token)


def _issue_token(request, device_id):
    """Выдает одноразовый токен для перехода к терминалу или командам."""
    import uuid
    key = _TOKEN_KEY.format(device_id=device_id)
    request.session[key] = str(uuid.uuid4())


@login_required
def verify_access(request, device_id):
    """
    Проверяет пароль перед удаленным доступом.

    Пароль может принадлежать администратору или любому активному оператору,
    закрепленному за месторождением выбранного устройства.
    """
    from apps.devices.models import Device
    from apps.users.access import filter_devices_by_user
    from apps.users.models import User, UserRole

    device = get_object_or_404(
        filter_devices_by_user(
            Device.objects.select_related("pump_jack__site__field"),
            request.user,
        ),
        id=device_id, is_active=True,
    )

    next_url = request.GET.get("next") or request.POST.get("next", "")
    if not next_url.startswith("/"):
        next_url = ""


    error = ""

    if request.method == "POST":
        password = request.POST.get("password", "")

        field = device.pump_jack.site.field if device.pump_jack_id else None

        # Проверяем не только текущего пользователя, а весь допустимый круг людей:
        # админы плюс операторы нужного месторождения.
        candidates = User.objects.filter(is_active=True, role=UserRole.ADMIN)
        if field:
            field_ops = User.objects.filter(
                is_active=True,
                role=UserRole.OPERATOR,
                profile__assigned_fields=field,
            )
            candidates = (candidates | field_ops).distinct()

        verified = False
        for candidate in candidates:
            if not candidate.is_frozen and candidate.check_password(password):
                verified = True
                break

        if verified:
            _issue_token(request, device_id)
            from apps.common.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.REMOTE_ACCESS_REQUESTED,
                object_type="Device",
                object_id=str(device.id),
                description=(
                    f"Пройдена верификация доступа к устройству {device.serial_number} "
                    f"пользователем {request.user.username}"
                ),
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            return redirect(next_url or "remote-access-log")
        else:
            error = "Неверный пароль. Введите пароль любого оператора, закреплённого за этим месторождением."

    field = device.pump_jack.site.field if device.pump_jack_id else None
    field_name = field.name if field else "—"

    return render(request, "remote_access/verify_access.html", {
        "device": device,
        "field_name": field_name,
        "next_url": next_url,
        "error": error,
    })


def _require_token(request, device_id, next_url):
    """Не пускает в терминал/команды без свежей проверки пароля."""
    if not _consume_token(request, device_id):
        from django.urls import reverse
        url = reverse("remote-verify", kwargs={"device_id": device_id})
        return redirect(f"{url}?next={next_url}")
    return None


@login_required
def remote_access_log(request):
    """Показывает устройства и последние сессии удаленного доступа."""
    from apps.devices.models import Device
    from apps.users.access import filter_devices_by_user

    devices = (
        filter_devices_by_user(
            Device.objects.filter(is_active=True),
            request.user,
        )
        .select_related("pump_jack__site__field__region", "assigned_operator")
        .order_by("-is_online", "pump_jack__site__field__region__name", "name")
    )

    ses_qs = (
        RemoteAccessSession.objects
        .filter(device__in=devices)
        .select_related("device", "operator")
        .order_by("-created_at")
    )
    if not request.user.is_admin:
        ses_qs = ses_qs.filter(operator=request.user)

    last_session = {}
    for s in ses_qs[:300]:
        did = str(s.device_id)
        if did not in last_session:
            last_session[did] = s

    device_rows = []
    for d in devices:
        device_rows.append({
            "device": d,
            "last_ses": last_session.get(str(d.id)),
        })

    ctx = {
        "device_rows": device_rows,
        "sessions": ses_qs[:50],
    }
    return render(request, "remote_access/remote_access.html", ctx)


@login_required
def terminal(request, device_id):
    """Открывает веб-терминал только после проверки доступа к устройству."""
    from apps.devices.models import Device
    from apps.users.access import filter_devices_by_user
    from apps.common.models import AuditLog
    from django.urls import reverse

    device = get_object_or_404(
        filter_devices_by_user(
            Device.objects.select_related("pump_jack__site__field__region"),
            request.user,
        ),
        id=device_id, is_active=True,
    )

    next_url = reverse("remote-terminal", kwargs={"device_id": device_id})
    redir = _require_token(request, device_id, next_url)
    if redir:
        return redir

    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.REMOTE_ACCESS_REQUESTED,
        object_type="Device",
        object_id=str(device.id),
        description=f"Открыт веб-терминал пользователем {request.user.username}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    return render(request, "remote_access/terminal.html", {"device": device})


@login_required
def commands(request, device_id):
    """Показывает страницу команд для конкретного устройства."""
    from apps.devices.models import Device
    from apps.users.access import filter_devices_by_user
    from apps.common.models import AuditLog
    from django.urls import reverse

    device = get_object_or_404(
        filter_devices_by_user(
            Device.objects.select_related("pump_jack__site__field__region"),
            request.user,
        ),
        id=device_id, is_active=True,
    )

    next_url = reverse("remote-commands", kwargs={"device_id": device_id})
    redir = _require_token(request, device_id, next_url)
    if redir:
        return redir

    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.REMOTE_ACCESS_REQUESTED,
        object_type="Device",
        object_id=str(device.id),
        description=f"Открыта страница команд для устройства {device.serial_number}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    categories = {}
    for key, meta in COMMAND_CATALOG.items():
        cat = meta["category"]
        categories.setdefault(cat, []).append({"key": key, **meta})

    return render(request, "remote_access/commands.html", {
        "device":     device,
        "categories": categories,
    })
