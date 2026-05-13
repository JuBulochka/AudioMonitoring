"""Health check endpoints."""
from django.urls import path
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import django


def health_check(request):
    """Liveness probe."""
    return JsonResponse({"status": "ok", "django": django.VERSION})


def readiness_check(request):
    """Readiness probe — checks DB and cache."""
    checks = {}

    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        cache.set("_health", "1", timeout=5)
        val = cache.get("_health")
        checks["cache"] = "ok" if val == "1" else "error: bad value"
    except Exception as e:
        checks["cache"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JsonResponse({"status": "ok" if all_ok else "degraded", "checks": checks}, status=status_code)


urlpatterns = [
    path("live/", health_check, name="health-live"),
    path("ready/", readiness_check, name="health-ready"),
]
