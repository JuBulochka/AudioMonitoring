"""Remote access web views."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from .models import RemoteAccessSession, COMMAND_CATALOG


@login_required
def remote_access_log(request):
    from apps.users.models import UserRole
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

    # Build dict: device_id (str) → most recent session
    last_session = {}
    for s in ses_qs[:300]:
        did = str(s.device_id)
        if did not in last_session:
            last_session[did] = s

    # Attach last_session to each device object for easy template access
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

    device = get_object_or_404(
        Device.objects.select_related("pump_jack__site__field__region"),
        id=device_id,
        is_active=True,
    )

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
    """
    Command dispatch page for a specific device.
    Shows the command catalog and execution history.
    """
    from apps.devices.models import Device
    from apps.common.models import AuditLog

    device = get_object_or_404(
        Device.objects.select_related("pump_jack__site__field__region"),
        id=device_id,
        is_active=True,
    )

    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.REMOTE_ACCESS_REQUESTED,
        object_type="Device",
        object_id=str(device.id),
        description=f"Открыта страница команд для устройства {device.serial_number}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Group catalog by category for the UI
    categories = {}
    for key, meta in COMMAND_CATALOG.items():
        cat = meta["category"]
        categories.setdefault(cat, []).append({"key": key, **meta})

    return render(request, "remote_access/commands.html", {
        "device":     device,
        "categories": categories,
    })

