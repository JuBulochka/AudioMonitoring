"""Alert / Notification web views."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

from .models import Notification, Alert


@login_required
def notifications(request):
    qs = Notification.objects.filter(
        user=request.user, is_dismissed=False
    ).select_related("alert__device").order_by("-created_at")

    unread_only = request.GET.get("unread_only") == "1"
    if unread_only:
        qs = qs.filter(is_read=False)

    ctx = {
        "notifications": qs[:200],
        "unread_only": unread_only,
        "unread_count": qs.filter(is_read=False).count(),
    }
    return render(request, "alerts/notifications.html", ctx)
