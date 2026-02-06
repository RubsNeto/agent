from django.urls import path
from . import views
from . import api_views
from .cakto_webhook import cakto_webhook

app_name = 'payments'

urlpatterns = [
    # === Assinatura Cakto (Novo sistema) ===
    path('assinatura/', views.subscription_status, name='subscription_status'),
    path('assinatura/lista/', views.subscription_list, name='subscription_list'),
    path('assinatura/criar/', views.create_subscription, name='create_subscription'),
    path('assinatura/nova-padaria/', views.create_padaria_subscription, name='create_padaria_subscription'),
    path('assinatura/cancelar/', views.cancel_subscription, name='cancel_subscription'),
    path('assinatura/link/', views.subscription_payment_link, name='subscription_payment_link'),
    path('assinatura/cadastrar-cartao/', views.cakto_register_card, name='cakto_register_card'),
    path('assinatura/test-action/', views.subscription_test_action, name='subscription_test_action'),
    path('assinatura/sincronizar/', views.sync_cakto_status, name='sync_cakto_status'),
    
    # === Webhook Cakto ===
    path('cakto/webhook/', cakto_webhook, name='cakto_webhook'),
    
    # === Mercado Pago (Padaria -> Cliente) ===
    path('mercadopago/', views.mercadopago_config, name='mercadopago_config'),
    path('mercadopago/testar/', views.mercadopago_test_connection, name='mercadopago_test'),
    path('mercadopago/criar-pagamento/', views.mercadopago_create_payment, name='mercadopago_create_payment'),
    path('mercadopago/status/<int:payment_id>/', views.mercadopago_payment_status, name='mercadopago_payment_status'),
    
    # === Páginas de status ===
    path('success/', views.payment_success, name='success'),
    path('assinatura/success/', views.payment_success, name='subscription_success'),
    path('cancel/', views.payment_cancel, name='cancel'),
    
    # === Mercado Pago - Páginas de Retorno ===
    path('mp/return/', views.mp_payment_return, name='mp_return'),
    path('mp/pay/<int:payment_id>/', views.mp_checkout_gate, name='mp_checkout_gate'),
    
    # === API para Agentes (WhatsApp/n8n) ===
    path('api/cart/', api_views.create_cart_payment, name='api_create_cart'),
    path('api/generate-link/', api_views.create_payment_link, name='api_generate_link'),
    path('api/<str:payment_id>/status/', api_views.get_payment_status, name='api_payment_status'),
    
    # === API de Monitoramento de Status ===
    path('api/check/<int:payment_id>/', api_views.check_payment_status, name='api_check_payment'),
    path('api/pending/', api_views.list_pending_payments, name='api_list_pending'),
    path('api/sync-pending/', api_views.sync_all_pending_payments, name='api_sync_pending'),
    
    # === API de Monitoramento Automático ===
    path('api/monitor/<int:payment_id>/start/', api_views.start_monitor, name='api_start_monitor'),
    path('api/monitors/', api_views.get_active_monitors, name='api_active_monitors'),
    path('api/monitors/start-all/', api_views.start_bulk_monitor, name='api_start_bulk_monitor'),
    
    # === Legado (Stripe) - Mantidos para compatibilidade ===
    path('settings/', views.payment_settings, name='settings'),
    path('stripe/onboarding/', views.start_onboarding, name='start_onboarding'),
    path('stripe/return/<slug:slug>/', views.onboarding_return, name='onboarding_return'),
    path('stripe/refresh/<slug:slug>/', views.onboarding_refresh, name='onboarding_refresh'),
    path('stripe/dashboard/', views.stripe_dashboard, name='stripe_dashboard'),
]
