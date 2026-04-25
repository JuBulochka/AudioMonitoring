from django.contrib import admin
from .models import AudioPacket, AudioClassScore, DailyDeviceMetrics


class AudioClassScoreInline(admin.TabularInline):
    model = AudioClassScore
    extra = 0
    readonly_fields = ["audio_class", "score", "threshold_exceeded"]


@admin.register(AudioPacket)
class AudioPacketAdmin(admin.ModelAdmin):
    list_display = [
        "device", "recorded_at", "severity", "dominant_class",
        "dominant_class_score", "has_anomaly", "operator_status",
    ]
    list_filter = ["severity", "has_anomaly", "operator_status", "dominant_class"]
    search_fields = ["device__serial_number"]
    date_hierarchy = "recorded_at"
    readonly_fields = ["id", "received_at", "raw_analysis"]
    inlines = [AudioClassScoreInline]


@admin.register(DailyDeviceMetrics)
class DailyDeviceMetricsAdmin(admin.ModelAdmin):
    list_display = ["device", "date", "total_packets", "anomaly_packets", "critical_packets"]
    list_filter = ["date"]
    date_hierarchy = "date"
