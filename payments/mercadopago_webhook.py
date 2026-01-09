"""
Webhook para receber eventos do Mercado Pago.
Processa notificações de pagamento e atualiza status.
"""
import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from payments.models import MercadoPagoPayment, MercadoPagoConfig
from payments.services.mercadopago_service import MercadoPagoService
from audit.models import AuditLog

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def mercadopago_webhook(request):
    """
    Endpoint para receber webhooks do Mercado Pago.
    URL: /webhooks/mercadopago/
    
    O Mercado Pago envia notificações IPN (Instant Payment Notification)
    quando o status de um pagamento muda.
    
    Documentação: https://www.mercadopago.com.br/developers/pt/docs/notifications
    """
    try:
        # Parse do payload
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.error("Mercado Pago webhook: JSON inválido")
            return HttpResponse(status=400)
        
        # O Mercado Pago envia diferentes tipos de notificação
        topic = payload.get("type") or request.GET.get("topic") or payload.get("topic")
        resource_id = payload.get("data", {}).get("id") or request.GET.get("id")
        
        logger.info(f"Mercado Pago webhook recebido: topic={topic}, resource_id={resource_id}")
        
        # Verificar se é notificação de pagamento
        if topic == "payment" and resource_id:
            handle_payment_notification(resource_id)
        elif topic == "payment.created" or topic == "payment.updated":
            # Formato webhook v2
            handle_payment_notification(resource_id)
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.exception(f"Erro ao processar webhook Mercado Pago: {e}")
        # Retorna 200 para evitar reenvio
        return HttpResponse(status=200)


def handle_payment_notification(mp_payment_id: str):
    """
    Processa notificação de pagamento do Mercado Pago.
    Busca detalhes do pagamento na API e atualiza o status local.
    """
    if not mp_payment_id:
        return
    
    # Buscar todos os configs para encontrar o pagamento
    # (não sabemos de qual config veio a notificação)
    for mp_config in MercadoPagoConfig.objects.filter(is_active=True):
        try:
            mp_service = MercadoPagoService(mp_config.access_token)
            payment_data = mp_service.get_payment(str(mp_payment_id))
            
            if not payment_data:
                continue
            
            status = payment_data.get("status", "")
            external_reference = payment_data.get("external_reference", "")
            preference_id = payment_data.get("preference_id", "")
            
            logger.info(f"MP Payment {mp_payment_id}: status={status}, preference_id={preference_id}")
            
            # Buscar pagamento local por preference_id ou mp_payment_id
            payment = None
            
            if preference_id:
                payment = MercadoPagoPayment.objects.filter(
                    config=mp_config,
                    mp_preference_id=preference_id
                ).first()
            
            if not payment:
                payment = MercadoPagoPayment.objects.filter(
                    config=mp_config,
                    mp_payment_id=str(mp_payment_id)
                ).first()
            
            if payment:
                old_status = payment.status
                payment.status = status
                payment.mp_payment_id = str(mp_payment_id)
                
                if status == "approved":
                    payment.paid_at = timezone.now()
                
                payment.save()
                
                logger.info(f"Pagamento {payment.id} atualizado: {old_status} -> {status}")
                
                # Log de auditoria
                AuditLog.log(
                    action="mercadopago_payment_updated",
                    entity="mercadopago_payment",
                    organization=mp_config.padaria,
                    entity_id=str(payment.id),
                    diff={
                        "old_status": old_status,
                        "new_status": status,
                        "mp_payment_id": str(mp_payment_id),
                    }
                )
                
                return  # Encontrou e atualizou, pode parar
            
        except Exception as e:
            logger.warning(f"Erro ao processar pagamento {mp_payment_id} com config {mp_config.id}: {e}")
            continue
    
    logger.warning(f"Pagamento MP {mp_payment_id} não encontrado no sistema")
