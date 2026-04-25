from django.urls import path
from . import views

urlpatterns = [
    path("", views.device_list, name="device-list"),
    path("new/", views.device_create, name="device-create"),
    path("map/", views.device_map, name="device-map"),
    path("<uuid:device_id>/", views.device_detail, name="device-detail"),
    path("<uuid:device_id>/setup/", views.device_setup, name="device-setup"),
]
