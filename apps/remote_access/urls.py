from django.urls import path
from . import views

urlpatterns = [
    path("", views.remote_access_log, name="remote-access-log"),
    path("verify/<uuid:device_id>/", views.verify_access, name="remote-verify"),
    path("terminal/<uuid:device_id>/", views.terminal, name="remote-terminal"),
    path("commands/<uuid:device_id>/", views.commands, name="remote-commands"),
]
