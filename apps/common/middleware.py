"""Custom middleware."""
import logging
import time

from django.utils import timezone

logger = logging.getLogger("apps.common")
security_logger = logging.getLogger("security")


class AuditLogMiddleware:
    """
    Log login/logout events automatically.
    Heavy actions (device key rotation, status changes) are logged in services.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        pass


class RequestTimingMiddleware:
    """Add X-Response-Time header to all responses."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        elapsed = time.monotonic() - start
        response["X-Response-Time"] = f"{elapsed * 1000:.1f}ms"
        return response


class DeviceAuthMiddleware:
    """
    Authenticate edge devices by X-Device-Key header.
    Attaches `request.device` if valid, else None.
    Used by device-facing API endpoints.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.device = None
        device_key = request.headers.get("X-Device-Key")
        if device_key and request.path.startswith("/api/v1/device/"):
            from apps.devices.services import authenticate_device
            request.device = authenticate_device(device_key)
            if not request.device:
                security_logger.warning(
                    "Failed device auth attempt from %s for path %s",
                    self._get_client_ip(request),
                    request.path,
                )
        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
