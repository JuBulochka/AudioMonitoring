from django.urls import path
from . import views, operator_views

urlpatterns = [
    path("login/",  views.login_view,  name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("operators/",                        operator_views.operator_list,        name="operator-list"),
    path("operators/create/",                 operator_views.operator_create,      name="operator-create"),
    path("operators/<int:pk>/",               operator_views.operator_detail,      name="operator-detail"),
    path("operators/<int:pk>/credentials/",   operator_views.operator_credentials, name="operator-credentials"),
]
