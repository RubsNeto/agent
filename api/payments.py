"""
API endpoints for chatbot payment integration.
Allows n8n/chatbot to create checkout sessions and check payment status.
"""
import json
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from core.utils import require_api_key, get_client_ip
from audit.models import AuditLog
from payments import services
from payments.models import PaymentSession


@csrf_exempt
@require_http_methods(["POST"])
@require_api_key
def create_checkout(request):
    """
    Cria uma sessão de checkout do Stripe.
    
    Request body:
    {
        "amount": 50.00,
        "description": "Pedido: 2x Pão Francês, 1x Café",
        "customer_phone": "5511999999999",
        "customer_name": "João Silva"
    }
    
    Response:
    {
        "success": true,
        "checkout_url": "https://checkout.stripe.com/...",
        "session_id": "cs_...",
        "payment_session_id": 123
    }
    """
    padaria = request.api_key.padaria
    
    # Verifica se padaria tem Stripe configurado
    stripe_account = getattr(padaria, 'stripe_account', None)
    if not stripe_account or not stripe_account.charges_enabled:
        return JsonResponse({
            "success": False,
            "error": "stripe_not_configured",
            "message": "Esta padaria não tem conta Stripe configurada para pagamentos."
        }, status=400)
    
    # Parse request body
    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "error": "invalid_json",
            "message": "JSON inválido no corpo da requisição."
        }, status=400)
    
    # Valida campos obrigatórios
    amount = data.get('amount')
    description = data.get('description', 'Pedido via WhatsApp')
    customer_phone = data.get('customer_phone', '')
    customer_name = data.get('customer_name', '')
    
    if not amount:
        return JsonResponse({
            "success": False,
            "error": "missing_amount",
            "message": "Campo 'amount' é obrigatório."
        }, status=400)
    
    # Valida e converte amount
    try:
        amount = Decimal(str(amount))
        if amount <= 0:
            raise InvalidOperation("Amount must be positive")
    except (InvalidOperation, ValueError):
        return JsonResponse({
            "success": False,
            "error": "invalid_amount",
            "message": "Valor 'amount' inválido. Use um número positivo."
        }, status=400)
    
    # Cria a sessão de checkout
    try:
        result = services.create_checkout_session(
            padaria=padaria,
            amount=amount,
            description=description,
            customer_phone=customer_phone,
            customer_name=customer_name
        )
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": "stripe_error",
            "message": str(e)
        }, status=500)
    
    # Log da requisição
    AuditLog.log(
        action="api_create_checkout",
        entity="payment_session",
        padaria=padaria,
        entity_id=str(result['payment_session_id']),
        diff={
            "amount": float(amount),
            "description": description,
            "customer_phone": customer_phone,
        },
        ip=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")
    )
    
    return JsonResponse({
        "success": True,
        "checkout_url": result['checkout_url'],
        "session_id": result['session_id'],
        "payment_session_id": result['payment_session_id']
    })


@csrf_exempt
@require_http_methods(["GET"])
@require_api_key
def get_payment_status(request, session_id):
    """
    Verifica o status de um pagamento.
    
    Response:
    {
        "success": true,
        "session_id": "cs_...",
        "status": "completed"|"pending"|"expired"|"failed",
        "amount": 50.00,
        "customer_phone": "5511999999999",
        "completed_at": "2024-01-01T12:00:00Z"
    }
    """
    padaria = request.api_key.padaria
    
    # Busca a sessão de pagamento
    try:
        payment_session = PaymentSession.objects.get(
            stripe_session_id=session_id,
            padaria=padaria
        )
    except PaymentSession.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "not_found",
            "message": "Sessão de pagamento não encontrada."
        }, status=404)
    
    # Atualiza status se necessário
    try:
        status_info = services.get_session_status(session_id)
    except Exception:
        status_info = None
    
    return JsonResponse({
        "success": True,
        "session_id": session_id,
        "status": payment_session.status,
        "amount": float(payment_session.amount),
        "customer_phone": payment_session.customer_phone,
        "customer_name": payment_session.customer_name,
        "created_at": payment_session.created_at.isoformat(),
        "completed_at": payment_session.completed_at.isoformat() if payment_session.completed_at else None
    })


@csrf_exempt
@require_http_methods(["GET"])
@require_api_key
def check_payments_enabled(request):
    """
    Verifica se a padaria tem pagamentos habilitados.
    Útil para o chatbot saber se pode oferecer pagamento online.
    
    Response:
    {
        "success": true,
        "payments_enabled": true,
        "account_status": {
            "charges_enabled": true,
            "payouts_enabled": true
        }
    }
    """
    padaria = request.api_key.padaria
    
    stripe_account = getattr(padaria, 'stripe_account', None)
    
    if not stripe_account:
        return JsonResponse({
            "success": True,
            "payments_enabled": False,
            "account_status": None
        })
    
    return JsonResponse({
        "success": True,
        "payments_enabled": stripe_account.charges_enabled,
        "account_status": {
            "charges_enabled": stripe_account.charges_enabled,
            "payouts_enabled": stripe_account.payouts_enabled,
            "is_fully_enabled": stripe_account.is_fully_enabled
        }
    })
