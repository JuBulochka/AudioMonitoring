"""Global template context processors."""


def global_context(request):
    """Inject global context into all templates."""
    unread_count = 0
    if request.user.is_authenticated:
        from apps.alerts.models import Notification
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False,
            is_dismissed=False,
        ).count()

    return {
        "unread_notifications_count": unread_count,
    }
