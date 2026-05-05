#!/usr/bin/env python3
"""
PumpJack Audio Monitor — Edge Client for Raspberry Pi 4
========================================================
Runs on the Raspberry Pi attached to each pump jack.

Responsibilities:
  1. Record audio from microphone (configurable duration)
  2. Run local ML model to classify audio
  3. Send heartbeat to server every N minutes
  4. Send audio packet (with analysis results) every 3 hours
  5. Send IMMEDIATE critical alert if anomaly score exceeds threshold
  6. Poll for remote access and open reverse SSH tunnel
  7. Poll for operator commands and execute them
  8. Report software version on startup

Configuration: /opt/pumpjack/.env  (env vars)

Usage:
  EnvironmentFile=/opt/pumpjack/.env
  ExecStart=/opt/pumpjack/venv/bin/python /opt/pumpjack/edge_client.py
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed: pip install requests")

# ---------------------------------------------------------------------------
# Config  (all from .env / environment)
# ---------------------------------------------------------------------------
SERVER_URL        = os.environ.get("SERVER_URL", "http://localhost:8000").rstrip("/")
DEVICE_AUTH_KEY   = os.environ.get("DEVICE_AUTH_KEY", "")
FIRMWARE_VERSION  = os.environ.get("FIRMWARE_VERSION", "1.3.2")
MODEL_VERSION     = os.environ.get("MODEL_VERSION",    "0.9.4")

RECORD_DURATION_SEC    = int(os.environ.get("RECORD_DURATION_SEC",    "30"))
PACKET_INTERVAL_SEC    = int(os.environ.get("PACKET_INTERVAL_SEC",    "10800"))  # 3 hours
HEARTBEAT_INTERVAL_SEC = int(os.environ.get("HEARTBEAT_INTERVAL_SEC", "300"))    # 5 min
REMOTE_POLL_INTERVAL_SEC  = int(os.environ.get("REMOTE_POLL_INTERVAL_SEC",  "60"))
COMMAND_POLL_INTERVAL_SEC = int(os.environ.get("COMMAND_POLL_INTERVAL_SEC", "30"))

CRITICAL_SCORE_THRESHOLD = float(os.environ.get("CRITICAL_SCORE_THRESHOLD", "0.65"))
SAMPLE_RATE  = 44100
CHANNELS     = 1
AUDIO_FORMAT = "wav"

# If set to "true", audio file is NOT uploaded — only analysis JSON is sent
DISABLE_AUDIO_UPLOAD = os.environ.get("DISABLE_AUDIO_UPLOAD", "false").lower() == "true"

# SSH tunnel
TUNNEL_REMOTE_HOST = os.environ.get("TUNNEL_REMOTE_HOST", "")
TUNNEL_REMOTE_PORT = int(os.environ.get("TUNNEL_REMOTE_PORT", "2222"))
TUNNEL_KEY_PATH    = os.environ.get("TUNNEL_KEY_PATH", "/opt/pumpjack/.ssh/tunnel_key")
LOCAL_SSH_PORT     = 22

# Trigger file: operator sends "record_now" command → edge_client picks it up
RECORD_TRIGGER_FILE = "/tmp/pumpjack_record_now"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("edge_client")

# ---------------------------------------------------------------------------
# Command catalog (MUST mirror server-side COMMAND_CATALOG in models.py)
# Server sends only the command_key; Pi runs the script defined here.
# ---------------------------------------------------------------------------
_CMD_CATALOG: dict = {

    # 1 — Логи и статус сервиса
    "view_logs": {
        "script": r"""
echo '=== СТАТУС СЕРВИСА ==='
if systemctl is-active --quiet pumpjack-edge 2>/dev/null; then
    echo "OK: pumpjack-edge.service активен (systemd)"
    systemctl status pumpjack-edge --no-pager -l 2>/dev/null | head -20
else
    EPID=$(pgrep -f edge_client.py | head -1)
    if [ -n "$EPID" ]; then
        echo "OK: edge_client.py запущен вручную (PID=$EPID)"
        ps -p "$EPID" -o pid,etime,pcpu,pmem,cmd --no-headers 2>/dev/null
    else
        echo "ВНИМАНИЕ: edge_client.py не запущен"
    fi
