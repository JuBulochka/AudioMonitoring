"""Команда заполнения локальной базы демонстрационными данными."""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Загрузить демонстрационные данные для локальной разработки"

    def add_arguments(self, parser):
        """Добавляет флаг пропуска, если данные уже существуют."""
        parser.add_argument("--skip-if-exists", action="store_true", help="Skip if data already exists")

    def handle(self, *args, **options):
        """Создает пользователей, географию, устройства, пакеты, инциденты и уведомления."""
        from apps.devices.models import Region, Field, Site, PumpJack, Device
        from apps.users.models import User, UserRole
        from apps.users.models import OperatorProfile

        if options["skip_if_exists"] and Device.objects.exists():
            self.stdout.write("Demo data already exists, skipping.")
            return

        self.stdout.write("Creating demo data...")

        users = {}
        employee_numbers = {
            "operator1": "OP-0001",
            "operator2": "OP-0002",
            "operator3": "OP-0003",
            "operator4": "OP-0004",
        }
        for username, role, fname, lname in [
            ("operator1", UserRole.OPERATOR, "Иван", "Петров"),
            ("operator2", UserRole.OPERATOR, "Мария", "Сидорова"),
            ("operator3", UserRole.OPERATOR, "Алексей", "Козлов"),
            ("operator4", UserRole.OPERATOR, "Дмитрий", "Новиков"),
        ]:
            u, _ = User.objects.get_or_create(
                username=username,
                defaults=dict(
                    email=f"{username}@pumpjack.local",
                    first_name=fname,
                    last_name=lname,
                    role=role,
                    employee_number=employee_numbers[username],
                    is_active=True,
                ),
            )
            if not u.employee_number:
                u.employee_number = employee_numbers[username]
                u.save(update_fields=["employee_number"])
            if not u.has_usable_password():
                u.set_password("demo1234567")
                u.save()
            OperatorProfile.objects.get_or_create(user=u)
            users[username] = u

        regions_data = [
            ("Западная Сибирь", "WS"),
            ("Поволжье", "PV"),
            ("Урал", "UR"),
        ]
        regions = []
        for name, code in regions_data:
            r, _ = Region.objects.get_or_create(name=name, defaults={"code": code})
            regions.append(r)


        fields_data = [
            (regions[0], "Самотлорское", "SAM", 61.2, 72.5),
            (regions[0], "Приобское", "PRIOB", 60.9, 71.3),
            (regions[1], "Ромашкинское", "ROM", 54.7, 52.3),
            (regions[2], "Арланское", "ARL", 55.8, 56.1),
        ]
        fields = []
        for region, name, code, lat, lon in fields_data:
            f, _ = Field.objects.get_or_create(
                code=code,
                defaults=dict(region=region, name=name, latitude=Decimal(str(lat)), longitude=Decimal(str(lon)))
            )
            fields.append(f)

        users["operator1"].profile.assigned_fields.set([fields[0], fields[1]])
        users["operator2"].profile.assigned_fields.set([fields[2], fields[3]])

        sites = []
        for i, field in enumerate(fields):
            for j in range(2):
                code = f"{field.code}-K{j+1}"
                s, _ = Site.objects.get_or_create(
                    code=code,
                    defaults=dict(
                        field=field,
                        name=f"Куст {j+1}",
                        latitude=field.latitude + Decimal(str(j * 0.05)),
                        longitude=field.longitude + Decimal(str(j * 0.05)),
                    )
                )
                sites.append(s)

        devices = []
        device_configs = [
            ("PJ-001", "Качалка №1", sites[0], "101", 61.201, 72.501, True),
            ("PJ-002", "Качалка №2", sites[0], "102", 61.198, 72.498, True),
            ("PJ-003", "Качалка №3", sites[1], "103", 61.210, 72.510, False),
            ("PJ-004", "Качалка №4", sites[2], "104", 61.190, 72.480, True),
            ("PJ-005", "Качалка №5", sites[3], "105", 60.905, 71.305, True),
            ("PJ-006", "Качалка №6", sites[4], "106", 54.701, 52.301, True),
            ("PJ-007", "Качалка №7", sites[5], "107", 54.695, 52.295, False),
            ("PJ-008", "Качалка №8", sites[6], "108", 55.801, 56.101, True),
        ]

        for serial, name, site, well_no, lat, lon, is_online in device_configs:
            pj, _ = PumpJack.objects.get_or_create(
                site=site,
                well_number=well_no,
                defaults=dict(
                    name=name,
                    latitude=Decimal(str(lat)),
                    longitude=Decimal(str(lon)),
                    is_active=True,
                )
            )
            from apps.devices.models import DeviceStatus
            dev, created = Device.objects.get_or_create(
                serial_number=serial,
                defaults=dict(
                    pump_jack=pj,
                    name=f"RPi-{serial}",
                    status=random.choice([
                        DeviceStatus.NORMAL,
                        DeviceStatus.NEEDS_INSPECTION,
                        DeviceStatus.NORMAL,
                        DeviceStatus.NORMAL,
                    ]),
                    is_online=is_online,
                    is_active=True,
                    last_seen_at=timezone.now() - timedelta(minutes=random.randint(2, 200)),
                    last_heartbeat_at=timezone.now() - timedelta(minutes=random.randint(1, 90)),
                    firmware_version="1.3.2",
                    model_version="0.9.4",
                    assigned_operator=random.choice(list(users.values())),
                )
            )
            devices.append(dev)

        from apps.packets.models import AudioPacket, AudioClassScore, AudioClass, SeverityLevel

        now = timezone.now()
        packet_classes = list(AudioClass.values)

        for dev in devices:
            for hours_ago in range(0, 24 * 14, 1):  # 14 days hourly
                recorded_at = now - timedelta(hours=hours_ago)
                roll = random.random()
                if roll < 0.75:
                    severity = SeverityLevel.INFO
                    dominant = AudioClass.NORMAL
                    dominant_score = round(random.uniform(0.7, 0.97), 3)
                    has_anomaly = False
                elif roll < 0.90:
                    severity = SeverityLevel.WARNING
                    dominant = random.choice([AudioClass.SQUEAK, AudioClass.NOISE, AudioClass.SPEECH])
                    dominant_score = round(random.uniform(0.45, 0.65), 3)
                    has_anomaly = True
                else:
                    severity = SeverityLevel.CRITICAL
                    dominant = random.choice([AudioClass.GRINDING, AudioClass.KNOCK, AudioClass.WHISTLE])
                    dominant_score = round(random.uniform(0.65, 0.95), 3)
                    has_anomaly = True

                pkt, created = AudioPacket.objects.get_or_create(
                    device=dev,
                    recorded_at=recorded_at,
                    defaults=dict(
                        duration_seconds=30.0,
                        has_anomaly=has_anomaly,
                        severity=severity,
                        dominant_class=dominant,
                        dominant_class_score=dominant_score,
                        status="processed",
                        device_cpu_temp=round(random.uniform(42, 72), 1),
                        device_cpu_usage=round(random.uniform(8, 55), 1),
                        device_memory_usage_pct=round(random.uniform(30, 70), 1),
                        device_disk_usage_pct=round(random.uniform(15, 50), 1),
                        device_firmware_version="1.3.2",
                        device_model_version="0.9.4",
                        raw_analysis={"demo": True},
                    )
                )

                if created:
                    remaining = 1.0
                    scores = {}
                    for cls in packet_classes:
                        if cls == dominant:
                            scores[cls] = dominant_score
                        else:
                            val = round(random.uniform(0.01, max(0.02, (1 - dominant_score) / len(packet_classes))), 3)
                            scores[cls] = val

                    AudioClassScore.objects.bulk_create([
                        AudioClassScore(
                            packet=pkt,
                            audio_class=cls,
                            score=score,
                            threshold_exceeded=(cls == dominant and has_anomaly),
                        )
                        for cls, score in scores.items()
                    ], ignore_conflicts=True)

        from apps.incidents.models import Incident, IncidentType, IncidentStatus, IncidentSeverity, IncidentComment

        incident_data = [
            (devices[0], IncidentType.AUDIO_ANOMALY, IncidentSeverity.CRITICAL, IncidentStatus.OPEN,
             "Скрежет высокой интенсивности", "Зафиксирован скрежет 0.87 в 3 последовательных пакетах."),
            (devices[2], IncidentType.DEVICE_OFFLINE, IncidentSeverity.WARNING, IncidentStatus.ACKNOWLEDGED,
             "Потеря связи с PJ-003", "Устройство не выходило на связь более 2 часов."),
            (devices[5], IncidentType.REPEATED_FAULT, IncidentSeverity.WARNING, IncidentStatus.IN_PROGRESS,
             "Повторяющийся стук", "8 аномальных пакетов за 24 часа."),
            (devices[1], IncidentType.AUDIO_ANOMALY, IncidentSeverity.CRITICAL, IncidentStatus.RESOLVED,
             "Свист — устранён", "Замена подшипника — проблема устранена."),
        ]

        for dev, itype, isev, istat, title, desc in incident_data:
            inc, created = Incident.objects.get_or_create(
                device=dev,
                title=title,
                defaults=dict(
                    incident_type=itype,
                    severity=isev,
                    status=istat,
                    description=desc,
                    assigned_to=users["operator1"],
                    created_at=now - timedelta(hours=random.randint(1, 48)),
                )
            )
            if created:
                IncidentComment.objects.create(
                    incident=inc,
                    author=users["operator3"],
                    text="Принято к рассмотрению. Назначен выезд.",
                )

        from apps.alerts.services import create_alert
        from apps.alerts.models import AlertType, AlertSeverity

        for dev in devices[:3]:
            create_alert(
                alert_type=AlertType.CRITICAL_ANOMALY,
                severity=AlertSeverity.CRITICAL,
                title=f"Критическая аномалия: {dev.serial_number}",
                message=f"Обнаружен скрежет на {dev.serial_number}.",
                device=dev,
                dedup_window_minutes=0,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Demo data loaded: {len(devices)} devices, packets for 14 days, incidents and alerts."
        ))
