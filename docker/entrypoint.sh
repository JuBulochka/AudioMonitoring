#!/bin/bash
set -e

echo "==> Waiting for PostgreSQL..."
until python -c "import psycopg2; psycopg2.connect(
  dbname='$DB_NAME', user='$DB_USER', password='$DB_PASSWORD',
  host='$DB_HOST', port='$DB_PORT'
)" 2>/dev/null; do
  sleep 1
done
echo "==> PostgreSQL is ready."

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Creating superuser if not exists..."
python manage.py shell -c "
from apps.users.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@pumpjack.local', 'admin1234567', role='admin')
    print('Superuser created: admin / admin1234567')
else:
    print('Superuser already exists.')
"

# Generate platform SSH key (used by web terminal to SSH into Pi through reverse tunnel)
PLATFORM_KEY_DIR="/app/media/platform"
mkdir -p "$PLATFORM_KEY_DIR"
if [ ! -f "$PLATFORM_KEY_DIR/platform_key" ]; then
    ssh-keygen -t ed25519 -f "$PLATFORM_KEY_DIR/platform_key" -N "" -q -C "pumpjack-platform"
    chmod 600 "$PLATFORM_KEY_DIR/platform_key"
    chmod 644 "$PLATFORM_KEY_DIR/platform_key.pub"
    echo "==> Platform SSH key generated: $PLATFORM_KEY_DIR/platform_key"
else
    echo "==> Platform SSH key already exists"
fi

# Generate tunnel SSH key (used by Pi to establish reverse tunnel into sshd container)
if [ ! -f "$PLATFORM_KEY_DIR/tunnel_key" ]; then
    ssh-keygen -t ed25519 -f "$PLATFORM_KEY_DIR/tunnel_key" -N "" -q -C "pumpjack-tunnel"
    chmod 600 "$PLATFORM_KEY_DIR/tunnel_key"
    chmod 644 "$PLATFORM_KEY_DIR/tunnel_key.pub"
    echo "==> Tunnel SSH key generated: $PLATFORM_KEY_DIR/tunnel_key"
    # Write public key to sshd authorized_keys so all Pis can establish tunnels
    cp "$PLATFORM_KEY_DIR/tunnel_key.pub" /app/docker/sshd/authorized_keys
    chmod 644 /app/docker/sshd/authorized_keys
    echo "==> Tunnel pubkey installed into sshd authorized_keys"
else
    echo "==> Tunnel SSH key already exists"
    # Ensure pubkey is in authorized_keys (idempotent)
    cp "$PLATFORM_KEY_DIR/tunnel_key.pub" /app/docker/sshd/authorized_keys
    chmod 644 /app/docker/sshd/authorized_keys
fi

exec "$@"
