from django.urls import path
from . import views

app_name = "api"

urlpatterns = [
    path("docs/", views.api_docs, name="docs"),
    path("n8n/agents/<slug:slug>/config", views.get_agent_config, name="agent_config"),
    path("n8n/agents/<slug:slug>/knowledge", views.get_agent_knowledge, name="agent_knowledge"),
]
