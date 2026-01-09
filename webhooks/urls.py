from django.urls import path
from . import views
from payments import asaas_webhook
from payments import mercadopago_webhook

app_name = "webhooks"

urlpatterns = [
    path("n8n/events", views.receive_event, name="n8n_events"),
    path("asaas/", asaas_webhook.asaas_webhook, name="asaas"),
    path("mercadopago/", mercadopago_webhook.mercadopago_webhook, name="mercadopago"),
]

