from django.urls import path
from . import views

urlpatterns = [
    path("", views.incident_list, name="incident-list"),
    path("<uuid:incident_id>/", views.incident_detail, name="incident-detail"),
    path("maintenance/", views.maintenance_list, name="maintenance-list"),
]
