"""Celery application configuration."""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("pumpjack")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


app.conf.beat_schedule = {
    "check-offline-devices": {
        "task": "apps.devices.tasks.check_offline_devices",
        "schedule": crontab(minute="*/5"),
    },
    "aggregate-daily-metrics": {
        "task": "apps.packets.tasks.aggregate_daily_metrics",
        "schedule": crontab(hour=0, minute=5),
    },
    "purge-old-packets": {
        "task": "apps.packets.tasks.purge_old_packets",
        "schedule": crontab(hour=2, minute=0),
    },
    "send-alert-digest": {
        "task": "apps.alerts.tasks.send_alert_digest",
        "schedule": crontab(minute="*/30"),
    },
    "detect-frequent-anomalies": {
        "task": "apps.incidents.tasks.detect_frequent_anomalies",
        "schedule": crontab(minute=10),
    },
    "expire-remote-sessions": {
        "task": "apps.remote_access.tasks.expire_stale_sessions",
        "schedule": crontab(minute="*/10"),
    },
    "device-health-sweep": {
        "task": "apps.devices.tasks.device_health_sweep",
        "schedule": crontab(minute=30),
    },
    "purge-audit-log": {
        "task": "apps.common.tasks.purge_old_audit_logs",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
