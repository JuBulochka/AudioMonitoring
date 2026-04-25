"""Celery application configuration."""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("pumpjack")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# ---------------------------------------------------------------------------
# Periodic task schedule
# ---------------------------------------------------------------------------
app.conf.beat_schedule = {
    # Check for offline devices every 5 minutes
    "check-offline-devices": {
        "task": "apps.devices.tasks.check_offline_devices",
        "schedule": crontab(minute="*/5"),
    },
    # Generate daily aggregated metrics at 00:05 UTC
    "aggregate-daily-metrics": {
        "task": "apps.packets.tasks.aggregate_daily_metrics",
        "schedule": crontab(hour=0, minute=5),
    },
    # Purge audio packets older than AUDIO_RETENTION_DAYS — runs at 02:00 UTC
    "purge-old-packets": {
        "task": "apps.packets.tasks.purge_old_packets",
        "schedule": crontab(hour=2, minute=0),
    },
    # Send unacknowledged alert digests every 30 minutes
    "send-alert-digest": {
        "task": "apps.alerts.tasks.send_alert_digest",
        "schedule": crontab(minute="*/30"),
    },
    # Detect devices with frequent anomalies — hourly
    "detect-frequent-anomalies": {
        "task": "apps.incidents.tasks.detect_frequent_anomalies",
        "schedule": crontab(minute=10),
    },
    # Expire stale remote-access sessions every 10 minutes
    "expire-remote-sessions": {
        "task": "apps.remote_access.tasks.expire_stale_sessions",
        "schedule": crontab(minute="*/10"),
    },
    # Health-check all devices — every hour
    "device-health-sweep": {
        "task": "apps.devices.tasks.device_health_sweep",
        "schedule": crontab(minute=30),
    },
    # Clean up audit log entries older than 1 year — weekly
    "purge-audit-log": {
        "task": "apps.common.tasks.purge_old_audit_logs",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
