"""
Core API tests.
Run: pytest tests/ -v
"""
import json
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    from apps.users.models import User, UserRole
    u = User.objects.create_superuser(
        username="testadmin",
        email="admin@test.local",
        password="testpass1234",
        role=UserRole.ADMIN,
        employee_number="ADM-TST",
    )
    return u


@pytest.fixture
def operator_user(db):
    from apps.users.models import User, UserRole
    return User.objects.create_user(
        username="testop",
        email="op@test.local",
        password="testpass1234",
        role=UserRole.OPERATOR,
        employee_number="OP-TST",
    )


@pytest.fixture
def auth_client(api_client, operator_user):
    api_client.force_authenticate(user=operator_user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def region(db):
    from apps.devices.models import Region
    return Region.objects.create(name="Test Region", code="TR")


@pytest.fixture
def device(db, region):
    from apps.devices.models import Field, Site, PumpJack, Device
    field = Field.objects.create(region=region, name="Test Field", code="TF",
                                  latitude=Decimal("55.0"), longitude=Decimal("37.0"))
    site = Site.objects.create(field=field, name="Site A", code="SA",
                                latitude=Decimal("55.01"), longitude=Decimal("37.01"))
    pj = PumpJack.objects.create(site=site, well_number="001", name="PJ Test",
                                  latitude=Decimal("55.01"), longitude=Decimal("37.01"))
    dev = Device.objects.create(
        pump_jack=pj,
        serial_number="TEST-001",
        name="Test Device",
    )
    return dev


@pytest.fixture
def other_device(db):
    from apps.devices.models import Region, Field, Site, PumpJack, Device
    region = Region.objects.create(name="Other Region", code="OR")
    field = Field.objects.create(region=region, name="Other Field", code="OF",
                                 latitude=Decimal("56.0"), longitude=Decimal("38.0"))
    site = Site.objects.create(field=field, name="Other Site", code="OS",
                               latitude=Decimal("56.01"), longitude=Decimal("38.01"))
    pj = PumpJack.objects.create(site=site, well_number="999", name="PJ Other",
                                  latitude=Decimal("56.01"), longitude=Decimal("38.01"))
    return Device.objects.create(
        pump_jack=pj,
        serial_number="OTHER-001",
        name="Other Device",
    )


@pytest.fixture
def assigned_operator(operator_user, device):
    from apps.users.models import OperatorProfile
    profile, _ = OperatorProfile.objects.get_or_create(user=operator_user)
    profile.assigned_fields.set([device.pump_jack.site.field])
    return operator_user


@pytest.fixture
def assigned_client(api_client, assigned_operator):
    api_client.force_authenticate(user=assigned_operator)
    return api_client


# ---------------------------------------------------------------------------
# Device auth
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeviceAuth:
    def test_heartbeat_valid_key(self, api_client, device):
        resp = api_client.post(
            "/api/v1/device/heartbeat/",
            data={"cpu_temp": 52.3, "cpu_usage": 18.5, "firmware_version": "1.0.0"},
            format="json",
            HTTP_X_DEVICE_KEY=device.auth_key,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_heartbeat_invalid_key(self, api_client):
        resp = api_client.post(
            "/api/v1/device/heartbeat/",
            data={"cpu_temp": 50.0},
            format="json",
            HTTP_X_DEVICE_KEY="invalid-key-xxx",
        )
        assert resp.status_code == 403

    def test_heartbeat_marks_device_online(self, api_client, device):
        device.is_online = False
        device.save()

        api_client.post(
            "/api/v1/device/heartbeat/",
            data={"cpu_temp": 50.0},
            format="json",
            HTTP_X_DEVICE_KEY=device.auth_key,
        )

        device.refresh_from_db()
        assert device.is_online is True


# ---------------------------------------------------------------------------
# Packet submission
# ---------------------------------------------------------------------------

VALID_ANALYSIS = {
    "normal": 0.05,
    "noise": 0.10,
    "grinding": 0.75,
    "squeak": 0.02,
    "knock": 0.03,
    "whistle": 0.01,
    "foreign_sounds": 0.01,
    "speech": 0.01,
    "other_anomaly": 0.02,
}


class TestPacketIngestion:
    def test_submit_packet_success(self, api_client, device):
        resp = api_client.post(
            "/api/v1/device/packet/",
            data={
                "recorded_at": "2026-04-13T10:00:00Z",
                "duration_seconds": 30.0,
                "analysis": VALID_ANALYSIS,
                "device_state": {"cpu_temp": 52.3, "firmware_version": "1.0"},
                "audio_meta": {"sample_rate": 44100, "channels": 1, "format": "wav"},
            },
            format="json",
            HTTP_X_DEVICE_KEY=device.auth_key,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert data["severity"] == "critical"  # grinding=0.75 → critical
        assert data["has_anomaly"] is True

    def test_submit_packet_missing_analysis(self, api_client, device):
        resp = api_client.post(
            "/api/v1/device/packet/",
            data={"recorded_at": "2026-04-13T10:00:00Z"},
            format="json",
            HTTP_X_DEVICE_KEY=device.auth_key,
        )
        assert resp.status_code == 400

    def test_packet_creates_class_scores(self, api_client, device):
        from apps.packets.models import AudioPacket, AudioClassScore
        resp = api_client.post(
            "/api/v1/device/packet/",
            data={
                "recorded_at": "2026-04-13T11:00:00Z",
                "analysis": VALID_ANALYSIS,
            },
            format="json",
            HTTP_X_DEVICE_KEY=device.auth_key,
        )
        assert resp.status_code == 201
        packet_id = resp.json()["packet_id"]
        scores = AudioClassScore.objects.filter(packet_id=packet_id)
        assert scores.count() == len(VALID_ANALYSIS)

    def test_normal_packet_no_anomaly(self, api_client, device):
        resp = api_client.post(
            "/api/v1/device/packet/",
            data={
                "recorded_at": "2026-04-13T12:00:00Z",
                "analysis": {
                    "normal": 0.92, "noise": 0.02, "grinding": 0.01,
                    "squeak": 0.01, "knock": 0.01, "whistle": 0.01,
                    "foreign_sounds": 0.01, "speech": 0.005, "other_anomaly": 0.005,
                },
            },
            format="json",
            HTTP_X_DEVICE_KEY=device.auth_key,
        )
        assert resp.status_code == 201
        assert resp.json()["has_anomaly"] is False


# ---------------------------------------------------------------------------
# Incident creation
# ---------------------------------------------------------------------------

class TestIncidentCreation:
    def test_critical_packet_creates_incident(self, api_client, device):
        from apps.incidents.models import Incident

        api_client.post(
            "/api/v1/device/packet/",
            data={
                "recorded_at": "2026-04-13T13:00:00Z",
                "analysis": {**VALID_ANALYSIS, "grinding": 0.85},
            },
            format="json",
            HTTP_X_DEVICE_KEY=device.auth_key,
        )

        # Celery task runs synchronously in tests (CELERY_TASK_ALWAYS_EAGER=True)
        assert Incident.objects.filter(device=device).exists()


# ---------------------------------------------------------------------------
# Operator API — device status
# ---------------------------------------------------------------------------

class TestDeviceStatusAPI:
    def test_change_status_as_admin(self, admin_client, device):
        resp = admin_client.patch(
            f"/api/v1/devices/{device.id}/status/",
            data={"status": "needs_inspection", "reason": "Test change"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        device.refresh_from_db()
        assert device.status == "needs_inspection"

    def test_change_status_creates_history(self, admin_client, device):
        from apps.devices.models import DeviceStatusHistory
        admin_client.patch(
            f"/api/v1/devices/{device.id}/status/",
            data={"status": "in_progress", "reason": "Taking action"},
            format="json",
        )
        assert DeviceStatusHistory.objects.filter(device=device, new_status="in_progress").exists()

    def test_operator_cannot_change_status(self, auth_client, device):
        resp = auth_client.patch(
            f"/api/v1/devices/{device.id}/status/",
            data={"status": "resolved"},
            format="json",
        )
        # Operator role has CanManageDevices = False for write
        assert resp.status_code in (403, 401)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class TestNotifications:
    def test_unread_count(self, auth_client, operator_user):
        from apps.alerts.services import create_alert
        from apps.alerts.models import AlertType, AlertSeverity
        create_alert(
            alert_type=AlertType.SYSTEM,
            severity=AlertSeverity.INFO,
            title="Test Alert",
            message="Test",
            dedup_window_minutes=0,
        )
        resp = auth_client.get("/api/v1/alerts/notifications/unread-count/")
        assert resp.status_code == 200
        assert "unread_count" in resp.json()

    def test_mark_all_read(self, auth_client, operator_user):
        resp = auth_client.post("/api/v1/alerts/notifications/mark-all-read/")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealth:
    def test_liveness(self, api_client):
        resp = api_client.get("/health/live/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_readiness(self, api_client):
        resp = api_client.get("/health/ready/")
        assert resp.status_code in (200, 503)
        assert "checks" in resp.json()


# ---------------------------------------------------------------------------
# Map API
# ---------------------------------------------------------------------------

class TestMapAPI:
    def test_map_devices(self, auth_client):
        resp = auth_client.get("/api/v1/map/devices/")
        assert resp.status_code == 200
        data = resp.json()
        assert "features" in data
        assert "count" in data

    def test_map_devices_bbox_filter(self, auth_client):
        resp = auth_client.get("/api/v1/map/devices/?sw_lat=50&sw_lng=30&ne_lat=70&ne_lng=80")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Operator field scoping
# ---------------------------------------------------------------------------

class TestOperatorFieldScoping:
    def test_device_api_list_only_assigned_fields(self, assigned_client, device, other_device):
        resp = assigned_client.get("/api/v1/devices/")
        assert resp.status_code == 200
        payload = resp.json()
        items = payload.get("results", payload)
        ids = {item["id"] for item in items}
        assert str(device.id) in ids
        assert str(other_device.id) not in ids

    def test_device_api_detail_blocks_unassigned_device(self, assigned_client, other_device):
        resp = assigned_client.get(f"/api/v1/devices/{other_device.id}/")
        assert resp.status_code == 404

    def test_map_api_only_assigned_fields(self, assigned_client, device, other_device):
        resp = assigned_client.get("/api/v1/map/devices/")
        assert resp.status_code == 200
        ids = {feature["id"] for feature in resp.json()["features"]}
        assert str(device.id) in ids
        assert str(other_device.id) not in ids

    def test_remote_access_page_only_assigned_devices(self, client, assigned_operator, device, other_device):
        client.force_login(assigned_operator)
        resp = client.get("/remote-access/")
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        assert device.serial_number in content
        assert other_device.serial_number not in content

    def test_remote_verify_blocks_unassigned_device(self, client, assigned_operator, other_device):
        client.force_login(assigned_operator)
        resp = client.get(f"/remote-access/verify/{other_device.id}/")
        assert resp.status_code == 404
