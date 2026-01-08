"""
Webhook para receber eventos do Asaas.
Processa pagamentos e atualiza status de assinaturas.
"""
import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils import timezone

from payments.models import AsaasSubscription, AsaasPayment
from audit.models import AuditLog

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def asaas_webhook(request):
    """
    Endpoint para receber webhooks do Asaas.
    URL: /webhooks/asaas/
    
    Eventos processados:
    - PAYMENT_CREATED: Cobrança criada
    - PAYMENT_RECEIVED: Pagamento recebido
    - PAYMENT_CONFIRMED: Pagamento confirmado
    - PAYMENT_OVERDUE: Cobrança vencida
    - PAYMENT_DELETED: Cobrança removida
    - PAYMENT_REFUNDED: Cobrança estornada
    - SUBSCRIPTION_CREATED: Assinatura criada
    - SUBSCRIPTION_UPDATED: Assinatura atualizada
    - SUBSCRIPTION_DELETED: Assinatura removida
    """
    # Validar token de autenticação
    auth_token = request.headers.get("asaas-access-token", "")
    if not auth_token:
        # Tenta pegar do query param (alternativa)
        auth_token = request.GET.get("token", "")
    
    expected_token = settings.ASAAS_WEBHOOK_TOKEN
    if auth_token != expected_token:
        logger.warning(f"Asaas webhook: token inválido recebido")
        return HttpResponse(status=401)
    
    # Parse do payload
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        logger.error("Asaas webhook: JSON inválido")
        return HttpResponse(status=400)
    
    event = payload.get("event")
    payment_data = payload.get("payment", {})
    subscription_data = payload.get("subscription", {})
    
    logger.info(f"Asaas webhook recebido: {event}")
    
    # Handlers para cada tipo de evento
    handlers = {
        "PAYMENT_CREATED": handle_payment_created,
        "PAYMENT_RECEIVED": handle_payment_received,
        "PAYMENT_CONFIRMED": handle_payment_confirmed,
        "PAYMENT_OVERDUE": handle_payment_overdue,
        "PAYMENT_DELETED": handle_payment_deleted,
        "PAYMENT_REFUNDED": handle_payment_refunded,
        "SUBSCRIPTION_CREATED": handle_subscription_created,
        "SUBSCRIPTION_UPDATED": handle_subscription_updated,
        "SUBSCRIPTION_DELETED": handle_subscription_deleted,
    }
    
    handler = handlers.get(event)
    if handler:
        try:
            handler(payment_data or subscription_data, payload)
        except Exception as e:
            logger.exception(f"Erro ao processar webhook {event}: {e}")
            # Retorna 200 mesmo com erro para não reenviar
    else:
        logger.info(f"Evento não processado: {event}")
    
    return HttpResponse(status=200)


# =============================================================================
# Handlers de Pagamento
# =============================================================================

def handle_payment_created(data, full_payload):
    """Processa evento PAYMENT_CREATED."""
    payment_id = data.get("id")
    subscription_id = data.get("subscription")
    
    if not subscription_id:
        return  # Não é pagamento de assinatura
    
    try:
        subscription = AsaasSubscription.objects.get(
            asaas_subscription_id=subscription_id
        )
    except AsaasSubscription.DoesNotExist:
        logger.warning(f"Assinatura não encontrada: {subscription_id}")
        return
    
    # Criar registro do pagamento
    AsaasPayment.objects.update_or_create(
        asaas_payment_id=payment_id,
        defaults={
            "subscription": subscription,
            "value": data.get("value", 0),
            "due_date": data.get("dueDate"),
            "billing_type": data.get("billingType", "PIX"),
            "invoice_url": data.get("invoiceUrl", ""),
            "status": "pending",
        }
    )
    
    # Atualizar link de pagamento atual
    subscription.current_payment_id = payment_id
    subscription.current_payment_link = data.get("invoiceUrl", "")
    subscription.save(update_fields=["current_payment_id", "current_payment_link", "updated_at"])
    
    # Log
    AuditLog.log(
        action="asaas_payment_created",
        entity="asaas_payment",
        organization=subscription.padaria,
        entity_id=payment_id,
        diff={"value": data.get("value"), "due_date": data.get("dueDate")}
    )


