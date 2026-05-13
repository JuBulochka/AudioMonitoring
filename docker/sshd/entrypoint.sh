#!/bin/bash
set -e

# Каждый запуск возвращает актуальный sshd_config из образа.
cp /etc/sshd_config.image /etc/ssh/sshd_config

# bind-mounted authorized_keys копируется во временный файл с правами, подходящими для sshd.
KEYS_SRC="/home/tunnel/.ssh/authorized_keys"
KEYS_WRITABLE="/tmp/authorized_keys"

if [ -f "$KEYS_SRC" ]; then
    cp "$KEYS_SRC" "$KEYS_WRITABLE"
else
    touch "$KEYS_WRITABLE"
    echo "==> WARNING: docker/sshd/authorized_keys is empty. Add Pi public key and restart."
fi
chmod 600 "$KEYS_WRITABLE"
chown tunnel:tunnel "$KEYS_WRITABLE"

sed -i "s|AuthorizedKeysFile .*|AuthorizedKeysFile $KEYS_WRITABLE|" /etc/ssh/sshd_config

COUNT=$(grep -cve '^\s*#' "$KEYS_WRITABLE" 2>/dev/null | tr -d ' ' || echo 0)
echo "==> Loaded $COUNT authorized key(s)"

# Host keys хранятся в volume, поэтому генерируются только при первом запуске.
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    echo "==> Generating SSH host keys..."
    ssh-keygen -t rsa -b 4096 -f /etc/ssh/ssh_host_rsa_key -N "" -q
    ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key -N "" -q
fi

echo "==> SSH jump server starting on port 22 (mapped to host 2222)"
echo "==> Reverse tunnel ports: 20001-20020"
exec /usr/sbin/sshd -D -e
