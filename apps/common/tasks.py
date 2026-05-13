"""Общие фоновые задачи проекта."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("apps.common")


@shared_task(name="apps.common.tasks.purge_old_audit_logs")
def purge_old_audit_logs():
    """Удаляет записи аудита старше года."""
    from apps.common.models import AuditLog
    cutoff = timezone.now() - timedelta(days=365)
    count, _ = AuditLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info("Purged %d old audit log entries", count)
    return count
