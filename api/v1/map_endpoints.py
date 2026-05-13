"""API карты: отдает легкие маркеры устройств для фронтенда."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.devices.services import get_devices_for_map
from apps.devices.models import DeviceStatus


STATUS_COLOR = {
    DeviceStatus.NORMAL: "#28a745",
    DeviceStatus.NEEDS_INSPECTION: "#ffc107",
    DeviceStatus.NEEDS_RECONFIGURATION: "#fd7e14",
    DeviceStatus.SITE_VISIT_REQUIRED: "#dc3545",
    DeviceStatus.IN_PROGRESS: "#007bff",
    DeviceStatus.RESOLVED: "#6c757d",
    DeviceStatus.FALSE_POSITIVE: "#adb5bd",
    DeviceStatus.OFFLINE: "#343a40",
}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def map_devices(request):
    """
    Возвращает устройства в текущей области карты.

    На этом уровне уже применяется доступ пользователя, поэтому оператор получает
    маркеры только по закрепленным за ним месторождениям.
    """
    params = request.query_params

    bbox = None
    try:
        sw_lat = params.get("sw_lat")
        sw_lng = params.get("sw_lng")
        ne_lat = params.get("ne_lat")
        ne_lng = params.get("ne_lng")
        if all([sw_lat, sw_lng, ne_lat, ne_lng]):
            bbox = (float(sw_lat), float(sw_lng), float(ne_lat), float(ne_lng))
    except (ValueError, TypeError):
        pass

    region_ids = None
    if params.get("region"):
        try:
            region_ids = [int(r) for r in params["region"].split(",")]
        except ValueError:
            pass

    status_filter = None
    if params.get("status"):
        status_filter = params["status"].split(",")

    online_only = params.get("online_only") == "true"
    anomaly_only = params.get("anomaly_only") == "true"

    devices = get_devices_for_map(
        user=request.user,
        region_ids=region_ids,
        status_filter=status_filter,
        online_only=online_only,
        anomaly_only=anomaly_only,
        bbox=bbox,
    )

    features = []
    for d in devices:
        lat = d["pump_jack__latitude"]
        lng = d["pump_jack__longitude"]
        if lat is None or lng is None:
            continue

        dev_status = d["status"]
        features.append({
            "id": str(d["id"]),
            "lat": float(lat),
            "lng": float(lng),
            "serial_number": d["serial_number"],
            "name": d["name"],
            "status": dev_status,
            "is_online": d["is_online"],
            "well_number": d["pump_jack__well_number"],
            "region": d["pump_jack__site__field__region__name"],
            "last_seen_at": d["last_seen_at"].isoformat() if d["last_seen_at"] else None,
            "color": STATUS_COLOR.get(dev_status, "#6c757d"),
        })

    return Response({
        "count": len(features),
        "features": features,
    })


from django.urls import path  # noqa: E402

urlpatterns = [
    path("devices/", map_devices, name="api-map-devices"),
]