fi
echo ''
echo '=== ПОСЛЕДНИЕ ЛОГИ (journalctl) ==='
journalctl -u pumpjack-edge -n 30 --no-pager 2>/dev/null \
    || echo "(journalctl недоступен — сервис запущен вручную)"
echo ''
echo '=== СИСТЕМНАЯ ИНФОРМАЦИЯ ==='
uptime
echo ''
echo '=== СЕТЕВЫЕ ТУННЕЛИ ==='
ss -tnp 2>/dev/null | grep -E 'ssh|autossh|2222' || echo 'Активных SSH-туннелей не обнаружено'
""".strip(),
        "timeout": 15,
    },

    # 2 — Отключить отправку аудио
    "disable_audio": {
        "script": r"""
BASE_DIR="$HOME/pumpjack-edge"
ENV_FILE="$BASE_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "ОШИБКА: .env не найден в $ENV_FILE"
    exit 1
fi
if grep -q '^DISABLE_AUDIO_UPLOAD=true' "$ENV_FILE" 2>/dev/null; then
    echo 'Отправка аудио уже отключена (DISABLE_AUDIO_UPLOAD=true)'
else
    if grep -q 'DISABLE_AUDIO_UPLOAD' "$ENV_FILE" 2>/dev/null; then
        sed -i 's/^DISABLE_AUDIO_UPLOAD=.*/DISABLE_AUDIO_UPLOAD=true/' "$ENV_FILE"
    else
        echo '' >> "$ENV_FILE"
        echo 'DISABLE_AUDIO_UPLOAD=true' >> "$ENV_FILE"
    fi
    echo "Записано: DISABLE_AUDIO_UPLOAD=true в $ENV_FILE"
    echo ''
    echo 'С этого момента аудиофайлы НЕ отправляются — только аналитика.'
    echo 'Изменение вступит в силу при следующем запуске записи.'
    echo 'Чтобы включить обратно: удалите строку DISABLE_AUDIO_UPLOAD из .env'
fi
""".strip(),
        "timeout": 15,
    },

    # 3 — Ручной старт записи прямо сейчас
    "record_now": {
        "script": r"""
TRIGGER=/tmp/pumpjack_record_now
touch "$TRIGGER"
echo "Триггер создан: $TRIGGER"
echo "Edge client обнаружит файл и запустит запись немедленно."
echo ''
echo 'Ожидание обработки...'
for i in $(seq 1 6); do
    sleep 5
    if [ ! -f "$TRIGGER" ]; then
        echo "OK: edge client обработал триггер — запись запущена (через $((i*5)) сек)."
        exit 0
    fi
    echo "  ... ожидаем (${i}/6)"
done
echo 'ПРЕДУПРЕЖДЕНИЕ: файл триггера не обработан за 30 сек.'
echo 'Проверьте что edge_client.py запущен: pgrep -f edge_client.py'
rm -f "$TRIGGER"
exit 1
""".strip(),
        "timeout": 40,
    },

    # 4 — Диагностика звука (USB-камера)
    "audio_diagnostics": {
        "script": r"""
echo '=== USB УСТРОЙСТВА ==='
lsusb 2>&1 | grep -iE 'audio|camera|mic|sound|video|capture|uvc' || echo 'USB audio-устройств не найдено'
echo ''
echo '=== ALSA — УСТРОЙСТВА ЗАПИСИ ==='
arecord -l 2>&1
echo ''
echo '=== SOUNDDEVICE (Python) ==='
python3 - <<'PYEOF'
try:
    import sounddevice as sd
    devs = sd.query_devices()
    inp = [d for d in devs if d['max_input_channels'] > 0]
    if inp:
        for i, d in enumerate(devs):
            if d['max_input_channels'] > 0:
                marker = ' <-- default' if sd.default.device[0] == i else ''
                print(f"  [{i}] {d['name']}  (ch:{d['max_input_channels']}){marker}")
    else:
        print('  Нет устройств ввода!')
except ImportError:
    print('sounddevice не установлен: sudo apt install python3-sounddevice')
except Exception as e:
    print(f'Ошибка: {e}')
