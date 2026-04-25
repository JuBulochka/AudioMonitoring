#!/bin/bash
# =============================================================================
# PumpJack Audio Monitor — Raspberry Pi 4 Setup Script
# =============================================================================
# Run as root or with sudo on a fresh Raspberry Pi OS Lite (64-bit) install.
#
# What this script does:
#   1. Updates system packages
#   2. Installs autossh, python3, pip, ffmpeg, portaudio
#   3. Creates /opt/pumpjack/ working directory
#   4. Installs Python dependencies
#   5. Generates SSH key pair for reverse tunnel authentication
#   6. Creates /opt/pumpjack/.env config file
#   7. Installs edge_client.py systemd service (auto-start on boot)
#   8. Prints setup summary and next steps
#
# Usage:
#   sudo bash pi_setup.sh
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC}  $*"; exit 1; }

# ---- Must run as root -------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
    error "Run as root: sudo bash pi_setup.sh"
fi

# ---- Detect script directory ------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "============================================================"
echo "  PumpJack Audio Monitor — Raspberry Pi Setup"
echo "============================================================"
echo ""

# ---- Interactive config collection -----------------------------------------
read -rp "Server URL (e.g. http://192.168.1.100): " SERVER_URL
SERVER_URL="${SERVER_URL%/}"

read -rp "Device Auth Key (copy from Admin → Devices → auth_key): " DEVICE_AUTH_KEY

read -rp "Tunnel Remote Host (server IP/hostname, same as above): " TUNNEL_REMOTE_HOST

read -rp "Pi username [pi]: " PI_USER
PI_USER="${PI_USER:-pi}"

read -rp "Firmware version [1.3.2]: " FIRMWARE_VERSION
FIRMWARE_VERSION="${FIRMWARE_VERSION:-1.3.2}"

read -rp "Model version [0.9.4]: " MODEL_VERSION
MODEL_VERSION="${MODEL_VERSION:-0.9.4}"

echo ""

# ---- System update ----------------------------------------------------------
info "Updating package lists..."
apt-get update -qq

info "Installing system dependencies..."
apt-get install -y -q \
    autossh \
    python3 \
    python3-pip \
    python3-venv \
    portaudio19-dev \
    libopenblas-dev \
    ffmpeg \
    curl \
    git

success "System packages installed"

# ---- Create working directory -----------------------------------------------
INSTALL_DIR="/opt/pumpjack"
info "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/.ssh"
chmod 700 "$INSTALL_DIR/.ssh"

# ---- Python virtualenv + dependencies ---------------------------------------
info "Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

info "Installing Python packages..."
pip install --quiet --upgrade pip
pip install --quiet \
    requests \
    psutil \
    sounddevice \
    soundfile \
    numpy

deactivate
success "Python environment ready"

# ---- Copy edge client -------------------------------------------------------
info "Installing edge client..."
if [ -f "$SCRIPT_DIR/edge_client.py" ]; then
    cp "$SCRIPT_DIR/edge_client.py" "$INSTALL_DIR/edge_client.py"
else
    warn "edge_client.py not found in $SCRIPT_DIR — download manually"
fi
chmod +x "$INSTALL_DIR/edge_client.py" 2>/dev/null || true
chown -R "$PI_USER:$PI_USER" "$INSTALL_DIR"

# ---- Generate SSH tunnel key ------------------------------------------------
TUNNEL_KEY="$INSTALL_DIR/.ssh/tunnel_key"

if [ -f "$TUNNEL_KEY" ]; then
    warn "Tunnel key already exists: $TUNNEL_KEY (skipping generation)"
else
    info "Generating SSH key pair for reverse tunnel..."
    sudo -u "$PI_USER" ssh-keygen \
        -t ed25519 \
        -f "$TUNNEL_KEY" \
        -C "pumpjack-tunnel@$(hostname)" \
        -N ""
    chmod 600 "$TUNNEL_KEY"
    chmod 644 "${TUNNEL_KEY}.pub"
    success "SSH key generated: $TUNNEL_KEY"
fi

TUNNEL_PUBKEY=$(cat "${TUNNEL_KEY}.pub")

# ---- Fetch platform public key from server ----------------------------------
# The platform (Django web) SSHes into Pi using this key for the web terminal.
# We fetch it from the server and add it to Pi's authorized_keys.
PI_HOME=$(eval echo "~$PI_USER")
AUTH_KEYS="$PI_HOME/.ssh/authorized_keys"

info "Fetching platform SSH public key from server..."
mkdir -p "$PI_HOME/.ssh"
chmod 700 "$PI_HOME/.ssh"

