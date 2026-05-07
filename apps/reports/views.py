"""
PDF report generation for АСУТП Мониторинг.

Generates a structured PDF with:
- Cover header: logo + title + period + generation info
- Summary stats table (devices, incidents, anomalies)
- Device status breakdown
- Audio anomalies by class
- Incidents list (up to 50 most recent)
- Page numbers footer
"""
import io
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.timezone import localtime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Image, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

# ── Font registration (Cyrillic support) ──────────────────────────────────────
_FONT_REGULAR = 'DejaVuSans'
_FONT_BOLD    = 'DejaVuSans-Bold'
_FONTS_OK     = False

def _register_fonts():
    """Register DejaVu TTF fonts for Cyrillic support. Falls back to Helvetica."""
    global _FONTS_OK
    if _FONTS_OK:
        return
    search_dirs = [
        '/usr/share/fonts/truetype/dejavu',
        '/usr/share/fonts/dejavu',
        '/usr/share/fonts/truetype',
        '/usr/share/fonts',
    ]
    for base in search_dirs:
        reg  = os.path.join(base, 'DejaVuSans.ttf')
        bold = os.path.join(base, 'DejaVuSans-Bold.ttf')
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont(_FONT_REGULAR, reg))
                pdfmetrics.registerFont(TTFont(_FONT_BOLD,    bold))
                _FONTS_OK = True
                return
            except Exception:
                pass

from apps.devices.models import Device, DeviceStatus, Region, Field, Site
from apps.incidents.models import Incident, IncidentSeverity, IncidentStatus
from apps.packets.models import AudioClass, AudioPacket

# ── Period config ──────────────────────────────────────────────────────────────
PERIOD_CHOICES = {
    '1':  ('1 день',   1),
    '7':  ('7 дней',  7),
    '14': ('14 дней', 14),
    '30': ('30 дней', 30),
}

# ── Brand palette ──────────────────────────────────────────────────────────────
CLR_GREEN       = colors.HexColor('#1a7f37')
CLR_DARK        = colors.HexColor('#1f2328')
CLR_MUTED       = colors.HexColor('#636c76')
CLR_BORDER      = colors.HexColor('#d0d7de')
CLR_ROW_ALT     = colors.HexColor('#f6f8fa')
CLR_RED         = colors.HexColor('#cf222e')
CLR_YELLOW      = colors.HexColor('#9a6700')
CLR_WHITE       = colors.white


# ── Views ──────────────────────────────────────────────────────────────────────

@login_required
def report_page(request):
    periods = [(k, v[0]) for k, v in PERIOD_CHOICES.items()]

    regions = list(Region.objects.order_by('name').values('id', 'name'))
    fields  = list(Field.objects.order_by('name').values('id', 'name', 'region_id'))
    sites   = list(Site.objects.order_by('name').values('id', 'name', 'field_id'))
    devices = list(
        Device.objects.filter(is_active=True)
        .select_related('pump_jack__site')
        .order_by('serial_number')
        .values('id', 'serial_number', 'name', 'pump_jack__site_id')
    )
    # Normalize UUID to str for JSON serialization
    for d in devices:
        d['id'] = str(d['id'])
        d['site_id'] = str(d.pop('pump_jack__site_id') or '')

    import json
    return render(request, 'reports/report.html', {
        'periods': periods,
        'regions': regions,
        'fields':  fields,
        'sites':   sites,
        'devices': devices,
        'regions_json': json.dumps(regions),
        'fields_json':  json.dumps(fields),
        'sites_json':   json.dumps(sites),
        'devices_json': json.dumps(devices),
    })


