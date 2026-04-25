"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Auth (session-based for UI)
    path("auth/", include("apps.users.urls")),

    # Web UI
    path("", include("apps.dashboard.urls")),
    path("devices/", include("apps.devices.urls")),
    path("packets/", include("apps.packets.urls")),
    path("incidents/", include("apps.incidents.urls")),
    path("alerts/", include("apps.alerts.urls")),
    path("remote-access/", include("apps.remote_access.urls")),

    # REST API v1
    path("api/v1/", include("api.v1.urls")),

    # One-command installer (key in URL, no session required)
    path("api/v1/install/<str:device_key>/",
         __import__("api.v1.device_endpoints", fromlist=["install_script"]).install_script,
         name="device-install-script"),

    # OpenAPI / Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Health check
    path("health/", include("apps.common.health_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
