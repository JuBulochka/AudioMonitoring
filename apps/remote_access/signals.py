"""Сигналы для обслуживания журнала удаленного доступа."""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="remote_access.RemoteAccessSession")
def trim_session_log(sender, instance, created, **kwargs):
    """Оставляет в журнале только последние сессии, чтобы таблица не разрасталась."""
    if not created:
        return
    MAX_SESSIONS = 20
    qs = sender.objects.order_by("-created_at").values_list("id", flat=True)
    ids_to_keep = list(qs[:MAX_SESSIONS])
    if len(ids_to_keep) == MAX_SESSIONS:
        sender.objects.exclude(id__in=ids_to_keep).delete()
