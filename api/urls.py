from django.urls import path
from . import views

app_name = "api"

urlpatterns = [
    path("n8n/agents/<slug:slug>/config", views.get_agent_config, name="agent_config"),
]
