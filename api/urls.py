from django.urls import path
from . import views
# from . import payments  # TODO v2: Stripe payments

app_name = "api"

urlpatterns = [
    path("docs/", views.api_docs, name="docs"),
    path("n8n/agents/<slug:slug>/config", views.get_agent_config, name="agent_config"),
    path("n8n/agents/<slug:slug>/knowledge", views.get_agent_knowledge, name="agent_knowledge"),
    
    # TODO v2: Payment API
    # path("payments/check-enabled/", payments.check_payments_enabled, name="payments_check_enabled"),
    # path("payments/create-checkout/", payments.create_checkout, name="payments_create_checkout"),
    # path("payments/status/<str:session_id>/", payments.get_payment_status, name="payments_status"),
]

