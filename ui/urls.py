from django.urls import path
from . import views

app_name = "ui"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("welcome/", views.welcome, name="welcome"),
    path("guia/", views.guia, name="guia"),
]