PLATFORM_PUBKEY=$(curl -sf \
    -H "X-Device-Key: $DEVICE_AUTH_KEY" \
    "$SERVER_URL/api/v1/device/platform-pubkey/" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['public_key'])" 2>/dev/null || echo "")

if [ -n "$PLATFORM_PUBKEY" ]; then
    touch "$AUTH_KEYS"
    # Avoid duplicates
    if ! grep -qF "$PLATFORM_PUBKEY" "$AUTH_KEYS" 2>/dev/null; then
        echo "$PLATFORM_PUBKEY" >> "$AUTH_KEYS"
        success "Platform public key added to $AUTH_KEYS"
    else
        success "Platform public key already in $AUTH_KEYS"
    fi
    chmod 600 "$AUTH_KEYS"
    chown "$PI_USER:$PI_USER" "$AUTH_KEYS"
else
    warn "Could not fetch platform key from $SERVER_URL — add it manually later:"
    warn "  curl -H 'X-Device-Key: \$DEVICE_AUTH_KEY' $SERVER_URL/api/v1/device/platform-pubkey/"
fi

# ---- Create config file -----------------------------------------------------
info "Creating config file: $INSTALL_DIR/.env"
cat > "$INSTALL_DIR/.env" <<EOF
# PumpJack Edge Client Configuration
# Generated by pi_setup.sh on $(date)

SERVER_URL=$SERVER_URL
DEVICE_AUTH_KEY=$DEVICE_AUTH_KEY

# Reverse SSH tunnel settings
TUNNEL_REMOTE_HOST=$TUNNEL_REMOTE_HOST
TUNNEL_REMOTE_PORT=2222
TUNNEL_KEY_PATH=$TUNNEL_KEY

# Device info
FIRMWARE_VERSION=$FIRMWARE_VERSION
MODEL_VERSION=$MODEL_VERSION

# Timing
HEARTBEAT_INTERVAL_SEC=300
PACKET_INTERVAL_SEC=10800
REMOTE_POLL_INTERVAL_SEC=60
COMMAND_POLL_INTERVAL_SEC=30
RECORD_DURATION_SEC=30
EOF

chmod 600 "$INSTALL_DIR/.env"
chown "$PI_USER:$PI_USER" "$INSTALL_DIR/.env"
success "Config file created"

# ---- Create systemd service -------------------------------------------------
info "Installing systemd service: pumpjack-edge..."
cat > /etc/systemd/system/pumpjack-edge.service <<EOF
[Unit]
Description=PumpJack Audio Monitor Edge Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$PI_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/edge_client.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pumpjack-edge

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pumpjack-edge
success "Systemd service installed and enabled"

# ---- Enable OpenSSH on Pi (for incoming tunnel connections from operators) --
info "Ensuring SSH daemon is enabled on Pi..."
systemctl enable ssh 2>/dev/null || systemctl enable sshd 2>/dev/null || true
systemctl start ssh 2>/dev/null || systemctl start sshd 2>/dev/null || true
success "SSH daemon enabled"

# ---- Summary ----------------------------------------------------------------
echo ""
echo "============================================================"
echo -e "  ${GREEN}Setup complete!${NC}"
echo "============================================================"
echo ""
echo -e "${YELLOW}ВАЖНО: Зарегистрируйте tunnel-ключ Pi на сервере${NC}"
echo ""
echo "  Добавьте этот публичный ключ в файл на сервере:"
echo "  docker/sshd/authorized_keys"
echo ""
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │ $TUNNEL_PUBKEY"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""
echo "  Затем перезапустите SSH jump server:"
echo "  docker compose restart sshd"
echo ""
echo -e "${BLUE}Управление edge client:${NC}"
echo "  Запустить:   sudo systemctl start pumpjack-edge"
echo "  Остановить:  sudo systemctl stop pumpjack-edge"
echo "  Логи:        sudo journalctl -u pumpjack-edge -f"
echo "  Конфиг:      sudo nano $INSTALL_DIR/.env"
echo ""
echo -e "${BLUE}Проверить туннель вручную:${NC}"
echo "  autossh -M 0 -N -R 30001:localhost:22 tunnel@$TUNNEL_REMOTE_HOST -p 2222 -i $TUNNEL_KEY"
echo ""
echo -e "${GREEN}Веб-терминал:${NC}"
echo "  После запуска edge_client и установки туннеля:"
echo "  Откройте платформу → Устройства → карточка устройства → кнопка [Терминал]"
echo "  SSH-сессия откроется прямо в браузере."
echo ""
