"""Alert Celery tasks."""
import logging

from celery import shared_task

logger = logging.getLogger("apps.alerts")


@shared_task(name="apps.alerts.tasks.send_alert_digest")
def send_alert_digest():
    """
    Every 30 minutes: send email digest of unread critical notifications
    to users who have email notifications enabled.
    """
    from django.conf import settings
    if not settings.CRITICAL_ALERT_EMAIL_ENABLED:
        return

    from apps.alerts.models import Notification
    from apps.users.models import User, UserRole
    from django.utils import timezone
    from datetime import timedelta
    from django.core.mail import send_mail

    window = timezone.now() - timedelta(minutes=30)
    users_with_pending = (
        Notification.objects
        .filter(
            is_read=False,
            created_at__gte=window,
            alert__severity="critical",
        )
        .values_list("user_id", flat=True)
        .distinct()
    )

    for user_id in users_with_pending:
        try:
            user = User.objects.get(id=user_id, is_active=True)
            if not getattr(user, "profile", None) or not user.profile.notify_email:
                continue

            notifs = Notification.objects.filter(
                user=user,
                is_read=False,
                created_at__gte=window,
                alert__severity="critical",
            ).select_related("alert__device")

            if not notifs.exists():
                continue

            lines = [f"• {n.alert.title} ({n.alert.device.serial_number if n.alert.device else 'N/A'})" for n in notifs]
            body = "Критические события за последние 30 минут:\n\n" + "\n".join(lines)

            send_mail(
                subject=f"[PumpJack Monitor] {notifs.count()} критических событий",
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            logger.info("Alert digest sent to %s (%d items)", user.email, notifs.count())
        except Exception as e:
            logger.exception("Alert digest error for user %s: %s", user_id, e)
