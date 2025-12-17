from django.urls import path
from . import views
from . import webhooks

app_name = 'payments'

urlpatterns = [
    # Configurações de pagamento
    path('settings/', views.payment_settings, name='settings'),
    
    # Stripe Connect onboarding
    path('stripe/onboarding/', views.start_onboarding, name='start_onboarding'),
    path('stripe/return/<slug:slug>/', views.onboarding_return, name='onboarding_return'),
    path('stripe/refresh/<slug:slug>/', views.onboarding_refresh, name='onboarding_refresh'),
    path('stripe/dashboard/', views.stripe_dashboard, name='stripe_dashboard'),
    
    # Stripe webhook
    path('stripe/webhook/', webhooks.stripe_webhook, name='stripe_webhook'),
    
    # Páginas de status de pagamento
    path('success/', views.payment_success, name='success'),
    path('cancel/', views.payment_cancel, name='cancel'),
]

