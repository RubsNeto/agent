from django.urls import path
from . import views
from payments import asaas_webhook

app_name = "webhooks"

urlpatterns = [
    path("n8n/events", views.receive_event, name="n8n_events"),
    path("asaas/", asaas_webhook.asaas_webhook, name="asaas"),
]