PYEOF
echo ''
echo '=== ТЕСТОВАЯ ЗАПИСЬ через arecord (3 сек) ==='
TMP=$(mktemp /tmp/test_audio_XXXXXX.wav)
timeout 10 arecord -D default -d 3 -f S16_LE -r 44100 -c 1 "$TMP" 2>&1
RC=$?
if [ $RC -eq 0 ] && [ -s "$TMP" ]; then
    SIZE=$(stat -c%s "$TMP")
    echo "OK: файл записан, размер ${SIZE} байт"
    rm -f "$TMP"
else
    echo "ОШИБКА arecord (код $RC) — микрофон не найден или занят"
    rm -f "$TMP"
fi
""".strip(),
        "timeout": 35,
    },

}


# ---------------------------------------------------------------------------
# Device diagnostics
# ---------------------------------------------------------------------------

def get_system_diagnostics() -> dict:
    """Collect CPU temp, usage, memory, disk, uptime."""
    diag = {
        "firmware_version": FIRMWARE_VERSION,
        "model_version":    MODEL_VERSION,
        "os_version":       platform.platform(),
        "python_version":   platform.python_version(),
    }
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            diag["cpu_temp"] = round(int(f.read().strip()) / 1000, 1)
    except Exception:
        diag["cpu_temp"] = None

    try:
        import psutil
        diag["cpu_usage"]        = psutil.cpu_percent(interval=1)
        mem                      = psutil.virtual_memory()
        diag["memory_total_mb"]  = mem.total  // (1024 * 1024)
        diag["memory_used_mb"]   = mem.used   // (1024 * 1024)
        disk                     = psutil.disk_usage("/")
        diag["disk_total_gb"]    = round(disk.total / (1024 ** 3), 2)
        diag["disk_used_gb"]     = round(disk.used  / (1024 ** 3), 2)
        diag["memory_usage_pct"] = round(mem.percent,  1)
        diag["disk_usage_pct"]   = round(disk.percent, 1)
        diag["uptime_seconds"]   = int(time.time() - psutil.boot_time())
    except ImportError:
        log.warning("psutil not available, skipping detailed metrics")

    return diag


# ---------------------------------------------------------------------------
# Audio recording
# ---------------------------------------------------------------------------

def record_audio(duration_sec: int, output_path: str) -> bool:
    try:
        import sounddevice as sd
        import soundfile  as sf

        log.info("Recording audio for %ds...", duration_sec)
        audio = sd.rec(
            int(duration_sec * SAMPLE_RATE),
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32",
        )
        sd.wait()
        sf.write(output_path, audio, SAMPLE_RATE)
        log.info("Audio saved: %s (%.1f KB)", output_path, Path(output_path).stat().st_size / 1024)
        return True
    except Exception as e:
        log.error("Audio recording failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# ML model inference (stub — replace with actual model)
# ---------------------------------------------------------------------------

def run_inference(audio_path: str) -> dict:
    """
    Run local ML model on audio file.
    STUB: replace with real onnx/tflite inference.
    """
    import random
    classes = ["normal","noise","grinding","squeak","knock","whistle","foreign_sounds","speech","other_anomaly"]
    dominant_idx = random.randint(0, len(classes) - 1)
    scores = {}
    for i, cls in enumerate(classes):
        scores[cls] = round(random.uniform(0.4, 0.95) if i == dominant_idx else random.uniform(0.01, 0.15), 4)
    total = sum(scores.values())
    scores = {k: round(v / total, 4) for k, v in scores.items()}
    log.info("Inference: dominant=%s (%.3f)", max(scores, key=scores.get), max(scores.values()))
    return scores


def _fallback_analysis() -> dict:
    return {
        "normal":0.92,"noise":0.02,"grinding":0.01,"squeak":0.01,"knock":0.01,
        "whistle":0.01,"foreign_sounds":0.01,"speech":0.005,"other_anomaly":0.005,
    }


# ---------------------------------------------------------------------------
# API communication
# ---------------------------------------------------------------------------

def _headers() -> dict:
    return {"X-Device-Key": DEVICE_AUTH_KEY, "Accept": "application/json"}


def send_heartbeat(diag: dict) -> dict | None:
    """Send heartbeat; returns server response dict (includes tunnel ports) or None."""
    try:
        resp = requests.post(f"{SERVER_URL}/api/v1/device/heartbeat/",
                             json=diag, headers=_headers(), timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            log.info("Heartbeat sent OK (ssh_port=%s)", data.get("tunnel_port"))
            return data
        log.warning("Heartbeat failed: %d %s", resp.status_code, resp.text[:100])
    except requests.RequestException as e:
        log.error("Heartbeat network error: %s", e)
    return None


def send_packet(recorded_at, analysis, diag, audio_path=None, urgent=False) -> dict | None:
    endpoint = "critical" if urgent else "packet"
    url = f"{SERVER_URL}/api/v1/device/{endpoint}/"

    audio_meta = {}
    if audio_path and Path(audio_path).exists():
        stat = Path(audio_path).stat()
        audio_meta = {
            "sample_rate": SAMPLE_RATE, "channels": CHANNELS,
            "format": AUDIO_FORMAT, "file_size_bytes": stat.st_size,
        }

    payload = {
        "recorded_at":      recorded_at,
        "duration_seconds": float(RECORD_DURATION_SEC),
        "analysis":         analysis,
        "device_state": {
            "cpu_temp":         diag.get("cpu_temp"),
            "cpu_usage":        diag.get("cpu_usage"),
            "memory_usage_pct": diag.get("memory_usage_pct"),
            "disk_usage_pct":   diag.get("disk_usage_pct"),
            "firmware_version": FIRMWARE_VERSION,
            "model_version":    MODEL_VERSION,
            "audio_upload_enabled": not DISABLE_AUDIO_UPLOAD,
        },
        "audio_meta": audio_meta,
    }

    try:
        # Upload audio file only if not disabled
        if audio_path and Path(audio_path).exists() and not DISABLE_AUDIO_UPLOAD:
            with open(audio_path, "rb") as f:
                resp = requests.post(
                    url,
                    data={"data": json.dumps(payload)},
                    files={"audio_file": (Path(audio_path).name, f, "audio/wav")},
                    headers=_headers(), timeout=60,
                )
        else:
            if DISABLE_AUDIO_UPLOAD:
                log.info("Audio upload disabled — sending analysis only")
            resp = requests.post(
                url,
                json=payload,
                headers={**_headers(), "Content-Type": "application/json"},
                timeout=30,
            )

        if resp.status_code in (200, 201):
            data = resp.json()
            log.info("Packet sent OK: id=%s severity=%s has_anomaly=%s",
                     data.get("packet_id"), data.get("severity"), data.get("has_anomaly"))
            return data
        log.warning("Packet failed: %d %s", resp.status_code, resp.text[:200])
    except requests.RequestException as e:
        log.error("Packet network error: %s", e)
    return None


def report_version() -> bool:
    try:
        resp = requests.post(
            f"{SERVER_URL}/api/v1/device/version/",
            json={
                "firmware_version": FIRMWARE_VERSION,
                "model_version":    MODEL_VERSION,
                "os_version":       platform.platform(),
                "python_version":   platform.python_version(),
            },
            headers=_headers(), timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        log.error("Version report failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# SSH reverse tunnel
# ---------------------------------------------------------------------------

def _open_tunnel(remote_port: int, local_port: int, label: str) -> subprocess.Popen | None:
    """Open a single autossh reverse tunnel: remote_port → localhost:local_port."""
    if not TUNNEL_REMOTE_HOST:
        return None
    if not Path(TUNNEL_KEY_PATH).exists():
        log.error("Tunnel key not found: %s", TUNNEL_KEY_PATH)
        return None

    use_autossh = shutil.which("autossh") is not None
    base = "autossh" if use_autossh else "ssh"

    cmd = [base]
    if use_autossh:
        cmd += ["-M", "0"]

    cmd += [
        "-N",
        "-R", f"{remote_port}:localhost:{local_port}",
        f"tunnel@{TUNNEL_REMOTE_HOST}",
        "-p", str(TUNNEL_REMOTE_PORT),
        "-i", TUNNEL_KEY_PATH,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "BatchMode=yes",
    ]

    log.info("Opening %s tunnel: localhost:%d → %s:%d", label, local_port, TUNNEL_REMOTE_HOST, remote_port)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(3)
        if proc.poll() is not None:
            log.error("%s tunnel exited: %s", label, proc.stderr.read().decode(errors="replace"))
            return None
        log.info("%s tunnel established (pid=%d)", label, proc.pid)
        return proc
    except FileNotFoundError:
        log.error("'%s' not found — install with: sudo apt install %s", base, base)
        return None


def open_tunnels(ssh_port: int | None) -> subprocess.Popen | None:
    """
    Open SSH reverse tunnel to the server.
    Always-on: called regardless of whether an operator session exists.
    Returns ssh_proc.
    """
    return _open_tunnel(ssh_port, LOCAL_SSH_PORT, "SSH") if ssh_port else None


def close_tunnel(proc: subprocess.Popen | None):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.info("Tunnel closed (pid=%d)", proc.pid)


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

def poll_commands() -> list:
    try:
        resp = requests.get(
            f"{SERVER_URL}/api/v1/device/commands/",
            headers=_headers(), timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("commands", [])
    except Exception as e:
        log.debug("Command poll error: %s", e)
    return []


def execute_command(cmd: dict) -> tuple[str, int]:
    key     = cmd.get("command_key", "")

    # ── Special case: record_now ───────────────────────────────────────────
    # The shell-script approach (create trigger file, wait for it to vanish)
    # dead-locks: execute_command() blocks the main loop, so the trigger
    # is never processed.  Instead, set the flag from Python and return
    # immediately — the main loop will pick it up within ≤5 seconds.
    if key == "record_now":
        try:
            Path(RECORD_TRIGGER_FILE).touch()
            log.info("record_now: trigger file created at %s", RECORD_TRIGGER_FILE)
            return (
                "Триггер записи создан: " + RECORD_TRIGGER_FILE + "\n"
                "Edge client запустит запись в течение 5–35 секунд.\n"
                "OK"
            ), 0
        except OSError as exc:
            msg = f"Не удалось создать файл триггера: {exc}"
            log.error(msg)
            return msg, 1

    cmd_def = _CMD_CATALOG.get(key)

    if not cmd_def:
        return f"Неизвестная команда: '{key}'.\nДоступные: {', '.join(_CMD_CATALOG)}", 1

    script  = cmd_def["script"]
    timeout = cmd_def.get("timeout", 30)

    log.info("Executing command: %s (timeout=%ds)", key, timeout)

    try:
        # Use setsid so the shell and ALL its children share a process group.
        # This lets us kill the whole group on timeout — avoiding the classic
        # "subprocess.run(shell=True, timeout=…) hangs forever" bug where
        # bash is killed but orphaned children (pip3, etc.) keep the pipe open.
        proc = subprocess.Popen(
            script,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            executable="/bin/bash",
            preexec_fn=os.setsid,
        )
        try:
            stdout_b, stderr_b = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                proc.kill()
            stdout_b, stderr_b = proc.communicate()
            msg = f"Команда '{key}' превысила таймаут {timeout}с"
            log.warning(msg)
            return msg, 124

        output = stdout_b.decode("utf-8", errors="replace")
        if stderr_b:
            output += "\n--- stderr ---\n" + stderr_b.decode("utf-8", errors="replace")
        rc = proc.returncode
        log.info("Command %s done: rc=%d len=%d", key, rc, len(output))
        return output.strip(), rc

    except Exception as e:
        msg = f"Исключение при выполнении '{key}': {e}"
        log.error(msg)
        return msg, 1


def report_command_result(command_id: str, output: str, exit_code: int) -> bool:
    try:
        resp = requests.post(
            f"{SERVER_URL}/api/v1/device/commands/{command_id}/result/",
            json={"output": output, "exit_code": exit_code},
            headers=_headers(), timeout=15,
        )
        return resp.status_code == 200
    except Exception as e:
        log.error("Error reporting command result: %s", e)
    return False


def process_pending_commands():
    commands = poll_commands()
    if not commands:
        return
    log.info("Executing %d command(s)", len(commands))
    for cmd in commands:
        cmd_id = cmd.get("id")
        if not cmd_id:
            continue
        output, exit_code = execute_command(cmd)
        for attempt in range(3):
            if report_command_result(cmd_id, output, exit_code):
                break
            if attempt < 2:
                time.sleep(5)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    if not DEVICE_AUTH_KEY:
        sys.exit("ERROR: DEVICE_AUTH_KEY not set.")

    log.info("=== PumpJack Edge Client starting ===")
    log.info("Server: %s | FW: %s | Model: %s", SERVER_URL, FIRMWARE_VERSION, MODEL_VERSION)
    if DISABLE_AUDIO_UPLOAD:
        log.info("Audio upload: DISABLED (analysis-only mode)")
    log.info("Packet interval: %dh", PACKET_INTERVAL_SEC // 3600)

    report_version()

    last_packet_time       = 0
    last_heartbeat_time    = 0
    last_tunnel_check_time = 0
    last_command_poll_time = 0

    ssh_tunnel: subprocess.Popen | None = None

    # Tunnel port from server (received in heartbeat response)
    assigned_ssh_port: int | None = None

    while True:
        now = time.time()

        # ── Heartbeat ──────────────────────────────────────────────────────
        if now - last_heartbeat_time >= HEARTBEAT_INTERVAL_SEC:
            diag = get_system_diagnostics()
            hb_data = send_heartbeat(diag)
            if hb_data:
                # Server tells us our assigned tunnel ports
                new_ssh = hb_data.get("tunnel_port")
                if new_ssh and new_ssh != assigned_ssh_port:
                    log.info("SSH tunnel port (re)assigned: %s", new_ssh)
                    # Port changed — close old tunnel so it reopens with new port
                    close_tunnel(ssh_tunnel)
                    ssh_tunnel = None
                    assigned_ssh_port = new_ssh
            last_heartbeat_time = now

        # ── Audio packet (every 3 hours OR trigger file) ───────────────────
        trigger_file_exists = Path(RECORD_TRIGGER_FILE).exists()
        if trigger_file_exists or (now - last_packet_time >= PACKET_INTERVAL_SEC):
            if trigger_file_exists:
                log.info("Record-now trigger detected: %s", RECORD_TRIGGER_FILE)
                try:
                    Path(RECORD_TRIGGER_FILE).unlink()
                except OSError:
                    pass

            diag        = get_system_diagnostics()
            recorded_at = datetime.now(timezone.utc).isoformat()

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                audio_path = tmp.name

            try:
                recorded  = record_audio(RECORD_DURATION_SEC, audio_path)
                if not recorded:
                    audio_path = None

                analysis      = run_inference(audio_path) if audio_path else _fallback_analysis()
                dominant      = max(analysis, key=analysis.get)
                dominant_score = analysis[dominant]

                urgent = (
                    dominant in ("grinding", "knock", "whistle")
                    and dominant_score >= CRITICAL_SCORE_THRESHOLD
                )
                if urgent:
                    log.warning("CRITICAL: %s=%.3f — sending urgent packet", dominant, dominant_score)

                result = send_packet(
                    recorded_at=recorded_at,
                    analysis=analysis,
                    diag=diag,
                    audio_path=audio_path,
                    urgent=urgent,
                )
                if result:
                    last_packet_time = now

            finally:
                if audio_path and Path(audio_path).exists():
                    Path(audio_path).unlink(missing_ok=True)

        # ── Always-on reverse SSH tunnel ──────────────────────────────────
        # Checked every 60 s; reopened automatically if it dies.
        # Tunnel port is learned from the heartbeat response.
        if now - last_tunnel_check_time >= REMOTE_POLL_INTERVAL_SEC:
            # Check SSH tunnel health
            if ssh_tunnel and ssh_tunnel.poll() is not None:
                log.info("SSH tunnel exited (rc=%d), will reopen", ssh_tunnel.returncode)
                ssh_tunnel = None

            # (Re)open if we have a port and tunnel is not running
            if assigned_ssh_port and not ssh_tunnel:
                ssh_tunnel = open_tunnels(assigned_ssh_port)
                log.info("SSH tunnel %s (pid=%s)",
                         "opened" if ssh_tunnel else "FAILED",
                         ssh_tunnel.pid if ssh_tunnel else "—")
            if ssh_tunnel:
                log.debug("Tunnels active: SSH pid=%d", ssh_tunnel.pid)

            last_tunnel_check_time = now

        # ── Command dispatch ────────────────────────────────────────────────
        if now - last_command_poll_time >= COMMAND_POLL_INTERVAL_SEC:
            process_pending_commands()
            last_command_poll_time = now

        time.sleep(5)


if __name__ == "__main__":
    main()
