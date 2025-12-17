"""
Serviços de integração com Stripe Connect.
Gerencia criação de contas, onboarding e pagamentos.
"""
import stripe
from django.conf import settings
from django.urls import reverse
from .models import StripeAccount, PaymentSession

# Configura o Stripe com a chave secreta
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_account(padaria):
    """
    Cria uma conta Express no Stripe Connect para a padaria.
    Retorna o StripeAccount criado.
    """
    # Verifica se já existe conta
    if hasattr(padaria, 'stripe_account'):
        return padaria.stripe_account
    
    # Cria conta Express no Stripe
    account = stripe.Account.create(
        type="express",
        country="BR",
        email=padaria.email if padaria.email else None,
        business_type="company",
        company={
            "name": padaria.name,
        },
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        metadata={
            "padaria_id": str(padaria.id),
            "padaria_slug": padaria.slug,
        }
    )
    
    # Salva no banco de dados
    stripe_account = StripeAccount.objects.create(
        padaria=padaria,
        stripe_account_id=account.id,
    )
    
    return stripe_account


def get_onboarding_link(padaria, request=None):
    """
    Gera um link de onboarding do Stripe Connect para a padaria.
    O link expira após uso ou 24h.
    """
    stripe_account = getattr(padaria, 'stripe_account', None)
    
    if not stripe_account:
        stripe_account = create_stripe_account(padaria)
    
    # URLs de retorno
    base_url = request.build_absolute_uri('/') if request else settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000/'
    refresh_url = f"{base_url.rstrip('/')}/payments/stripe/refresh/{padaria.slug}/"
    return_url = f"{base_url.rstrip('/')}/payments/stripe/return/{padaria.slug}/"
    
    # Cria o link de onboarding
    account_link = stripe.AccountLink.create(
        account=stripe_account.stripe_account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    
    return account_link.url


def get_account_status(padaria):
    """
    Verifica o status atual da conta Stripe da padaria.
    Atualiza os campos no banco de dados.
    """
    stripe_account = getattr(padaria, 'stripe_account', None)
    
    if not stripe_account:
        return None
    
    # Busca dados atualizados do Stripe
    account = stripe.Account.retrieve(stripe_account.stripe_account_id)
    
    # Atualiza status no banco
    stripe_account.charges_enabled = account.charges_enabled
    stripe_account.payouts_enabled = account.payouts_enabled
    stripe_account.details_submitted = account.details_submitted
    stripe_account.is_onboarding_complete = (
        account.details_submitted and 
        account.charges_enabled and 
        account.payouts_enabled
    )
    stripe_account.save()
    
    return {
        "account_id": stripe_account.stripe_account_id,
        "charges_enabled": stripe_account.charges_enabled,
        "payouts_enabled": stripe_account.payouts_enabled,
        "details_submitted": stripe_account.details_submitted,
        "is_fully_enabled": stripe_account.is_fully_enabled,
    }


def get_dashboard_link(padaria):
    """
    Gera um link para o dashboard Express do Stripe.
    Permite que o dono da padaria veja transações e configure conta.
    """
    stripe_account = getattr(padaria, 'stripe_account', None)
    
    if not stripe_account or not stripe_account.is_fully_enabled:
        return None
    
    login_link = stripe.Account.create_login_link(
        stripe_account.stripe_account_id
    )
    
    return login_link.url


def create_checkout_session(padaria, amount, description, customer_phone=None, customer_name=None, success_url=None, cancel_url=None):
    """
    Cria uma sessão de checkout do Stripe.
    O pagamento vai direto para a conta Connect da padaria.
    
    Args:
        padaria: Padaria que receberá o pagamento
        amount: Valor em reais (Decimal)
        description: Descrição do pedido
        customer_phone: Telefone do cliente (WhatsApp)
        customer_name: Nome do cliente
        success_url: URL de redirecionamento após sucesso
        cancel_url: URL de redirecionamento após cancelamento
    
    Returns:
        dict com checkout_url e session_id
    """
    stripe_account = getattr(padaria, 'stripe_account', None)
    
    if not stripe_account or not stripe_account.charges_enabled:
        raise ValueError("Padaria não tem conta Stripe habilitada para pagamentos")
    
    # Converte para centavos
    amount_cents = int(float(amount) * 100)
    
    # URLs padrão
    base_url = settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000'
    success_url = success_url or f"{base_url}/payments/success/"
    cancel_url = cancel_url or f"{base_url}/payments/cancel/"
    
    # Cria a sessão de checkout
    # Usando destination charges - o dinheiro vai para a conta conectada
    session = stripe.checkout.Session.create(
        payment_method_types=["card", "boleto", "pix"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {
                    "name": f"Pedido - {padaria.name}",
                    "description": description,
                },
                "unit_amount": amount_cents,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        payment_intent_data={
            "transfer_data": {
                "destination": stripe_account.stripe_account_id,
            },
            "metadata": {
                "padaria_id": str(padaria.id),
                "customer_phone": customer_phone or "",
            }
        },
        metadata={
            "padaria_id": str(padaria.id),
            "customer_phone": customer_phone or "",
            "customer_name": customer_name or "",
        }
    )
    
    # Salva no banco de dados
    payment_session = PaymentSession.objects.create(
        padaria=padaria,
        stripe_session_id=session.id,
        checkout_url=session.url,
        customer_phone=customer_phone or "",
        customer_name=customer_name or "",
        description=description,
        amount=amount,
        status="pending",
    )
    
    return {
        "session_id": session.id,
        "checkout_url": session.url,
        "payment_session_id": payment_session.id,
    }


def get_session_status(session_id):
    """
    Verifica o status de uma sessão de pagamento.
    """
    try:
        payment_session = PaymentSession.objects.get(stripe_session_id=session_id)
    except PaymentSession.DoesNotExist:
        return None
    
    # Busca status atualizado do Stripe
    session = stripe.checkout.Session.retrieve(session_id)
    
    # Mapeia status
    status_map = {
        "complete": "completed",
        "expired": "expired",
        "open": "pending",
    }
    
    new_status = status_map.get(session.status, "pending")
    
    if payment_session.status != new_status:
        payment_session.status = new_status
        if new_status == "completed":
            from django.utils import timezone
            payment_session.completed_at = timezone.now()
        payment_session.save()
    
    return {
        "session_id": session_id,
        "status": payment_session.status,
        "amount": float(payment_session.amount),
        "customer_phone": payment_session.customer_phone,
        "completed_at": payment_session.completed_at.isoformat() if payment_session.completed_at else None,
    }
