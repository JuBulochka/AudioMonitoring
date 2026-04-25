"""
SSH Terminal WebSocket Consumer
================================
Proxies a full interactive SSH session between the browser (xterm.js)
and the Raspberry Pi via the reverse SSH tunnel.

Flow:
  Browser (xterm.js)
    ↕ WebSocket  ws://.../ws/ssh/<device_id>/
  Django Channels SSHTerminalConsumer
    ↕ asyncssh
  sshd container:  host=sshd, port=<device.tunnel_port>
    ↕ reverse tunnel (Pi established this)
  Raspberry Pi sshd  port 22
"""
import asyncio
import json
import logging
import os

import asyncssh
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("apps.remote_access")

# Message types sent to browser
MSG_OUTPUT = "output"   # raw terminal bytes → base64 encoded
MSG_STATUS = "status"   # "connecting" | "connected" | "disconnected" | "error"
MSG_RESIZE = "resize"   # ack (not sent to browser, received from browser)


def _platform_key_path() -> str:
    return getattr(
        settings,
        "PLATFORM_SSH_KEY_PATH",
        os.path.join(settings.MEDIA_ROOT, "platform", "platform_key"),
    )


def _sshd_host() -> str:
    return getattr(settings, "SSHD_HOST", "sshd")


def _pi_user() -> str:
    return getattr(settings, "PI_SSH_USER", "pi")


class SSHTerminalConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that creates a live SSH session to a Raspberry Pi.

    URL: ws://<host>/ws/ssh/<device_id>/

    Protocol (browser → server):
        Binary frames  → forwarded as stdin to SSH
        Text frames    → JSON control messages:
            {"type": "resize", "cols": 120, "rows": 30}
            {"type": "ping"}

    Protocol (server → browser):
        Binary frames  → raw SSH stdout/stderr bytes
        Text frames    → JSON status:
            {"type": "status", "status": "connecting", "message": "..."}
            {"type": "status", "status": "connected",  "message": "..."}
            {"type": "status", "status": "error",      "message": "..."}
    """

    ssh_conn = None
    ssh_process = None
    _read_task = None
    _ssh_user = None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.device_id = self.scope["url_route"]["kwargs"]["device_id"]
        self.user = user

        device = await self._get_device(self.device_id)
        if not device:
            await self.accept()
            await self._send_status("error", "Устройство не найдено")
            await self.close()
            return

        if not device.tunnel_port:
            await self.accept()
            await self._send_status(
                "error",
                "Устройству не назначен порт туннеля. Убедитесь, что устройство создано в системе."
            )
            await self.close()
            return

        self.device = device
        await self.accept()

        # Log audit
        await self._create_session_log()

        await self._send_status("connecting", f"Подключение к {device.serial_number}…")
        await self._start_ssh()

    async def disconnect(self, code):
        if self._read_task:
            self._read_task.cancel()
        if self.ssh_process:
            try:
                self.ssh_process.close()
            except Exception:
                pass
        if self.ssh_conn:
            try:
                self.ssh_conn.close()
            except Exception:
                pass
        await self._mark_session_ended()
        logger.info("SSH terminal disconnected: device=%s user=%s", self.device_id, getattr(self, 'user', '?'))

    async def receive(self, text_data=None, bytes_data=None):
        if self.ssh_process is None:
            return

        if bytes_data:
            # Raw keyboard input → stdin (process opened with encoding=None → expects bytes)
            try:
                self.ssh_process.stdin.write(bytes_data)
            except Exception as e:
                logger.debug("SSH stdin write error: %s", e)

        elif text_data:
            try:
                msg = json.loads(text_data)
                if msg.get("type") == "resize":
                    cols = int(msg.get("cols", 80))
                    rows = int(msg.get("rows", 24))
                    self.ssh_process.change_terminal_size(width=cols, height=rows)
            except (json.JSONDecodeError, ValueError):
                # Treat as raw text input
                try:
                    self.ssh_process.stdin.write(text_data.encode("utf-8"))
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # SSH connection
    # -------------------------------------------------------------------------

    async def _start_ssh(self):
        key_path = _platform_key_path()
        sshd_host = _sshd_host()
        pi_user = _pi_user()
        self._ssh_user = pi_user
        tunnel_port = self.device.tunnel_port

        if not os.path.exists(key_path):
            await self._send_status(
                "error",
                f"Платформенный SSH-ключ не найден ({key_path}). "
                "Перезапустите контейнер web для генерации ключа."
            )
            await self.close()
            return

        try:
            logger.info("SSH connect: %s:%d as %s (device=%s)",
                        sshd_host, tunnel_port, pi_user, self.device_id)

            self.ssh_conn = await asyncssh.connect(
                host=sshd_host,
                port=tunnel_port,
                username=pi_user,
                client_keys=[key_path],
                known_hosts=None,           # No host key checking (tunneled connection)
                connect_timeout=15,
                encoding=None,              # Raw bytes mode
            )

            self.ssh_process = await self.ssh_conn.create_process(
                term_type="xterm-256color",
                term_size=(80, 24),
                encoding=None,
            )

            await self._send_status("connected", f"Подключено к {self.device.serial_number}")
            await self._mark_session_active()

            # Start background task: SSH stdout → WebSocket
            self._read_task = asyncio.ensure_future(self._ssh_to_ws())

        except asyncssh.DisconnectError as e:
            await self._send_status("error", f"SSH отключён: {e.reason}")
            await self.close()
        except asyncssh.PermissionDenied:
            await self._send_status(
                "error",
                "Доступ запрещён. Убедитесь, что публичный ключ платформы добавлен "
                "на Raspberry Pi (pi_setup.sh делает это автоматически)."
            )
            await self.close()
        except (OSError, asyncssh.Error) as e:
            msg = str(e)
            if "Connection refused" in msg or "timed out" in msg:
                await self._send_status(
                    "error",
                    f"Нет подключения. Убедитесь, что устройство в сети и туннель активен "
                    f"(порт {tunnel_port}). Ошибка: {msg}"
                )
            else:
                await self._send_status("error", f"Ошибка SSH: {msg}")
            await self.close()
        except Exception as e:
            logger.exception("Unexpected SSH error for device %s", self.device_id)
            await self._send_status("error", f"Неожиданная ошибка: {e}")
            await self.close()

    async def _ssh_to_ws(self):
        """Continuously read SSH stdout and forward to WebSocket."""
        sent_any_output = False
        try:
            while True:
                data = await self.ssh_process.stdout.read(8192)
                if not data:
                    break
                sent_any_output = True
                await self.send(bytes_data=data)
        except asyncssh.TerminalSizeChanged:
            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("SSH read error: %s", e)
        finally:
            try:
                await self._send_status("disconnected", "Сессия завершена")
                await self.close()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    async def _send_status(self, status: str, message: str):
        try:
            await self.send(text_data=json.dumps({
                "type": "status",
                "status": status,
                "message": message,
            }))
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # DB helpers (run in thread pool)
    # -------------------------------------------------------------------------

    @database_sync_to_async
    def _get_device(self, device_id):
        from apps.devices.models import Device
        try:
            return Device.objects.select_related(
                "pump_jack__site__field__region"
            ).get(id=device_id, is_active=True)
        except Device.DoesNotExist:
            return None

    @database_sync_to_async
    def _create_session_log(self):
        from apps.remote_access.models import RemoteAccessSession
        try:
            self._session_obj = RemoteAccessSession.objects.create(
                device=self.device,
                operator=self.user,
                operator_ip=self.scope.get("client", ["", ""])[0],
            )
        except Exception as e:
            logger.warning("Could not create session log: %s", e)
            self._session_obj = None

    @database_sync_to_async
    def _mark_session_active(self):
        if getattr(self, "_session_obj", None):
            try:
                self._session_obj.start(
                    tunnel_host=_sshd_host(),
                    tunnel_port=self.device.tunnel_port,
                )
            except Exception:
                pass


    @database_sync_to_async
    def _mark_session_ended(self):
        if getattr(self, "_session_obj", None):
            try:
                self._session_obj.end(notes="Веб-терминал закрыт")
            except Exception:
                pass
