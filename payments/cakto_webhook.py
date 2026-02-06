"""
Cakto Webhook Handler
Processa webhooks da Cakto para eventos de pagamento.
"""
import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from payments.services.cakto_service import cakto_service

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def cakto_webhook(request):
    """
    Endpoint para receber webhooks da Cakto.
    
    Eventos suportados:
    - purchase_approved: Pagamento aprovado
    - subscription_canceled: Assinatura cancelada
    - payment_rejected: Pagamento rejeitado
    - pix_generated: PIX gerado (informativo)
    """
    try:
        # Verificar token de autenticação
        auth_header = request.headers.get("Authorization", "")
        webhook_token = request.headers.get("X-Webhook-Token", "")
        
        # Aceitar token no header Authorization ou X-Webhook-Token
        expected_token = settings.CAKTO_WEBHOOK_TOKEN
        if expected_token:
            if auth_header != f"Bearer {expected_token}" and webhook_token != expected_token:
                logger.warning("Cakto webhook: Token inválido")
                return JsonResponse({"error": "Unauthorized"}, status=401)
        
        # Parse do body
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Cakto webhook: JSON inválido")
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        # Identificar tipo de evento
        event_type = payload.get("event") or payload.get("type") or payload.get("event_type")
        
        if not event_type:
            logger.warning(f"Cakto webhook: Tipo de evento não identificado. Payload: {payload}")
            # Tenta identificar pelo conteúdo
            if payload.get("status") == "approved" or payload.get("payment_status") == "approved":
                event_type = "purchase_approved"
            elif payload.get("status") == "canceled":
                event_type = "subscription_canceled"
        
        logger.info(f"Cakto webhook recebido: {event_type}")
        logger.debug(f"Cakto webhook payload: {json.dumps(payload, indent=2)}")
        
        # Processar evento
        result = {"status": "ignored"}
        
        if event_type in ["purchase_approved", "payment_approved", "charge_confirmed"]:
            result = cakto_service.process_payment_approved(payload)
            
        elif event_type in ["subscription_canceled", "subscription_cancelled"]:
            result = cakto_service.process_subscription_canceled(payload)
            
        elif event_type in ["payment_rejected", "charge_rejected", "charge_failed"]:
            result = cakto_service.process_payment_rejected(payload)
            
        elif event_type in ["pix_generated", "qrcode_generated"]:
            # Evento informativo, apenas loga
            logger.info(f"Cakto: PIX gerado - Order {payload.get('order_id')}")
            result = {"status": "acknowledged"}
            
        else:
            logger.info(f"Cakto webhook: Evento não processado: {event_type}")
            result = {"status": "ignored", "event": event_type}
        
        # Retornar sucesso para a Cakto
        return JsonResponse({
            "received": True,
            "event": event_type,
            "result": result.get("status", "processed") if isinstance(result, dict) else "processed"
        })
        
    except Exception as e:
        logger.exception(f"Erro no webhook Cakto: {str(e)}")
        # Retornar 200 mesmo em erro para a Cakto não retentar
        return JsonResponse({
            "received": True,
            "error": "Internal processing error"
        })
