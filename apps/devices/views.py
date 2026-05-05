"""Device web views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import Device, DeviceStatus, Region, Field, Site, PumpJack


@login_required
def device_list(request):
    from apps.devices.models import Region

    qs = Device.objects.filter(is_active=True).select_related(
        "pump_jack__site__field__region", "assigned_operator"
    ).order_by("-last_seen_at")

    # Filters
    region_id = request.GET.get("region")
    status = request.GET.get("status")
    online = request.GET.get("online")
    search = request.GET.get("q", "").strip()

    if region_id:
        qs = qs.filter(pump_jack__site__field__region_id=region_id)
    if status:
        qs = qs.filter(status=status)
    if online == "1":
        qs = qs.filter(is_online=True)
    elif online == "0":
        qs = qs.filter(is_online=False)
    if search:
        qs = qs.filter(
            __import__("django.db.models", fromlist=["Q"]).Q(name__icontains=search)
            | __import__("django.db.models", fromlist=["Q"]).Q(serial_number__icontains=search)
            | __import__("django.db.models", fromlist=["Q"]).Q(pump_jack__well_number__icontains=search)
        )

    ctx = {
        "devices": qs,
        "regions": Region.objects.all().order_by("name"),
        "device_statuses": DeviceStatus.choices,
        "filter_region": region_id or "",
        "filter_status": status or "",
        "filter_online": online or "",
        "filter_q": search,
    }
    return render(request, "devices/device_list.html", ctx)


@login_required
def device_detail(request, device_id):
    from apps.packets.models import AudioPacket, SeverityLevel

    device = get_object_or_404(
        Device.objects.select_related(
            "pump_jack__site__field__region", "assigned_operator"
        ),
        id=device_id, is_active=True,
    )

    now = timezone.now()
    since_90 = now - timedelta(days=90)

    # Recent packets
    packets_qs = AudioPacket.objects.filter(
        device=device, recorded_at__gte=since_90
    ).prefetch_related("class_scores").order_by("-recorded_at")

    # Filters on packets
    sev = request.GET.get("severity")
    anomaly = request.GET.get("anomaly")
    from_dt = request.GET.get("from_date")
    to_dt = request.GET.get("to_date")

    if sev:
        packets_qs = packets_qs.filter(severity=sev)
    if anomaly == "1":
        packets_qs = packets_qs.filter(has_anomaly=True)
    if from_dt:
        from django.utils.dateparse import parse_date
        d = parse_date(from_dt)
        if d:
            packets_qs = packets_qs.filter(recorded_at__date__gte=d)
    if to_dt:
        from django.utils.dateparse import parse_date
        d = parse_date(to_dt)
        if d:
            packets_qs = packets_qs.filter(recorded_at__date__lte=d)

    packets = packets_qs[:100]

    # Status history
    status_history = device.status_history.select_related("changed_by").order_by("-changed_at")[:20]

    # Operator comments
    comments = device.comments.select_related("author").order_by("-created_at")[:20]

    # Open incidents
    from apps.incidents.models import Incident, IncidentStatus
    open_incidents = Incident.objects.filter(
        device=device,
        status__in=[IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS],
    ).order_by("-created_at")[:5]

    # Latest heartbeat
    latest_hb = device.heartbeats.first()

    # Remote access sessions
    from apps.remote_access.models import RemoteAccessSession
    recent_sessions = RemoteAccessSession.objects.filter(
        device=device
    ).select_related("operator").order_by("-created_at")[:5]

    # Chart data — class score averages for last 7 days
    from apps.packets.models import AudioClassScore
    from django.db import models
    chart_data = {}
    class_aggs = (
        AudioClassScore.objects
        .filter(packet__device=device, packet__recorded_at__gte=now - timedelta(days=7))
        .values("audio_class")
        .annotate(avg_score=models.Avg("score"), exc_count=models.Count("id", filter=models.Q(threshold_exceeded=True)))
    )
    for row in class_aggs:
        chart_data[row["audio_class"]] = {
            "avg_score": round(row["avg_score"], 4),
            "exc_count": row["exc_count"],
        }

    ctx = {
        "device": device,
        "packets": packets,
        "status_history": status_history,
        "comments": comments,
        "open_incidents": open_incidents,
        "latest_hb": latest_hb,
        "recent_sessions": recent_sessions,
        "chart_data": chart_data,
        "device_statuses": DeviceStatus.choices,
        "severity_levels": SeverityLevel.choices,
        "filter_severity": sev or "",
        "filter_anomaly": anomaly or "",
        "filter_from": from_dt or "",
        "filter_to": to_dt or "",
    }
    return render(request, "devices/device_detail.html", ctx)


@login_required
def device_create(request):
    """Custom single-page device creation with full geographic hierarchy."""
    if request.method == "POST":
        try:
            with transaction.atomic():
                # --- Region: pick existing or create new ---
                region_id = request.POST.get("region_id")
                if region_id:
                    region = Region.objects.get(id=region_id)
                else:
                    region_name = request.POST.get("region_name", "").strip()
                    region_code = request.POST.get("region_code", "").strip() or region_name[:20].upper().replace(" ", "_")
                    if not region_name:
                        raise ValueError("Укажите регион")
                    region, _ = Region.objects.get_or_create(
                        code=region_code,
                        defaults={"name": region_name},
                    )

                # --- Field (месторождение): pick existing or create ---
                field_id = request.POST.get("field_id")
                if field_id:
                    field = Field.objects.get(id=field_id)
                else:
                    field_name = request.POST.get("field_name", "").strip()
                    field_code = request.POST.get("field_code", "").strip() or f"{region.code}-{field_name[:10].upper().replace(' ','_')}"
                    if not field_name:
                        raise ValueError("Укажите месторождение")
                    field, _ = Field.objects.get_or_create(
                        code=field_code,
                        defaults={"name": field_name, "region": region},
                    )

                # --- Site (куст): pick existing or create ---
                site_id = request.POST.get("site_id")
                if site_id:
                    site = Site.objects.get(id=site_id)
                else:
                    site_name = request.POST.get("site_name", "").strip()
                    site_code = request.POST.get("site_code", "").strip() or f"{field.code}-{site_name[:10].upper().replace(' ','_')}"
                    if not site_name:
                        raise ValueError("Укажите куст скважин")
                    site, _ = Site.objects.get_or_create(
                        code=site_code,
                        defaults={"name": site_name, "field": field},
                    )

                # --- PumpJack: always create new ---
                well_number = request.POST.get("well_number", "").strip()
                pj_name = request.POST.get("pj_name", "").strip() or f"Скв. {well_number}"
                lat = request.POST.get("latitude", "").strip() or "0"
                lon = request.POST.get("longitude", "").strip() or "0"
                if not well_number:
                    raise ValueError("Укажите номер скважины")

                pump_jack = PumpJack.objects.create(
                    site=site,
                    well_number=well_number,
                    name=pj_name,
                    latitude=lat,
                    longitude=lon,
                )

                # --- Device ---
                device_name = request.POST.get("device_name", "").strip() or f"Pi-{well_number}"
                serial_number = request.POST.get("serial_number", "").strip() or f"RPI-{well_number}"
                device = Device.objects.create(
                    pump_jack=pump_jack,
                    name=device_name,
                    serial_number=serial_number,
                )

            messages.success(request, f"Устройство «{device.name}» создано. Скопируйте ключ и настройте Pi.")
            return redirect("device-setup", device_id=device.id)

        except Exception as e:
            messages.error(request, f"Ошибка: {e}")

    # GET — render form
    ctx = {
        "regions": Region.objects.all().order_by("name"),
        "fields": Field.objects.select_related("region").all().order_by("name"),
        "sites": Site.objects.select_related("field").all().order_by("name"),
    }
    return render(request, "devices/device_create.html", ctx)


@login_required
def device_setup(request, device_id):
    """Setup instructions page shown after device creation."""
    device = get_object_or_404(Device, id=device_id, is_active=True)
    host   = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    api_base    = f"{scheme}://{host}"
    install_url = f"{api_base}/api/v1/install/{device.auth_key}/"
    ctx = {
        "device":         device,
        "api_base":       api_base,
        "install_url":    install_url,
        "tunnel_host":    host.split(":")[0],
        "tunnel_ssh_port": 2222,
    }
    return render(request, "devices/device_setup.html", ctx)


@login_required
def device_map(request):
    from apps.devices.models import Region
    from django.conf import settings as django_settings
    ctx = {
        "regions": Region.objects.all().order_by("name"),
        "device_statuses": DeviceStatus.choices,
        "yandex_maps_api_key": django_settings.YANDEX_MAPS_API_KEY,
    }
    return render(request, "devices/map.html", ctx)


@login_required
def audio_test(request):
    """Page for manual audio file testing through ML model."""
    return render(request, "devices/audio_test.html")


@login_required
def audio_test_analyze(request):
    """AJAX endpoint: receive audio file, run ML analysis, return JSON."""
    import tempfile
    import os
    import requests as http_requests
    from django.http import JsonResponse
    from django.conf import settings as django_settings

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    audio_file = request.FILES.get("audio_file")
    if not audio_file:
        return JsonResponse({"error": "Файл не загружен"}, status=400)

    # Validate file type
    allowed_types = {"audio/wav", "audio/ogg", "audio/mpeg", "audio/flac", "audio/x-wav"}
    allowed_exts  = {".wav", ".ogg", ".mp3", ".flac"}
    ext = os.path.splitext(audio_file.name)[1].lower()
    if ext not in allowed_exts:
        return JsonResponse({"error": f"Неподдерживаемый формат: {ext}"}, status=400)

    # Save to temp file
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        # Call ML service
        ml_url = getattr(django_settings, "ML_SERVICE_URL", "http://ml-service:8001")
        resp = http_requests.post(
            f"{ml_url}/analyze",
            json={"file_path": tmp_path},
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()

        # Add human-readable labels
        CLASS_LABELS = {
            "normal":        "Норма",
            "noise":         "Шум",
            "grinding":      "Скрежет",
            "squeak":        "Скрип",
            "knock":         "Стук",
            "whistle":       "Свист",
            "foreign_sounds":"Посторонние звуки",
            "speech":        "Речь",
            "other_anomaly": "Иная аномалия",
        }
        result["class_labels"] = CLASS_LABELS
        result["filename"] = audio_file.name
        result["file_size_kb"] = round(audio_file.size / 1024, 1)
        return JsonResponse(result)

    except http_requests.exceptions.ConnectionError:
        return JsonResponse({"error": "ML сервис недоступен. Попробуйте позже."}, status=503)
    except http_requests.exceptions.Timeout:
        return JsonResponse({"error": "ML сервис не отвечает (timeout). Попробуйте позже."}, status=504)
    except Exception as e:
        return JsonResponse({"error": f"Ошибка анализа: {e}"}, status=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
