"""Remote access Celery tasks."""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("apps.remote_access")


@shared_task(name="apps.remote_access.tasks.expire_stale_sessions")
def expire_stale_sessions():
    """Every 10 minutes: expire sessions whose token TTL has passed."""
    from apps.remote_access.models import RemoteAccessSession, RemoteAccessStatus

    stale = RemoteAccessSession.objects.filter(
        status__in=[RemoteAccessStatus.APPROVED, RemoteAccessStatus.ACTIVE],
        token_expires_at__lt=timezone.now(),
    )
    count = stale.count()
    for session in stale:
        session.expire()

    logger.info("Expired %d stale remote access sessions", count)
    return count
