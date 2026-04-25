"""Standalone maintenance task endpoints."""
from api.v1.incident_endpoints import (
    MaintenanceTaskListCreateView,
    MaintenanceTaskStatusView,
)
from django.urls import path

urlpatterns = [
    path("", MaintenanceTaskListCreateView.as_view(), name="api-task-list"),
    path("<uuid:id>/status/", MaintenanceTaskStatusView.as_view(), name="api-task-status"),
]
