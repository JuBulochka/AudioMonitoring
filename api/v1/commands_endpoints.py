"""
Command dispatch API.

Pi-facing  (authenticated by X-Device-Key):
  GET  /api/v1/device/commands/        — Pi polls for pending commands
  POST /api/v1/device/commands/<id>/result/  — Pi reports execution result

Operator-facing (authenticated by session / JWT):
  GET  /api/v1/commands/catalog/               — list available command types
  GET  /api/v1/commands/?device=<uuid>         — command history for a device
  POST /api/v1/commands/                       — send a command to a device
  POST /api/v1/commands/<id>/cancel/           — cancel a pending command
  GET  /api/v1/commands/<id>/                  — single command detail + output
"""
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from apps.common.permissions import IsDeviceAuthenticated
from apps.remote_access.models import COMMAND_CATALOG, CommandStatus, DeviceCommand

logger = logging.getLogger("apps.remote_access")


# ============================================================================
# Pi-facing endpoints
# ============================================================================

@api_view(["GET"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
def device_poll_commands(request):
    """
    GET /api/v1/device/commands/

    Pi calls this every N seconds. Returns all pending commands for the device.
    The Pi should process them in order (oldest first) and report results.

    Response:
    {
        "commands": [
            {"id": "uuid", "command_key": "system_info", "params": {}, "created_at": "..."},
            ...
        ]
    }
    """
    if not request.device:
        return Response({"error": "Unauthorized"}, status=401)

    pending = (
        DeviceCommand.objects
        .filter(device=request.device, status=CommandStatus.PENDING)
        .order_by("created_at")
    )

    commands_data = [
        {
            "id":          str(cmd.id),
            "command_key": cmd.command_key,
            "params":      cmd.params,
            "created_at":  cmd.created_at.isoformat(),
        }
        for cmd in pending
    ]

    # Mark all returned commands as "running" immediately
    if commands_data:
        ids = [c["id"] for c in commands_data]
        DeviceCommand.objects.filter(id__in=ids, status=CommandStatus.PENDING).update(
            status=CommandStatus.RUNNING,
            picked_up_at=timezone.now(),
        )

    return Response({"commands": commands_data})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
def device_report_result(request, command_id):
    """
    POST /api/v1/device/commands/<id>/result/

    Pi reports the result of a command execution.

    Body:
    {
        "output":    "...stdout/stderr...",
        "exit_code": 0,
        "error":     ""   // optional, filled if exception occurred
    }
    """
    if not request.device:
        return Response({"error": "Unauthorized"}, status=401)

    try:
        cmd = DeviceCommand.objects.get(id=command_id, device=request.device)
    except DeviceCommand.DoesNotExist:
        return Response({"error": "Command not found"}, status=404)

    if cmd.status not in (CommandStatus.RUNNING, CommandStatus.PENDING):
        return Response({"error": "Command already in terminal state"}, status=400)

    data      = request.data
    output    = data.get("output", "")
    exit_code = data.get("exit_code", 0)
    error     = data.get("error", "")

    if error:
        cmd.status        = CommandStatus.FAILED
        cmd.error_message = error
        cmd.output        = output
    else:
        cmd.status    = CommandStatus.COMPLETED if exit_code == 0 else CommandStatus.FAILED
        cmd.output    = output
        cmd.exit_code = exit_code

    cmd.completed_at = timezone.now()
    cmd.save(update_fields=["status", "output", "exit_code", "error_message", "completed_at"])

    logger.info(
        "Command result: id=%s key=%s device=%s status=%s exit_code=%s",
        cmd.id, cmd.command_key, request.device.serial_number, cmd.status, exit_code,
    )

    return Response({"success": True})


# ============================================================================
# Operator-facing endpoints
# ============================================================================

def _check_operator(request):
    if not request.user or not request.user.is_authenticated:
        return Response({"error": "Authentication required"}, status=401)
    return None


@api_view(["GET"])
def catalog(request):
    """
    GET /api/v1/commands/catalog/

    Returns the full list of available command types grouped by category.
    """
    err = _check_operator(request)
    if err:
        return err

    result = []
    for key, meta in COMMAND_CATALOG.items():
        result.append({
            "key":              key,
            "label":            meta["label"],
            "description":      meta["description"],
            "category":         meta["category"],
            "timeout":          meta["timeout"],
            "requires_confirm": meta.get("requires_confirm", False),
            "icon":             meta.get("icon", "bi-terminal"),
        })
    return Response(result)


@api_view(["GET", "POST"])
def command_list_create(request):
    """
    GET  /api/v1/commands/?device=<uuid>[&status=pending]
         Returns command history for a device (latest 100).

    POST /api/v1/commands/
         Send a command to a device.
         Body: {"device_id": "uuid", "command_key": "system_info", "params": {}}
    """
    err = _check_operator(request)
    if err:
        return err

    if request.method == "GET":
        device_id = request.query_params.get("device")
        if not device_id:
            return Response({"error": "device query param required"}, status=400)

        qs = (
            DeviceCommand.objects
            .filter(device_id=device_id)
            .select_related("sent_by")
            .order_by("-created_at")[:100]
        )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        data = []
        for cmd in qs:
            entry = COMMAND_CATALOG.get(cmd.command_key, {})
            data.append({
                "id":            str(cmd.id),
                "command_key":   cmd.command_key,
                "label":         entry.get("label", cmd.command_key),
                "category":      entry.get("category", ""),
                "icon":          entry.get("icon", "bi-terminal"),
                "status":        cmd.status,
                "exit_code":     cmd.exit_code,
                "sent_by":       cmd.sent_by.username if cmd.sent_by else None,
                "created_at":    cmd.created_at.isoformat(),
                "picked_up_at":  cmd.picked_up_at.isoformat()  if cmd.picked_up_at  else None,
                "completed_at":  cmd.completed_at.isoformat()  if cmd.completed_at  else None,
                "duration_sec":  cmd.duration_seconds,
                "has_output":    bool(cmd.output),
            })

        return Response(data)

    # POST — create command
    from apps.devices.models import Device
    body        = request.data
    device_id   = body.get("device_id")
    command_key = body.get("command_key")

    if not device_id or not command_key:
        return Response({"error": "device_id and command_key are required"}, status=400)

    if command_key not in COMMAND_CATALOG:
        return Response(
            {"error": f"Unknown command_key '{command_key}'. See /api/v1/commands/catalog/"},
            status=400,
        )

    try:
        device = Device.objects.get(id=device_id, is_active=True)
    except Device.DoesNotExist:
        return Response({"error": "Device not found"}, status=404)

    # Prevent duplicate pending/running commands of the same type
    already = DeviceCommand.objects.filter(
        device=device,
        command_key=command_key,
        status__in=[CommandStatus.PENDING, CommandStatus.RUNNING],
    ).exists()
    if already:
        return Response(
            {"error": "This command is already pending or running on the device"},
            status=409,
        )

    cmd = DeviceCommand.objects.create(
        device      = device,
        sent_by     = request.user,
        command_key = command_key,
        params      = body.get("params", {}),
    )

    logger.info(
        "Command dispatched: key=%s device=%s by=%s",
        command_key, device.serial_number, request.user.username,
    )

    entry = COMMAND_CATALOG[command_key]
    return Response(
        {
            "id":          str(cmd.id),
            "command_key": cmd.command_key,
            "label":       entry["label"],
            "status":      cmd.status,
            "created_at":  cmd.created_at.isoformat(),
        },
        status=201,
    )


@api_view(["GET"])
def command_detail(request, command_id):
    """
    GET /api/v1/commands/<id>/
    Returns full details including output text.
    """
    err = _check_operator(request)
    if err:
        return err

    try:
        cmd = DeviceCommand.objects.select_related("device", "sent_by").get(id=command_id)
    except DeviceCommand.DoesNotExist:
        return Response({"error": "Not found"}, status=404)

    # Only allow access if operator owns it or is admin
    if (not request.user.is_admin
            and cmd.sent_by != request.user):
        return Response({"error": "Forbidden"}, status=403)

    entry = COMMAND_CATALOG.get(cmd.command_key, {})
    return Response({
        "id":            str(cmd.id),
        "command_key":   cmd.command_key,
        "label":         entry.get("label", cmd.command_key),
        "category":      entry.get("category", ""),
        "description":   entry.get("description", ""),
        "params":        cmd.params,
        "status":        cmd.status,
        "exit_code":     cmd.exit_code,
        "output":        cmd.output,
        "error_message": cmd.error_message,
        "sent_by":       cmd.sent_by.username if cmd.sent_by else None,
        "device":        {"id": str(cmd.device_id), "serial": cmd.device.serial_number},
        "created_at":    cmd.created_at.isoformat(),
        "picked_up_at":  cmd.picked_up_at.isoformat()  if cmd.picked_up_at  else None,
        "completed_at":  cmd.completed_at.isoformat()  if cmd.completed_at  else None,
        "duration_sec":  cmd.duration_seconds,
    })


@api_view(["POST"])
def command_cancel(request, command_id):
    """
    POST /api/v1/commands/<id>/cancel/
    Cancel a pending command (cannot cancel running/completed).
    """
    err = _check_operator(request)
    if err:
        return err

    try:
        cmd = DeviceCommand.objects.get(id=command_id)
    except DeviceCommand.DoesNotExist:
        return Response({"error": "Not found"}, status=404)

    if cmd.status not in (CommandStatus.PENDING, CommandStatus.RUNNING):
        return Response({"error": f"Cannot cancel command in '{cmd.status}' state"}, status=400)

    cmd.status = CommandStatus.CANCELLED
    cmd.completed_at = timezone.now()
    cmd.save(update_fields=["status", "completed_at"])

    return Response({"success": True})


# ---------------------------------------------------------------------------
# URL patterns (included by api/v1/urls.py)
# ---------------------------------------------------------------------------
from django.urls import path  # noqa: E402

urlpatterns = [
    path("catalog/",                catalog,             name="commands-catalog"),
    path("",                        command_list_create, name="commands-list-create"),
    path("<uuid:command_id>/",      command_detail,      name="commands-detail"),
    path("<uuid:command_id>/cancel/", command_cancel,    name="commands-cancel"),
]
