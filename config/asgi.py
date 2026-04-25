"""ASGI config — Django Channels routing."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.urls import re_path  # noqa: E402

from apps.alerts.routing import websocket_urlpatterns as alert_ws  # noqa: E402
from apps.remote_access.ssh_consumer import SSHTerminalConsumer  # noqa: E402

websocket_urlpatterns = alert_ws + [
    re_path(
        r"^ws/ssh/(?P<device_id>[0-9a-f-]{36})/$",
        SSHTerminalConsumer.as_asgi(),
    ),
]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
