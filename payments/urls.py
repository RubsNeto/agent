from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # === Assinatura (SaaS -> Padaria) ===
    path('assinatura/', views.subscription_status, name='subscription_status'),
    path('assinatura/lista/', views.subscription_list, name='subscription_list'),
    path('assinatura/criar/', views.create_subscription, name='create_subscription'),
    path('assinatura/nova-padaria/', views.create_padaria_subscription, name='create_padaria_subscription'),
    path('assinatura/cancelar/', views.cancel_subscription, name='cancel_subscription'),
    path('assinatura/link/', views.subscription_payment_link, name='subscription_payment_link'),
    
    # === Mercado Pago (Padaria -> Cliente) ===
    path('mercadopago/', views.mercadopago_config, name='mercadopago_config'),
    path('mercadopago/testar/', views.mercadopago_test_connection, name='mercadopago_test'),
    path('mercadopago/criar-pagamento/', views.mercadopago_create_payment, name='mercadopago_create_payment'),
    
    # === Páginas de status ===
    path('success/', views.payment_success, name='success'),
    path('cancel/', views.payment_cancel, name='cancel'),
    
    # === Legado (Stripe) - Mantidos para compatibilidade ===
    path('settings/', views.payment_settings, name='settings'),
    path('stripe/onboarding/', views.start_onboarding, name='start_onboarding'),
    path('stripe/return/<slug:slug>/', views.onboarding_return, name='onboarding_return'),
    path('stripe/refresh/<slug:slug>/', views.onboarding_refresh, name='onboarding_refresh'),
    path('stripe/dashboard/', views.stripe_dashboard, name='stripe_dashboard'),
]
