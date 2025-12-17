"""
Webhooks para receber eventos do Stripe.
Lida com atualizações de conta e confirmações de pagamento.
"""
import json
import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import StripeAccount, PaymentSession
from audit.models import AuditLog

stripe.api_key = settings.STRIPE_SECRET_KEY


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """
    Endpoint para receber webhooks do Stripe.
    Processa eventos como account.updated e checkout.session.completed.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    # Verifica a assinatura do webhook (somente se tiver webhook secret configurado)
    event = None
    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            # Payload inválido
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            # Assinatura inválida
            return HttpResponse(status=400)
    else:
        # Em desenvolvimento, aceita sem verificar assinatura
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return HttpResponse(status=400)
    
    event_type = event.get('type', '')
    data = event.get('data', {}).get('object', {})
    
    # Handlers para diferentes tipos de eventos
    handlers = {
        'account.updated': handle_account_updated,
        'checkout.session.completed': handle_checkout_completed,
        'checkout.session.expired': handle_checkout_expired,
    }
    
    handler = handlers.get(event_type)
    if handler:
        try:
            handler(data)
        except Exception as e:
            # Log do erro mas retorna 200 para não reenviar
            print(f"Webhook handler error: {e}")
    
    return HttpResponse(status=200)


def handle_account_updated(account_data):
    """
    Atualiza status da conta Stripe quando ela é modificada.
    """
    account_id = account_data.get('id')
    
    try:
        stripe_account = StripeAccount.objects.get(stripe_account_id=account_id)
    except StripeAccount.DoesNotExist:
        return
    
    # Atualiza campos de status
    stripe_account.charges_enabled = account_data.get('charges_enabled', False)
    stripe_account.payouts_enabled = account_data.get('payouts_enabled', False)
    stripe_account.details_submitted = account_data.get('details_submitted', False)
    stripe_account.is_onboarding_complete = (
        stripe_account.details_submitted and
        stripe_account.charges_enabled and
        stripe_account.payouts_enabled
    )
    stripe_account.save()
    
    # Log da atualização
    AuditLog.log(
        action="stripe_account_updated",
        entity="stripe_account",
        organization=stripe_account.padaria,
        entity_id=str(stripe_account.id),
        diff={
            "charges_enabled": stripe_account.charges_enabled,
            "payouts_enabled": stripe_account.payouts_enabled,
            "details_submitted": stripe_account.details_submitted,
        }
    )


def handle_checkout_completed(session_data):
    """
    Processa pagamento concluído com sucesso.
    """
    session_id = session_data.get('id')
    
    try:
        payment_session = PaymentSession.objects.get(stripe_session_id=session_id)
    except PaymentSession.DoesNotExist:
        return
    
    from django.utils import timezone
    
    payment_session.status = 'completed'
    payment_session.completed_at = timezone.now()
    payment_session.save()
    
    # Log do pagamento
    AuditLog.log(
        action="payment_completed",
        entity="payment_session",
        organization=payment_session.padaria,
        entity_id=str(payment_session.id),
        diff={
            "amount": float(payment_session.amount),
            "customer_phone": payment_session.customer_phone,
            "session_id": session_id,
        }
    )


def handle_checkout_expired(session_data):
    """
    Marca sessão como expirada.
    """
    session_id = session_data.get('id')
    
    try:
        payment_session = PaymentSession.objects.get(stripe_session_id=session_id)
    except PaymentSession.DoesNotExist:
        return
    
    payment_session.status = 'expired'
    payment_session.save()