@login_required
def generate_pdf(request):
    period_key = request.GET.get('period', '7')
    if period_key not in PERIOD_CHOICES:
        period_key = '7'

    period_label, period_days = PERIOD_CHOICES[period_key]
    now       = timezone.now()
    date_from = now - timedelta(days=period_days)

    # ── Filters ────────────────────────────────────────────────────────────────
    region_id  = request.GET.get('region_id', '').strip()
    field_id   = request.GET.get('field_id',  '').strip()
    site_id    = request.GET.get('site_id',   '').strip()
    device_ids_param = [d for d in request.GET.getlist('device_id') if d.strip()]

    # Build human-readable filter label for PDF header
    filter_label = 'Все устройства'
    try:
        if device_ids_param:
            devs_qs = Device.objects.filter(id__in=device_ids_param).values('serial_number', 'name')
            names = [f"{d['serial_number']}" + (f" — {d['name']}" if d['name'] else '') for d in devs_qs]
            filter_label = 'Устройства: ' + ', '.join(names)
        elif site_id:
            site_obj = Site.objects.select_related('field__region').get(id=site_id)
            filter_label = (
                f'{site_obj.field.region.name} / '
                f'{site_obj.field.name} / {site_obj.name}'
            )
        elif field_id:
            field_obj = Field.objects.select_related('region').get(id=field_id)
            filter_label = f'{field_obj.region.name} / {field_obj.name}'
        elif region_id:
            region_obj = Region.objects.get(id=region_id)
            filter_label = region_obj.name
    except Exception:
        filter_label = 'Все устройства'

    # ── Query data ─────────────────────────────────────────────────────────────
    all_devices = Device.objects.filter(is_active=True)

    # Apply geographic / device filters (most specific wins)
    if device_ids_param:
        all_devices = all_devices.filter(id__in=device_ids_param)
    elif site_id:
        all_devices = all_devices.filter(pump_jack__site_id=site_id)
    elif field_id:
        all_devices = all_devices.filter(pump_jack__site__field_id=field_id)
    elif region_id:
        all_devices = all_devices.filter(pump_jack__site__field__region_id=region_id)

    total_devices   = all_devices.count()
    online_devices  = all_devices.filter(is_online=True).count()
    offline_devices = total_devices - online_devices
    critical_devices = all_devices.filter(
        status__in=[DeviceStatus.SITE_VISIT_REQUIRED, DeviceStatus.NEEDS_INSPECTION]
    ).count()

    # Status breakdown (skip zero-count statuses)
    status_label_map = dict(DeviceStatus.choices)
    status_counts = []
    for val in DeviceStatus.values:
        cnt = all_devices.filter(status=val).count()
        if cnt:
            status_counts.append((status_label_map[val], cnt))

    # Collect device IDs for incident/packet filtering
    device_ids = list(all_devices.values_list('id', flat=True))

    # Incidents in period
    incidents_qs = Incident.objects.filter(
        created_at__gte=date_from,
        device_id__in=device_ids,
    ).select_related('device')
    total_incidents  = incidents_qs.count()
    open_incidents   = Incident.objects.filter(
        device_id__in=device_ids,
        status__in=[IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS]
    ).count()
    critical_inc = incidents_qs.filter(severity=IncidentSeverity.CRITICAL).count()
    warning_inc  = incidents_qs.filter(severity=IncidentSeverity.WARNING).count()
    info_inc     = incidents_qs.filter(severity=IncidentSeverity.INFO).count()
    incidents    = list(incidents_qs.order_by('-created_at')[:50])

    # Anomaly stats
    anomaly_qs = AudioPacket.objects.filter(
        recorded_at__gte=date_from,
        has_anomaly=True,
        device_id__in=device_ids,
    )
    total_anomalies = anomaly_qs.count()
    class_label_map = dict(AudioClass.choices)
    anomaly_by_class = {}
    for row in anomaly_qs.values('dominant_class'):
        cls = row['dominant_class']
        anomaly_by_class[cls] = anomaly_by_class.get(cls, 0) + 1

    # ── Build PDF ──────────────────────────────────────────────────────────────
    _register_fonts()
    fn  = _FONT_REGULAR if _FONTS_OK else 'Helvetica'
    fn_b = _FONT_BOLD   if _FONTS_OK else 'Helvetica-Bold'

    buffer = io.BytesIO()
    page_w = A4[0] - 40 * mm   # usable content width

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=20 * mm,   bottomMargin=20 * mm,
        title=f'Отчёт АСУТП Мониторинг — {period_label}',
        author=request.user.get_full_name() or request.user.username,
    )

    styles = getSampleStyleSheet()

    S_H1 = ParagraphStyle(
        'H1', parent=styles['Normal'],
        fontSize=18, fontName=fn_b,
        textColor=CLR_DARK, spaceAfter=4, alignment=TA_CENTER,
    )
    S_H2 = ParagraphStyle(
        'H2', parent=styles['Normal'],
        fontSize=12, fontName=fn_b,
        textColor=CLR_DARK, spaceBefore=12, spaceAfter=5,
    )
    S_SUB = ParagraphStyle(
        'Sub', parent=styles['Normal'],
        fontSize=9, fontName=fn,
        textColor=CLR_MUTED, spaceAfter=2, alignment=TA_CENTER,
    )
    S_NORM = ParagraphStyle(
        'Norm', parent=styles['Normal'],
        fontSize=8.5, fontName=fn, textColor=CLR_DARK,
    )
    S_SMALL = ParagraphStyle(
        'Small', parent=styles['Normal'],
        fontSize=7.5, fontName=fn,
        textColor=CLR_MUTED, spaceAfter=1, alignment=TA_CENTER,
    )
    S_FOOTER = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=7, fontName=fn,
        textColor=CLR_MUTED, alignment=TA_CENTER,
    )

    elems = []

    # ── Logo ───────────────────────────────────────────────────────────────────
    logo_path = _find_logo()
    if logo_path:
        try:
            img = Image(logo_path)
            # scale proportionally to max width 48mm or max height 22mm
            iw, ih = img.imageWidth, img.imageHeight
            if iw and ih:
                scale = min(48 * mm / iw, 22 * mm / ih)
                img.drawWidth  = iw * scale
                img.drawHeight = ih * scale
            else:
                img.drawWidth, img.drawHeight = 48 * mm, 18 * mm
            img.hAlign = 'CENTER'
            elems.append(img)
            elems.append(Spacer(1, 4 * mm))
        except Exception:
            pass

    # ── Header ─────────────────────────────────────────────────────────────────
    elems.append(Paragraph('АСУТП Мониторинг', S_H1))
    elems.append(Paragraph('Система мониторинга нефтяных качалок', S_SUB))
    elems.append(Spacer(1, 3 * mm))

    now_local  = localtime(now)
    from_local = localtime(date_from)
    elems.append(Paragraph(f'Отчётный период: <b>{period_label}</b>', S_SUB))
    elems.append(Paragraph(
        f'{from_local.strftime("%d.%m.%Y %H:%M")} — {now_local.strftime("%d.%m.%Y %H:%M")}',
        S_SUB,
    ))
    elems.append(Paragraph(f'Выборка: <b>{filter_label}</b>', S_SUB))
    elems.append(Spacer(1, 2 * mm))
    elems.append(Paragraph(
        f'Сформирован: {now_local.strftime("%d.%m.%Y %H:%M")} &nbsp;|&nbsp; '
        f'Пользователь: {request.user.get_full_name() or request.user.username}',
        S_SMALL,
    ))
    elems.append(Spacer(1, 4 * mm))
    elems.append(HRFlowable(width='100%', thickness=1.5, color=CLR_GREEN, spaceAfter=6 * mm))

    # ── Summary stats ──────────────────────────────────────────────────────────
    elems.append(Paragraph('Сводная статистика', S_H2))

    summary_data = [
        ['Показатель', 'Значение'],
        ['Всего устройств',                 str(total_devices)],
        ['Онлайн',                          str(online_devices)],
        ['Оффлайн',                         str(offline_devices)],
        ['Требуют внимания',                str(critical_devices)],
        [f'Инцидентов за {period_label}',   str(total_incidents)],
        ['Открытых инцидентов (всего)',     str(open_incidents)],
        ['  — Критических',                 str(critical_inc)],
        ['  — Предупреждений',              str(warning_inc)],
        ['  — Информационных',              str(info_inc)],
        [f'Аудиоаномалий за {period_label}', str(total_anomalies)],
    ]
    elems.append(_make_table(summary_data, [page_w * 0.72, page_w * 0.28],
                             header_color=CLR_GREEN, fn=fn, fn_b=fn_b))
    elems.append(Spacer(1, 4 * mm))

    # ── Device status breakdown ────────────────────────────────────────────────
    if status_counts:
        elems.append(Paragraph('Статус устройств', S_H2))
        status_data = [['Статус', 'Кол-во']] + [[lbl, str(cnt)] for lbl, cnt in status_counts]
        elems.append(_make_table(status_data, [page_w * 0.72, page_w * 0.28], fn=fn, fn_b=fn_b))
        elems.append(Spacer(1, 4 * mm))

    # ── Anomalies by class ─────────────────────────────────────────────────────
    if anomaly_by_class:
        elems.append(Paragraph(f'Аудиоаномалии по типу за {period_label}', S_H2))
        anomaly_data = [['Тип аномалии', 'Кол-во пакетов']]
        for cls_val, cnt in sorted(anomaly_by_class.items(), key=lambda x: -x[1]):
            anomaly_data.append([class_label_map.get(cls_val, cls_val), str(cnt)])
        elems.append(_make_table(anomaly_data, [page_w * 0.72, page_w * 0.28], fn=fn, fn_b=fn_b))
        elems.append(Spacer(1, 4 * mm))

    # ── Incidents table ────────────────────────────────────────────────────────
    elems.append(Paragraph(f'Инциденты за {period_label}', S_H2))

    if incidents:
        # Abbreviated labels so text fits narrow columns without overflow
        sev_labels = {
            IncidentSeverity.CRITICAL: 'Критично',
            IncidentSeverity.WARNING:  'Пред-ние',
            IncidentSeverity.INFO:     'Инфо',
        }
        sta_labels = {
            IncidentStatus.OPEN:           'Открыт',
            IncidentStatus.ACKNOWLEDGED:   'Принят',
            IncidentStatus.IN_PROGRESS:    'В работе',
            IncidentStatus.RESOLVED:       'Устранён',
            IncidentStatus.FALSE_POSITIVE: 'Ложное',
            IncidentStatus.CLOSED:         'Закрыт',
        }

        S_CELL = ParagraphStyle('Cell', parent=styles['Normal'],
                                fontSize=7.5, fontName=fn, textColor=CLR_DARK,
                                leading=10, wordWrap='CJK')
        S_CELL_B = ParagraphStyle('CellB', parent=S_CELL, fontName=fn_b)

        col_w = [
            page_w * 0.13,   # Дата
            page_w * 0.17,   # Устройство
            page_w * 0.13,   # Критичность
            page_w * 0.13,   # Статус
            page_w * 0.44,   # Заголовок
        ]

        inc_data = [[
            Paragraph('Дата',        S_CELL_B),
            Paragraph('Устройство',  S_CELL_B),
            Paragraph('Критичность', S_CELL_B),
            Paragraph('Статус',      S_CELL_B),
            Paragraph('Заголовок',   S_CELL_B),
        ]]

        # Colour severity cells via Paragraph style (TEXTCOLOR doesn't apply to Paragraph cells)
        S_CELL_CRIT = ParagraphStyle('CellCrit', parent=S_CELL, textColor=CLR_RED, fontName=fn_b)
        S_CELL_WARN = ParagraphStyle('CellWarn', parent=S_CELL, textColor=CLR_YELLOW)

        # Rebuild data rows with coloured severity cell
        inc_data = [inc_data[0]]
        for inc in incidents:
            sev_txt = sev_labels.get(inc.severity, inc.severity)
            sev_style = (S_CELL_CRIT if inc.severity == IncidentSeverity.CRITICAL
                         else S_CELL_WARN if inc.severity == IncidentSeverity.WARNING
                         else S_CELL)
            inc_data.append([
                Paragraph(localtime(inc.created_at).strftime('%d.%m.%Y'), S_CELL),
                Paragraph(inc.device.serial_number, S_CELL),
                Paragraph(sev_txt, sev_style),
                Paragraph(sta_labels.get(inc.status, inc.status), S_CELL),
                Paragraph(inc.title[:120], S_CELL),
            ])

        tbl = _make_table(inc_data, col_w, font_size=7.5, repeat_header=True, fn=fn, fn_b=fn_b)
        elems.append(tbl)
    else:
        elems.append(Paragraph('Инциденты за выбранный период отсутствуют.', S_NORM))

    # ── Footer ─────────────────────────────────────────────────────────────────
    elems.append(Spacer(1, 8 * mm))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=CLR_BORDER))
    elems.append(Spacer(1, 2 * mm))
    elems.append(Paragraph(
        f'АСУТП Мониторинг v1.0 — отчёт сформирован автоматически '
        f'{now_local.strftime("%d.%m.%Y %H:%M")}',
        S_FOOTER,
    ))

    # Build with page numbers
    doc.build(elems, onFirstPage=_page_number, onLaterPages=_page_number)

    buffer.seek(0)
    filename = f'report_{period_key}d_{now_local.strftime("%Y%m%d_%H%M")}.pdf'
    resp = HttpResponse(buffer.read(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


# ── Helpers ────────────────────────────────────────────────────────────────────

def _find_logo():
    """Return absolute filesystem path to logo.png, or None."""
    try:
        from django.contrib.staticfiles import finders
        path = finders.find('img/logo.png')
        if path:
            return path
    except Exception:
        pass
    candidate = os.path.join(settings.STATIC_ROOT, 'img', 'logo.png')
    return candidate if os.path.exists(candidate) else None


def _make_table(data, col_widths, header_color=None, font_size=9, repeat_header=False,
                extra_cmds=None, fn='Helvetica', fn_b='Helvetica-Bold'):
    """Build a styled ReportLab Table with Cyrillic-capable fonts."""
    if header_color is None:
        header_color = CLR_DARK

    cmds = [
        # Header
        ('BACKGROUND',    (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR',     (0, 0), (-1, 0), CLR_WHITE),
        ('FONTNAME',      (0, 0), (-1, 0), fn_b),
        ('FONTSIZE',      (0, 0), (-1, 0), font_size),
        ('TOPPADDING',    (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('LEFTPADDING',   (0, 0), (-1, 0), 8),
        ('RIGHTPADDING',  (0, 0), (-1, 0), 8),
        # Data rows
        ('FONTNAME',      (0, 1), (-1, -1), fn),
        ('FONTSIZE',      (0, 1), (-1, -1), font_size),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [CLR_WHITE, CLR_ROW_ALT]),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('LEFTPADDING',   (0, 1), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 1), (-1, -1), 8),
        # Last column centred
        ('ALIGN',         (-1, 0), (-1, -1), 'CENTER'),
        # Grid
        ('GRID',          (0, 0), (-1, -1), 0.4, CLR_BORDER),
    ]
    if extra_cmds:
        cmds.extend(extra_cmds)

    tbl = Table(data, colWidths=col_widths, repeatRows=1 if repeat_header else 0)
    tbl.setStyle(TableStyle(cmds))
    return tbl


def _page_number(canvas, doc):
    """Draw page number at bottom-right of each page."""
    canvas.saveState()
    page_font = _FONT_REGULAR if _FONTS_OK else 'Helvetica'
    canvas.setFont(page_font, 7)
    canvas.setFillColor(CLR_MUTED)
    canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f'Страница {canvas.getPageNumber()}')
    canvas.restoreState()
