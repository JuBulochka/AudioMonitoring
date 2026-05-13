"""API команд: Raspberry Pi забирает задания, оператор создает и смотрит их."""
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.response import Response

from apps.common.permissions import IsDeviceAuthenticated
from apps.common.throttling import DeviceRateThrottle
from apps.devices.models import Device
from apps.remote_access.models import COMMAND_CATALOG, CommandStatus, DeviceCommand
from apps.users.access import filter_devices_by_user

logger = logging.getLogger("apps.remote_access")



@api_view(["GET"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
@throttle_classes([DeviceRateThrottle])
def device_poll_commands(request):
    """
    Возвращает ожидающие команды для устройства.

    После выдачи команды сразу помечаются как running, чтобы Raspberry Pi
    не получил одну и ту же команду повторно при следующем опросе.
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
@throttle_classes([DeviceRateThrottle])
def device_report_result(request, command_id):
    """Принимает от Raspberry Pi результат выполнения команды."""
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



def _check_operator(request):
    """Единая проверка, что запрос пришел от авторизованного пользователя."""
    if not request.user or not request.user.is_authenticated:
        return Response({"error": "Authentication required"}, status=401)
    return None


@api_view(["GET"])
def catalog(request):
    """Отдает фронтенду список доступных команд из серверного каталога."""
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
    Читает историю команд или создает новую команду для устройства.

    Все выборки проходят через filter_devices_by_user, поэтому оператор не может
    увидеть или отправить команду на чужое месторождение.
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
            .filter(device_id=device_id, device__in=filter_devices_by_user(Device.objects.all(), request.user))
            .select_related("sent_by")
            .order_by("-created_at")
        )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        data = []
        for cmd in qs[:100]:
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
        device = filter_devices_by_user(Device.objects.all(), request.user).get(id=device_id, is_active=True)
    except Device.DoesNotExist:
        return Response({"error": "Device not found"}, status=404)

    already = DeviceCommand.objects.filter(
        device=device,
        command_key=command_key,
        status__in=[CommandStatus.PENDING, CommandStatus.RUNNING],
    ).exists()
    # Не ставим вторую такую же команду, пока первая еще не завершилась.
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
    """Возвращает подробности команды вместе с выводом терминала."""
    err = _check_operator(request)
    if err:
        return err

    try:
        cmd = DeviceCommand.objects.select_related("device", "sent_by").get(
            id=command_id,
            device__in=filter_devices_by_user(Device.objects.all(), request.user),
        )
    except DeviceCommand.DoesNotExist:
        return Response({"error": "Not found"}, status=404)

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
    """Отменяет команду, если она еще не перешла в финальное состояние."""
    err = _check_operator(request)
    if err:
        return err

    try:
        cmd = DeviceCommand.objects.get(
            id=command_id,
            device__in=filter_devices_by_user(Device.objects.all(), request.user),
        )
    except DeviceCommand.DoesNotExist:
        return Response({"error": "Not found"}, status=404)

    if cmd.status not in (CommandStatus.PENDING, CommandStatus.RUNNING):
        return Response({"error": f"Cannot cancel command in '{cmd.status}' state"}, status=400)

    cmd.status = CommandStatus.CANCELLED
    cmd.completed_at = timezone.now()
    cmd.save(update_fields=["status", "completed_at"])

    return Response({"success": True})


from django.urls import path  # noqa: E402

urlpatterns = [
    path("catalog/",                catalog,             name="commands-catalog"),
    path("",                        command_list_create, name="commands-list-create"),
    path("<uuid:command_id>/",      command_detail,      name="commands-detail"),
    path("<uuid:command_id>/cancel/", command_cancel,    name="commands-cancel"),
]
