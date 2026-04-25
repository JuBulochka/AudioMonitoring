"""Custom throttle classes."""
from rest_framework.throttling import SimpleRateThrottle


class DeviceRateThrottle(SimpleRateThrottle):
    """Rate limit for edge device API calls (by device key)."""
    scope = "device"

    def get_cache_key(self, request, view):
        device_key = request.headers.get("X-Device-Key")
        if not device_key:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": device_key[:16],
        }