def handle_payment_received(data, full_payload):
    """Processa evento PAYMENT_RECEIVED - Pagamento confirmado."""
    payment_id = data.get("id")
    subscription_id = data.get("subscription")
    
    # Atualizar pagamento
    try:
        payment = AsaasPayment.objects.get(asaas_payment_id=payment_id)
        payment.status = "received"
        payment.payment_date = timezone.now().date()
        payment.save()
    except AsaasPayment.DoesNotExist:
        pass
    
    # Atualizar assinatura
    if subscription_id:
        try:
            subscription = AsaasSubscription.objects.get(
                asaas_subscription_id=subscription_id
            )
            subscription.status = "active"
            subscription.last_payment_date = timezone.now().date()
            # Próximo vencimento = 30 dias
            subscription.next_due_date = (
                timezone.now() + timezone.timedelta(days=30)
            ).date()
            subscription.current_payment_id = ""
            subscription.current_payment_link = ""
            subscription.save()
            
            # Log
            AuditLog.log(
                action="subscription_activated",
                entity="asaas_subscription",
                organization=subscription.padaria,
                entity_id=str(subscription.id),
                diff={"status": "active", "payment_id": payment_id}
            )
        except AsaasSubscription.DoesNotExist:
            logger.warning(f"Assinatura não encontrada: {subscription_id}")


def handle_payment_confirmed(data, full_payload):
    """Processa evento PAYMENT_CONFIRMED."""
    # Mesmo tratamento de PAYMENT_RECEIVED
    handle_payment_received(data, full_payload)


def handle_payment_overdue(data, full_payload):
    """Processa evento PAYMENT_OVERDUE - Cobrança vencida."""
    payment_id = data.get("id")
    subscription_id = data.get("subscription")
    
    # Atualizar pagamento
    try:
        payment = AsaasPayment.objects.get(asaas_payment_id=payment_id)
        payment.status = "overdue"
        payment.save()
    except AsaasPayment.DoesNotExist:
        pass
    
    # Atualizar assinatura para inadimplente
    if subscription_id:
        try:
            subscription = AsaasSubscription.objects.get(
                asaas_subscription_id=subscription_id
            )
            subscription.status = "overdue"
            subscription.save()
            
            # Log
            AuditLog.log(
                action="subscription_overdue",
                entity="asaas_subscription",
                organization=subscription.padaria,
                entity_id=str(subscription.id),
                diff={"status": "overdue", "payment_id": payment_id}
            )
        except AsaasSubscription.DoesNotExist:
            pass


def handle_payment_deleted(data, full_payload):
    """Processa evento PAYMENT_DELETED."""
    payment_id = data.get("id")
    
    try:
        payment = AsaasPayment.objects.get(asaas_payment_id=payment_id)
        payment.status = "deleted"
        payment.save()
    except AsaasPayment.DoesNotExist:
        pass


def handle_payment_refunded(data, full_payload):
    """Processa evento PAYMENT_REFUNDED - Estorno."""
    payment_id = data.get("id")
    
    try:
        payment = AsaasPayment.objects.get(asaas_payment_id=payment_id)
        payment.status = "refunded"
        payment.save()
    except AsaasPayment.DoesNotExist:
        pass


# =============================================================================
# Handlers de Assinatura
# =============================================================================

def handle_subscription_created(data, full_payload):
    """Processa evento SUBSCRIPTION_CREATED."""
    subscription_id = data.get("id")
    customer_id = data.get("customer")
    
    # Buscar assinatura existente pelo customer_id
    try:
        subscription = AsaasSubscription.objects.get(
            asaas_customer_id=customer_id
        )
        subscription.asaas_subscription_id = subscription_id
        subscription.status = "pending"
        subscription.plan_value = data.get("value", 0)
        subscription.billing_type = data.get("billingType", "PIX")
        subscription.next_due_date = data.get("nextDueDate")
        subscription.save()
    except AsaasSubscription.DoesNotExist:
        logger.warning(f"Assinatura local não encontrada para customer: {customer_id}")


def handle_subscription_updated(data, full_payload):
    """Processa evento SUBSCRIPTION_UPDATED."""
    subscription_id = data.get("id")
    
    try:
        subscription = AsaasSubscription.objects.get(
            asaas_subscription_id=subscription_id
        )
        
        # Atualizar campos
        if "value" in data:
            subscription.plan_value = data["value"]
        if "billingType" in data:
            subscription.billing_type = data["billingType"]
        if "nextDueDate" in data:
            subscription.next_due_date = data["nextDueDate"]
        
        subscription.save()
    except AsaasSubscription.DoesNotExist:
        pass


def handle_subscription_deleted(data, full_payload):
    """Processa evento SUBSCRIPTION_DELETED - Cancelamento."""
    subscription_id = data.get("id")
    
    try:
        subscription = AsaasSubscription.objects.get(
            asaas_subscription_id=subscription_id
        )
        subscription.status = "cancelled"
        subscription.save()
        
        # Log
        AuditLog.log(
            action="subscription_cancelled",
            entity="asaas_subscription",
            organization=subscription.padaria,
            entity_id=str(subscription.id),
            diff={"status": "cancelled"}
        )
    except AsaasSubscription.DoesNotExist:
        pass
