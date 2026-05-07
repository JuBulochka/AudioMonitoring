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

from apps.devices.models import Device, DeviceStatus
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
    return render(request, 'reports/report.html', {'periods': periods})


@login_required
def generate_pdf(request):
    period_key = request.GET.get('period', '7')
    if period_key not in PERIOD_CHOICES:
        period_key = '7'

    period_label, period_days = PERIOD_CHOICES[period_key]
    now       = timezone.now()
    date_from = now - timedelta(days=period_days)

    # ── Query data ─────────────────────────────────────────────────────────────
    all_devices    = Device.objects.filter(is_active=True)
    total_devices  = all_devices.count()
    online_devices = all_devices.filter(is_online=True).count()
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

    # Incidents in period
    incidents_qs = Incident.objects.filter(created_at__gte=date_from).select_related(
        'device'
    )
    total_incidents  = incidents_qs.count()
    open_incidents   = Incident.objects.filter(
        status__in=[IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS]
    ).count()
    critical_inc = incidents_qs.filter(severity=IncidentSeverity.CRITICAL).count()
    warning_inc  = incidents_qs.filter(severity=IncidentSeverity.WARNING).count()
    info_inc     = incidents_qs.filter(severity=IncidentSeverity.INFO).count()
    incidents    = list(incidents_qs.order_by('-created_at')[:50])

    # Anomaly stats
    anomaly_qs    = AudioPacket.objects.filter(recorded_at__gte=date_from, has_anomaly=True)
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
        inc_data = [['Дата', 'Устройство', 'Критичность', 'Статус', 'Заголовок']]
        col_w = [
            page_w * 0.12, page_w * 0.16,
            page_w * 0.14, page_w * 0.14,
            page_w * 0.44,
        ]

        sev_labels = {
            IncidentSeverity.CRITICAL:    'Критично',
            IncidentSeverity.WARNING:     'Предупреждение',
            IncidentSeverity.INFO:        'Информация',
        }
        sta_labels = {
            IncidentStatus.OPEN:          'Открыт',
            IncidentStatus.ACKNOWLEDGED:  'Принят',
            IncidentStatus.IN_PROGRESS:   'В работе',
            IncidentStatus.RESOLVED:      'Устранён',
            IncidentStatus.FALSE_POSITIVE:'Ложное',
            IncidentStatus.CLOSED:        'Закрыт',
        }

        for inc in incidents:
            inc_data.append([
                localtime(inc.created_at).strftime('%d.%m.%Y'),
                inc.device.serial_number,
                sev_labels.get(inc.severity, inc.severity),
                sta_labels.get(inc.status,   inc.status),
                Paragraph(inc.title[:90], S_NORM),
            ])

        # Build severity colour commands before creating table
        ts_extra = []
        for row_idx, inc in enumerate(incidents, start=1):
            if inc.severity == IncidentSeverity.CRITICAL:
                ts_extra += [
                    ('TEXTCOLOR', (2, row_idx), (2, row_idx), CLR_RED),
                    ('FONTNAME',  (2, row_idx), (2, row_idx), 'Helvetica-Bold'),
                ]
            elif inc.severity == IncidentSeverity.WARNING:
                ts_extra.append(('TEXTCOLOR', (2, row_idx), (2, row_idx), CLR_YELLOW))

        tbl = _make_table(inc_data, col_w, font_size=8, repeat_header=True,
                          extra_cmds=ts_extra, fn=fn, fn_b=fn_b)
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
