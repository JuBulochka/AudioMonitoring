"""
Device-facing API endpoints.
Edge devices (Raspberry Pi) call these endpoints to:
- Send heartbeat
- Submit audio packets
- Report critical incidents
- Poll for remote access tokens
- Report software versions

Authentication: X-Device-Key header (pre-shared per-device token).
All endpoints use DeviceAuthMiddleware to populate request.device.
"""
import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.response import Response

from apps.common.permissions import IsDeviceAuthenticated
from apps.common.throttling import DeviceRateThrottle
from apps.devices.models import DeviceHeartbeat, SoftwareVersion
from apps.devices.services import update_device_from_heartbeat
from apps.packets.services import ingest_packet
from apps.alerts.services import create_disk_critical_alert, create_high_temp_alert

logger = logging.getLogger("apps.devices")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DISK_CRITICAL_THRESHOLD = 90.0
TEMP_CRITICAL_THRESHOLD = 80.0


def _require_device(request):
    """Return 401 if device not authenticated."""
    if not request.device:
        return Response(
            {"success": False, "error": "Invalid or missing X-Device-Key"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return None


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
@throttle_classes([DeviceRateThrottle])
def heartbeat(request):
    """
    POST /api/v1/device/heartbeat/

    Payload example:
    {
        "cpu_temp": 52.3,
        "cpu_usage": 18.5,
        "memory_total_mb": 4096,
        "memory_used_mb": 1820,
        "disk_total_gb": 32.0,
        "disk_used_gb": 7.4,
        "firmware_version": "1.2.3",
        "model_version": "0.9.1",
        "uptime_seconds": 86400,
        "network_ssid": "field_wifi_01",
        "signal_strength_dbm": -65
    }
    """
    err = _require_device(request)
    if err:
        return err

    device = request.device
    data = request.data

    hb = DeviceHeartbeat.objects.create(
        device=device,
        cpu_temp=data.get("cpu_temp"),
        cpu_usage=data.get("cpu_usage"),
        memory_total_mb=data.get("memory_total_mb"),
        memory_used_mb=data.get("memory_used_mb"),
        disk_total_gb=data.get("disk_total_gb"),
        disk_used_gb=data.get("disk_used_gb"),
        firmware_version=data.get("firmware_version", ""),
        model_version=data.get("model_version", ""),
        uptime_seconds=data.get("uptime_seconds"),
        network_ssid=data.get("network_ssid", ""),
        signal_strength_dbm=data.get("signal_strength_dbm"),
        raw_data=data,
    )

    update_device_from_heartbeat(device, hb)

    # Check for alerts
    if hb.disk_usage_pct and hb.disk_usage_pct >= DISK_CRITICAL_THRESHOLD:
        create_disk_critical_alert(device, hb.disk_usage_pct)

    if hb.cpu_temp and hb.cpu_temp >= TEMP_CRITICAL_THRESHOLD:
        create_high_temp_alert(device, hb.cpu_temp)

    return Response({
        "success": True,
        "heartbeat_id": hb.id,
        # Return tunnel ports so Pi can always maintain reverse tunnels
        "tunnel_port":     device.tunnel_port,
        "vnc_tunnel_port": device.vnc_tunnel_port,
    }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Audio Packet submission
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
@throttle_classes([DeviceRateThrottle])
def submit_packet(request):
    """
    POST /api/v1/device/packet/

    Multipart form data:
    - audio_file: binary audio file (WAV/MP3)
    - data: JSON string with analysis results and metadata

    OR JSON body (when audio already uploaded separately or not included):
    {
        "recorded_at": "2024-01-15T10:00:00Z",
        "duration_seconds": 30.0,
        "analysis": {
            "normal": 0.05,
            "noise": 0.10,
            "grinding": 0.75,
            "squeak": 0.02,
            "knock": 0.03,
            "whistle": 0.01,
            "foreign_sounds": 0.01,
            "speech": 0.01,
            "other_anomaly": 0.02
        },
        "device_state": {
            "cpu_temp": 52.3,
            "cpu_usage": 18.5,
            "memory_usage_pct": 44.5,
            "disk_usage_pct": 23.1,
            "firmware_version": "1.2.3",
            "model_version": "0.9.1"
        },
        "audio_meta": {
            "sample_rate": 44100,
            "channels": 1,
            "format": "wav",
            "file_size_bytes": 1234567
        }
    }
    """
    err = _require_device(request)
    if err:
        return err

    device = request.device

    # Handle both JSON body and multipart
    if request.content_type and "multipart" in request.content_type:
        import json
        try:
            data = json.loads(request.data.get("data", "{}"))
        except (json.JSONDecodeError, ValueError):
            return Response(
                {"success": False, "error": "Invalid JSON in 'data' field"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        audio_file = request.FILES.get("audio_file")
    else:
        data = request.data
        audio_file = None

    # Validate required fields
    if "recorded_at" not in data:
        return Response(
            {"success": False, "error": "recorded_at is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if "analysis" not in data or not data["analysis"]:
        return Response(
            {"success": False, "error": "analysis is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate audio file size
    if audio_file:
        max_bytes = settings.AUDIO_MAX_FILE_SIZE_MB * 1024 * 1024
        if audio_file.size > max_bytes:
            return Response(
                {"success": False, "error": f"Audio file exceeds {settings.AUDIO_MAX_FILE_SIZE_MB}MB limit"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

    try:
        packet = ingest_packet(device, data, audio_file)
    except Exception as e:
        logger.exception("Packet ingest error for device %s: %s", device.serial_number, e)
        return Response(
            {"success": False, "error": "Packet processing failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            "success": True,
            "packet_id": str(packet.id),
            "severity": packet.severity,
            "has_anomaly": packet.has_anomaly,
        },
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# Critical incident (urgent, bypasses rate limit)
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
def report_critical(request):
    """
    POST /api/v1/device/critical/

    Urgent report — device detected a critical anomaly and sends it
    immediately without waiting for the next scheduled packet.
    Same payload as submit_packet.
    """
    err = _require_device(request)
    if err:
        return err

    device = request.device
    data = request.data

    if "analysis" not in data:
        return Response({"success": False, "error": "analysis required"}, status=400)

    audio_file = request.FILES.get("audio_file")

    try:
        packet = ingest_packet(device, data, audio_file)
    except Exception as e:
        logger.exception("Critical packet ingest error: %s", e)
        return Response({"success": False, "error": "Processing failed"}, status=500)

    return Response(
        {"success": True, "packet_id": str(packet.id), "severity": packet.severity},
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# Software version report
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
@throttle_classes([DeviceRateThrottle])
def report_version(request):
    """
    POST /api/v1/device/version/
    {
        "firmware_version": "1.2.3",
        "model_version": "0.9.1",
        "os_version": "Debian 12",
        "python_version": "3.12.0"
    }
    """
    err = _require_device(request)
    if err:
        return err

    device = request.device
    data = request.data

    SoftwareVersion.objects.create(
        device=device,
        firmware_version=data.get("firmware_version", ""),
        model_version=data.get("model_version", ""),
        os_version=data.get("os_version", ""),
        python_version=data.get("python_version", ""),
        raw_info=data,
    )

    device.firmware_version = data.get("firmware_version", device.firmware_version)
    device.model_version = data.get("model_version", device.model_version)
    device.save(update_fields=["firmware_version", "model_version", "updated_at"])

    return Response({"success": True})


# ---------------------------------------------------------------------------
# Poll for remote access commands
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
@throttle_classes([DeviceRateThrottle])
def poll_remote_access(request):
    """
    GET /api/v1/device/remote-poll/

    Device polls this endpoint to check if a remote access session is pending.
    Returns session token if active, empty if none.
    """
    err = _require_device(request)
    if err:
        return err

    device = request.device

    from apps.remote_access.models import RemoteAccessSession, RemoteAccessStatus

    session = (
        RemoteAccessSession.objects
        .filter(device=device, status=RemoteAccessStatus.APPROVED)
        .filter(token_expires_at__gt=timezone.now())
        .first()
    )

    if not session:
        return Response({"has_session": False})

    return Response({
        "has_session": True,
        "session_id": str(session.id),
        "access_token": session.access_token,
        "expires_at": session.token_expires_at.isoformat(),
        "tunnel_port": device.tunnel_port,
    })


# ---------------------------------------------------------------------------
# Confirm tunnel established (device calls this when tunnel is up)
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
def confirm_tunnel(request):
    """
    POST /api/v1/device/remote-confirm/
    {
        "session_id": "...",
        "access_token": "...",
        "tunnel_host": "0.tcp.ngrok.io",
        "tunnel_port": 12345,
        "tunnel_type": "ssh"
    }
    """
    err = _require_device(request)
    if err:
        return err

    from apps.remote_access.models import RemoteAccessSession, RemoteAccessStatus

    session_id = request.data.get("session_id")
    token = request.data.get("access_token")

    try:
        session = RemoteAccessSession.objects.get(
            id=session_id,
            device=request.device,
            access_token=token,
        )
    except RemoteAccessSession.DoesNotExist:
        return Response({"success": False, "error": "Invalid session"}, status=403)

    if not session.is_token_valid:
        return Response({"success": False, "error": "Session expired"}, status=403)

    session.start(
        tunnel_host=request.data.get("tunnel_host", ""),
        tunnel_port=request.data.get("tunnel_port"),
        device_ip=request.META.get("REMOTE_ADDR"),
    )

    logger.info("Tunnel confirmed: session=%s device=%s", session.id, request.device.serial_number)

    return Response({"success": True})


# ---------------------------------------------------------------------------
# Platform public key — Pi fetches this during pi_setup.sh to authorize
# the platform's SSH access
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
@throttle_classes([])          # setup-only endpoint — no throttling needed
def platform_pubkey(request):
    """
    GET /api/v1/device/platform-pubkey/
    Returns the platform SSH public key so Pi can add it to ~/.ssh/authorized_keys.
    Authenticated by X-Device-Key header.
    """
    import os
    from django.conf import settings as _s

    key_path = getattr(
        _s, "PLATFORM_SSH_KEY_PATH",
        os.path.join(_s.MEDIA_ROOT, "platform", "platform_key"),
    ) + ".pub"

    if not os.path.exists(key_path):
        return Response(
            {"error": "Platform key not yet generated. Restart the web container."},
            status=503,
        )

    with open(key_path) as f:
        pubkey = f.read().strip()

    return Response({"public_key": pubkey})


# ---------------------------------------------------------------------------
# Tunnel private key — Pi fetches this to establish reverse SSH tunnel.
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
@throttle_classes([])          # setup-only endpoint — no throttling needed
def tunnel_privkey(request):
    """
    GET /api/v1/device/tunnel-key/
    Returns the private SSH key Pi must use to establish the reverse tunnel.
    Authenticated by X-Device-Key header.
    """
    import os
    from django.conf import settings as _s
    from django.http import HttpResponse

    key_path = os.path.join(_s.MEDIA_ROOT, "platform", "tunnel_key")
    if not os.path.exists(key_path):
        return Response(
            {"error": "Tunnel key not yet generated. Restart the web container."},
            status=503,
        )

    with open(key_path) as f:
        privkey = f.read()

    return HttpResponse(privkey, content_type="text/plain")


# ---------------------------------------------------------------------------
# Edge client script — Pi downloads edge_client.py from here.
# Authenticated so random people can't grab internal scripts.
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([])
@permission_classes([IsDeviceAuthenticated])
@throttle_classes([])          # setup-only endpoint — no throttling needed
def edge_client_script(request):
    """GET /api/v1/device/edge-client/ — serves scripts/edge_client.py."""
    import os
    from django.conf import settings as _s
    from django.http import HttpResponse

    path = os.path.join(_s.BASE_DIR, "scripts", "edge_client.py")
    if not os.path.exists(path):
        return Response({"error": "edge_client.py not found"}, status=404)
    with open(path, "rb") as f:
        return HttpResponse(f.read(), content_type="text/x-python")


# ---------------------------------------------------------------------------
# One-command installer — generates a ready-to-run bash script for a device.
# No auth required: the device key IS the secret in the URL.
# Usage on Pi:  curl -fsSL https://<host>/api/v1/install/<key>/ | bash
# ---------------------------------------------------------------------------

def install_script(request, device_key):
    """
    GET /api/v1/install/<device_key>/
    Returns a complete bash installer that sets up the edge client on a Pi.
    No X-Device-Key header required — the key is embedded in the URL so the
    operator can simply copy-paste a single curl command from the setup page.
    """
    import os
    import textwrap
    from django.http import HttpResponse
    from apps.devices.models import Device

    try:
        device = Device.objects.get(auth_key=device_key, is_active=True)
    except Device.DoesNotExist:
        return HttpResponse("# ERROR: device not found or inactive\nexit 1\n",
                            content_type="text/x-shellscript", status=404)

    scheme      = "https" if request.is_secure() else "http"
    server_url  = f"{scheme}://{request.get_host()}"
    tunnel_host = getattr(settings, "TUNNEL_HOST",
                          request.get_host().split(":")[0])
    tunnel_ssh_port = getattr(settings, "TUNNEL_SSH_PORT", 2222)

    script = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        # ============================================================
        #  PumpJack Edge — автоустановка для устройства {device.serial_number}
        #  Сервер:  {server_url}
        #  Запуск:  curl -fsSL {server_url}/api/v1/install/{device_key}/ | bash
        # ============================================================
        set -e

        DEVICE_KEY="{device_key}"
        SERVER_URL="{server_url}"
        TUNNEL_HOST="{tunnel_host}"
        TUNNEL_PORT="{tunnel_ssh_port}"
        BASE_DIR="$HOME/pumpjack-edge"
        SERVICE_NAME="pumpjack-edge"
        CURRENT_USER="$(whoami)"
        CURRENT_HOME="$HOME"

        echo ""
        echo "╔══════════════════════════════════════════════════╗"
        echo "║   PumpJack Edge — установка                      ║"
        echo "║   Устройство: {device.serial_number:<34} ║"
        echo "╚══════════════════════════════════════════════════╝"
        echo ""

        # ── 1. Системные зависимости ──────────────────────────────
        echo "▶ Установка зависимостей..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq autossh python3-requests curl

        # ── 2. Рабочая директория ─────────────────────────────────
        echo "▶ Создание $BASE_DIR..."
        mkdir -p "$BASE_DIR"
        cd "$BASE_DIR"

        # ── 3. Конфигурационный файл .env ─────────────────────────
        echo "▶ Запись .env..."
        cat > "$BASE_DIR/.env" << ENVEOF
SERVER_URL={server_url}
DEVICE_AUTH_KEY={device_key}
TUNNEL_REMOTE_HOST={tunnel_host}
TUNNEL_REMOTE_PORT={tunnel_ssh_port}
TUNNEL_KEY_PATH=$CURRENT_HOME/.ssh/pumpjack_tunnel_key
HEARTBEAT_INTERVAL_SEC=60
PACKET_INTERVAL_SEC=300
FIRMWARE_VERSION=1.3.2
MODEL_VERSION=0.9.4
ENVEOF

        # ── 4. SSH-директория ─────────────────────────────────────
        echo "▶ Настройка SSH..."
        sudo chown -R "$CURRENT_USER:$CURRENT_USER" "$CURRENT_HOME/.ssh" 2>/dev/null || true
        mkdir -p "$CURRENT_HOME/.ssh" && chmod 700 "$CURRENT_HOME/.ssh"

        # ── 5. Ключ туннеля (Pi → сервер) ────────────────────────
        echo "▶ Загрузка ключа туннеля..."
        curl -fsSL -H "X-Device-Key: $DEVICE_KEY" \\
            "$SERVER_URL/api/v1/device/tunnel-key/" \\
            -o "$CURRENT_HOME/.ssh/pumpjack_tunnel_key"
        chmod 600 "$CURRENT_HOME/.ssh/pumpjack_tunnel_key"

        # ── 6. Публичный ключ платформы (сервер → Pi) ────────────
        echo "▶ Добавление публичного ключа платформы..."
        PUB=$(curl -fsSL -H "X-Device-Key: $DEVICE_KEY" \\
                "$SERVER_URL/api/v1/device/platform-pubkey/" \\
              | python3 -c "import sys,json; print(json.load(sys.stdin)['public_key'])")
        touch "$CURRENT_HOME/.ssh/authorized_keys" && chmod 600 "$CURRENT_HOME/.ssh/authorized_keys"
        grep -qxF "$PUB" "$CURRENT_HOME/.ssh/authorized_keys" 2>/dev/null || echo "$PUB" >> "$CURRENT_HOME/.ssh/authorized_keys"

        # ── 7. Edge-клиент ────────────────────────────────────────
        echo "▶ Загрузка edge_client.py..."
        curl -fsSL -H "X-Device-Key: $DEVICE_KEY" \\
            "$SERVER_URL/api/v1/device/edge-client/" \\
            -o "$BASE_DIR/edge_client.py"
        chmod +x "$BASE_DIR/edge_client.py"

        # ── 8. Systemd-сервис ─────────────────────────────────────
        echo "▶ Создание systemd-сервиса $SERVICE_NAME..."
        sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << SVCEOF
[Unit]
Description=PumpJack Edge Client ({device.serial_number})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$BASE_DIR
EnvironmentFile=$BASE_DIR/.env
ExecStart=/usr/bin/python3 $BASE_DIR/edge_client.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pumpjack-edge

[Install]
WantedBy=multi-user.target
SVCEOF

        sudo systemctl daemon-reload
        sudo systemctl enable $SERVICE_NAME
        sudo systemctl restart $SERVICE_NAME

        echo ""
        echo "╔══════════════════════════════════════════════════╗"
        echo "║   ✓ Установка завершена!                         ║"
        echo "╚══════════════════════════════════════════════════╝"
        echo ""
        echo "Сервис запущен и добавлен в автозапуск."
        echo ""
        echo "Полезные команды:"
        echo "  Статус:    sudo systemctl status $SERVICE_NAME"
        echo "  Логи:      sudo journalctl -u $SERVICE_NAME -f"
        echo "  Стоп:      sudo systemctl stop $SERVICE_NAME"
        echo "  Рестарт:   sudo systemctl restart $SERVICE_NAME"
        echo ""
        sleep 3
        sudo journalctl -u $SERVICE_NAME -n 20 --no-pager
    """)

    return HttpResponse(script, content_type="text/x-shellscript")


# ---------------------------------------------------------------------------
# Command dispatch — delegate to commands_endpoints (avoids circular import)
# ---------------------------------------------------------------------------
from api.v1.commands_endpoints import (  # noqa: E402
    device_poll_commands as _device_poll_commands,
    device_report_result as _device_report_result,
)

# ---------------------------------------------------------------------------
# URL patterns
# ---------------------------------------------------------------------------
from django.urls import path  # noqa: E402

urlpatterns = [
    path("heartbeat/", heartbeat, name="device-heartbeat"),
    path("packet/", submit_packet, name="device-packet"),
    path("critical/", report_critical, name="device-critical"),
    path("version/", report_version, name="device-version"),
    path("remote-poll/", poll_remote_access, name="device-remote-poll"),
    path("remote-confirm/", confirm_tunnel, name="device-remote-confirm"),
    path("platform-pubkey/", platform_pubkey, name="device-platform-pubkey"),
    path("tunnel-key/", tunnel_privkey, name="device-tunnel-key"),
    path("edge-client/", edge_client_script, name="device-edge-client"),
    # Command dispatch (Pi polls for commands, reports results)
    path("commands/", _device_poll_commands, name="device-commands-poll"),
    path("commands/<uuid:command_id>/result/", _device_report_result, name="device-commands-result"),
]
