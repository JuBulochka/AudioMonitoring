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
    User.objects.create_superuser('admin', 'admin@pumpjack.local', 'admin1234567', role='admin', employee_number='ADM-0001')
    print('Superuser created: admin / admin1234567')
else:
    admin = User.objects.get(username='admin')
    if not admin.employee_number:
        admin.employee_number = 'ADM-0001'
        admin.save(update_fields=['employee_number'])
    print('Superuser already exists.')
"

# Ключ платформы нужен веб-терминалу для входа на Raspberry Pi через reverse-туннель.
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

# Ключ туннеля используется Raspberry Pi для подключения к sshd-контейнеру.
if [ ! -f "$PLATFORM_KEY_DIR/tunnel_key" ]; then
    ssh-keygen -t ed25519 -f "$PLATFORM_KEY_DIR/tunnel_key" -N "" -q -C "pumpjack-tunnel"
    chmod 600 "$PLATFORM_KEY_DIR/tunnel_key"
    chmod 644 "$PLATFORM_KEY_DIR/tunnel_key.pub"
    echo "==> Tunnel SSH key generated: $PLATFORM_KEY_DIR/tunnel_key"
    cp "$PLATFORM_KEY_DIR/tunnel_key.pub" /app/docker/sshd/authorized_keys
    chmod 644 /app/docker/sshd/authorized_keys
    echo "==> Tunnel pubkey installed into sshd authorized_keys"
else
    echo "==> Tunnel SSH key already exists"
    cp "$PLATFORM_KEY_DIR/tunnel_key.pub" /app/docker/sshd/authorized_keys
    chmod 644 /app/docker/sshd/authorized_keys
fi

exec "$@"
