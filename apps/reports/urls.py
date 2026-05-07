from django.urls import path
from . import views

urlpatterns = [
    path('', views.report_page, name='reports'),
    path('pdf/', views.generate_pdf, name='report-pdf'),
]
