"""Remote access web views."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages

from .models import RemoteAccessSession, COMMAND_CATALOG

# Session flag key — per device, expires after 1 hour
_SESSION_KEY = "ra_verified_{device_id}"
_SESSION_TS_KEY = "ra_verified_ts_{device_id}"
_VERIFY_TTL = 3600  # seconds


def _is_verified(request, device_id):
    """Check if the current session has a valid remote-access verification for this device."""
    key = _SESSION_KEY.format(device_id=device_id)
    ts_key = _SESSION_TS_KEY.format(device_id=device_id)
    if not request.session.get(key):
        return False
    ts = request.session.get(ts_key, 0)
    return (timezone.now().timestamp() - ts) < _VERIFY_TTL


def _set_verified(request, device_id):
    key = _SESSION_KEY.format(device_id=device_id)
    ts_key = _SESSION_TS_KEY.format(device_id=device_id)
    request.session[key] = True
    request.session[ts_key] = timezone.now().timestamp()


@login_required
def verify_access(request, device_id):
    """
    Password gate before terminal / commands.
    Accepts the password of ANY operator assigned to the device's field.
    Admins still must verify (they can use their own password).
    """
    from apps.devices.models import Device
    from apps.users.models import User, UserRole

    device = get_object_or_404(
        Device.objects.select_related("pump_jack__site__field"),
        id=device_id, is_active=True,
    )

    # Where to redirect after success
    next_url = request.GET.get("next") or request.POST.get("next", "")
    # Sanitise: only allow relative URLs to our own views
    if not next_url.startswith("/"):
        next_url = ""

    if _is_verified(request, device_id):
        return redirect(next_url or "remote-access-log")

    error = ""

    if request.method == "POST":
        password = request.POST.get("password", "")

        field = device.pump_jack.site.field if device.pump_jack_id else None

        # Collect candidate users:
        # - All admins
        # - All operators assigned to the device's field
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
            _set_verified(request, device_id)
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

    # Compute which field/operators are relevant (for the hint)
    field = device.pump_jack.site.field if device.pump_jack_id else None
    field_name = field.name if field else "—"

    return render(request, "remote_access/verify_access.html", {
        "device": device,
        "field_name": field_name,
        "next_url": next_url,
        "error": error,
    })


def _require_verified(request, device_id, next_url):
    """Return a redirect to verification page if not yet verified, else None."""
    if not _is_verified(request, device_id):
        from django.urls import reverse
        url = reverse("remote-verify", kwargs={"device_id": device_id})
        return redirect(f"{url}?next={next_url}")
    return None


@login_required
def remote_access_log(request):
    from apps.devices.models import Device

    devices = (
        Device.objects
        .filter(is_active=True)
        .select_related("pump_jack__site__field__region", "assigned_operator")
        .order_by("-is_online", "pump_jack__site__field__region__name", "name")
    )

    ses_qs = (
        RemoteAccessSession.objects
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
    from apps.devices.models import Device
    from apps.common.models import AuditLog
    from django.urls import reverse

    device = get_object_or_404(
        Device.objects.select_related("pump_jack__site__field__region"),
        id=device_id, is_active=True,
    )

    # ── Security gate ────────────────────────────────────────────────────────
    next_url = reverse("remote-terminal", kwargs={"device_id": device_id})
    redir = _require_verified(request, device_id, next_url)
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
    """Command dispatch page for a specific device."""
    from apps.devices.models import Device
    from apps.common.models import AuditLog
    from django.urls import reverse

    device = get_object_or_404(
        Device.objects.select_related("pump_jack__site__field__region"),
        id=device_id, is_active=True,
    )

    # ── Security gate ────────────────────────────────────────────────────────
    next_url = reverse("remote-commands", kwargs={"device_id": device_id})
    redir = _require_verified(request, device_id, next_url)
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
