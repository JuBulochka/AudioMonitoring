# PumpJack Audio Monitor — Инструкции по запуску

## Быстрый старт через Docker (рекомендуется)

```bash
# 1. Клонируй/открой директорию проекта
cd kursachAudio

# 2. Создай .env из примера
cp .env.example .env

# 3. Запусти все сервисы
docker compose up --build -d

# 4. Следи за логами
docker compose logs -f web

# 5. Открой браузер
# http://localhost/          — веб-интерфейс (через nginx)
# http://localhost:8000/     — Django напрямую
# http://localhost:8000/admin/    — Админка
# http://localhost:8000/api/docs/ — Swagger UI
```

**Учётные данные по умолчанию:**
- `admin` / `admin1234567` — суперпользователь
- `operator1` / `demo1234567` — оператор
- `supervisor1` / `demo1234567` — супервайзер

---

## Локальный запуск (без Docker)

### Требования
- Python 3.12+
- PostgreSQL 14+
- Redis 7+

```bash
# Создай виртуальное окружение
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Установи зависимости
pip install -r requirements.txt

# Настрой .env
cp .env.example .env
# Отредактируй .env: DB_HOST=localhost, REDIS_URL=redis://localhost:6379/0

# Создай базу данных
psql -U postgres -c "CREATE USER pumpjack WITH PASSWORD 'pumpjack_secret';"
psql -U postgres -c "CREATE DATABASE pumpjack_db OWNER pumpjack;"

# Миграции
python manage.py migrate

# Загрузи тестовые данные
python manage.py load_demo_data

# Создай суперпользователя (если нет)
python manage.py createsuperuser

# Запусти Django
python manage.py runserver 0.0.0.0:8000

# В отдельном терминале — Celery worker
celery -A config.celery worker --loglevel=info

# В отдельном терминале — Celery Beat (планировщик)
celery -A config.celery beat --loglevel=info
```

---

## Структура проекта

```
kursachAudio/
├── config/                    # Django config
│   ├── settings/
│   │   ├── base.py           # Общие настройки
│   │   ├── development.py    # Dev настройки
│   │   └── production.py     # Prod настройки
│   ├── celery.py             # Celery конфиг + расписание
│   ├── urls.py               # Корневые URL
│   ├── asgi.py               # ASGI (WebSocket)
│   └── wsgi.py
├── apps/
│   ├── users/                # Пользователи и роли
│   ├── devices/              # Устройства, регионы, heartbeat
│   ├── packets/              # Аудиопакеты и анализ
│   ├── incidents/            # Инциденты и обслуживание
│   ├── alerts/               # Уведомления + WebSocket
│   ├── remote_access/        # Удалённый доступ
│   ├── dashboard/            # Дашборд
│   └── common/               # Утилиты, middleware, audit log
├── api/v1/                   # REST API endpoints
├── templates/                # Django HTML templates
├── static/                   # CSS/JS
├── scripts/
│   └── edge_client.py        # Клиент для Raspberry Pi
├── tests/
│   └── test_api.py
├── docker/
│   ├── entrypoint.sh
│   └── nginx.conf
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## API Endpoints — краткий справочник

### Device API (аутентификация по заголовку `X-Device-Key`)

| Метод | URL | Назначение |
|-------|-----|------------|
| POST | `/api/v1/device/heartbeat/` | Heartbeat от устройства |
| POST | `/api/v1/device/packet/` | Загрузка аудиопакета |
| POST | `/api/v1/device/critical/` | Срочное критическое событие |
| POST | `/api/v1/device/version/` | Отчёт о версии ПО |
| GET  | `/api/v1/device/remote-poll/` | Опрос: есть ли токен удалённого доступа |
| POST | `/api/v1/device/remote-confirm/` | Подтверждение открытого туннеля |

### Operator API (JWT Bearer или Session)

| Метод | URL | Назначение |
|-------|-----|------------|
| GET | `/api/v1/devices/` | Список устройств |
| GET | `/api/v1/devices/<id>/` | Карточка устройства |
| PATCH | `/api/v1/devices/<id>/status/` | Сменить статус |
| GET/POST | `/api/v1/devices/<id>/comments/` | Комментарии |
| GET | `/api/v1/packets/?device=<id>` | Пакеты устройства |
| PATCH | `/api/v1/packets/<id>/review/` | Верификация пакета |
| GET | `/api/v1/incidents/` | Список инцидентов |
| PATCH | `/api/v1/incidents/<id>/status/` | Сменить статус инцидента |
| GET | `/api/v1/alerts/notifications/` | Уведомления |
| POST | `/api/v1/alerts/notifications/mark-all-read/` | Прочитать все |
| POST | `/api/v1/remote-access/request/` | Запрос удалённого доступа |
| GET | `/api/v1/map/devices/` | Точки для карты |
| GET | `/api/v1/dashboard/summary/` | Сводная статистика |
| GET | `/health/live/` | Liveness probe |
| GET | `/health/ready/` | Readiness probe |

---

## Тестирование

```bash
# Запуск тестов
pytest tests/ -v

# С покрытием
pytest tests/ --cov=apps --cov-report=html
```

---

## Имитация устройства (Raspberry Pi)

```bash
# Пример heartbeat
curl -X POST http://localhost:8000/api/v1/device/heartbeat/ \
  -H "X-Device-Key: <auth_key>" \
  -H "Content-Type: application/json" \
  -d '{"cpu_temp": 52.3, "cpu_usage": 18.5, "memory_total_mb": 4096,
       "memory_used_mb": 1820, "disk_total_gb": 32.0, "disk_used_gb": 7.4,
       "firmware_version": "1.3.2", "model_version": "0.9.4", "uptime_seconds": 86400}'

# Пример отправки пакета
curl -X POST http://localhost:8000/api/v1/device/packet/ \
  -H "X-Device-Key: <auth_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "recorded_at": "2026-04-13T10:00:00Z",
    "duration_seconds": 30.0,
    "analysis": {
      "normal": 0.05, "noise": 0.10, "grinding": 0.75,
      "squeak": 0.02, "knock": 0.03, "whistle": 0.01,
      "foreign_sounds": 0.01, "speech": 0.01, "other_anomaly": 0.02
    },
    "device_state": {
      "cpu_temp": 52.3, "cpu_usage": 18.5,
      "memory_usage_pct": 44.5, "disk_usage_pct": 23.1,
      "firmware_version": "1.3.2", "model_version": "0.9.4"
    },
    "audio_meta": {"sample_rate": 44100, "channels": 1, "format": "wav", "file_size_bytes": 1234567}
  }'

# Получить auth_key для устройства
# Откройте /admin/ → Devices → выберите устройство → скопируйте auth_key
```

---

## Edge Client на Raspberry Pi

```bash
# Установка
pip install requests sounddevice soundfile numpy psutil

# Запуск
export DEVICE_AUTH_KEY="ваш-ключ-устройства"
export SERVER_URL="https://ваш-сервер.ru"
export FIRMWARE_VERSION="1.3.2"
export MODEL_VERSION="0.9.4"

python scripts/edge_client.py
```

---

## Масштабирование

- **>1000 устройств**: добавить range-partitioning для `packets_audio_packet` по `recorded_at`
- **Файлы**: переключить `STORAGE_BACKEND=s3` + MinIO/AWS S3
- **Воркеры Celery**: масштабировать горизонтально через `--concurrency`
- **База**: read-replica PostgreSQL для аналитических запросов
- **Nginx**: `upstream` с несколькими gunicorn-инстансами
