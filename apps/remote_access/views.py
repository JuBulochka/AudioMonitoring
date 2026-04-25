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
    if request.user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
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


@login_required
def vnc_desktop(request, device_id):
    """
    Browser-based remote desktop via noVNC + VNC reverse tunnel.
    Writes a websockify token entry so noVNC can route to the right Pi VNC port.
    """
    from apps.devices.models import Device
    from apps.common.models import AuditLog
    import os

    device = get_object_or_404(
        Device.objects.select_related("pump_jack__site__field__region"),
        id=device_id,
        is_active=True,
    )

    # Write/update the noVNC token so websockify knows where to connect.
    # Token file lives in /vnc_tokens/ (Docker volume shared with novnc container).
    token     = str(device.id)
    vnc_host  = "sshd"                         # internal Docker hostname
    vnc_port  = device.vnc_tunnel_port or 21001

    token_file = os.environ.get("VNC_TOKEN_FILE", "/vnc_tokens/tokens.cfg")
    try:
        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        # Read existing lines (avoid duplicate tokens)
        try:
            with open(token_file) as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []

        new_line = f"{token}: {vnc_host}:{vnc_port}\n"
        updated  = False
        new_lines = []
        for line in lines:
            if line.startswith(token + ":"):
                new_lines.append(new_line)
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(new_line)

        with open(token_file, "w") as f:
            f.writelines(new_lines)
    except OSError as e:
        import logging
        logging.getLogger("apps.remote_access").warning("Could not write VNC token file: %s", e)

    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.REMOTE_ACCESS_REQUESTED,
        object_type="Device",
        object_id=str(device.id),
        description=f"Открыт VNC-рабочий стол для {device.serial_number}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    return render(request, "remote_access/vnc.html", {
        "device":    device,
        "vnc_token": token,
        "vnc_port":  vnc_port,
    })
