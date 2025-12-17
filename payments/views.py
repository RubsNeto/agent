"""
Views para integração Stripe Connect.
Gerencia onboarding e callbacks.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

from organizations.models import Padaria, PadariaUser
from . import services
from .models import StripeAccount


def get_user_padaria(user):
    """Retorna a padaria do usuário logado (se for dono)."""
    if user.is_superuser:
        return None
    
    membership = PadariaUser.objects.filter(user=user, role='dono').first()
    if membership:
        return membership.padaria
    
    # Fallback: primeira padaria onde é membro
    membership = PadariaUser.objects.filter(user=user).first()
    return membership.padaria if membership else None


@login_required
def payment_settings(request):
    """
    Página de configurações de pagamento.
    Exibe status da integração Stripe e permite iniciar onboarding.
    """
    padaria = get_user_padaria(request.user)
    
    if not padaria:
        messages.error(request, "Você precisa estar associado a uma padaria.")
        return redirect('ui:dashboard')
    
    # Verifica se tem conta Stripe
    stripe_account = getattr(padaria, 'stripe_account', None)
    account_status = None
    
    if stripe_account:
        try:
            account_status = services.get_account_status(padaria)
        except Exception as e:
            messages.warning(request, f"Erro ao verificar status da conta Stripe: {e}")
    
    context = {
        'padaria': padaria,
        'stripe_account': stripe_account,
        'account_status': account_status,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
    
    return render(request, 'payments/settings.html', context)


@login_required
def start_onboarding(request):
    """
    Inicia o processo de onboarding Stripe Connect.
    Redireciona para o formulário hospedado do Stripe.
    """
    padaria = get_user_padaria(request.user)
    
    if not padaria:
        messages.error(request, "Você precisa estar associado a uma padaria.")
        return redirect('ui:dashboard')
    
    try:
        onboarding_url = services.get_onboarding_link(padaria, request)
        return redirect(onboarding_url)
    except Exception as e:
        messages.error(request, f"Erro ao iniciar onboarding: {e}")
        return redirect('payments:settings')


def onboarding_return(request, slug):
    """
    Callback após o usuário completar/sair do onboarding.
    Verifica o status e redireciona para configurações.
    """
    padaria = get_object_or_404(Padaria, slug=slug)
    
    try:
        account_status = services.get_account_status(padaria)
        
        if account_status and account_status.get('is_fully_enabled'):
            messages.success(request, "Conta Stripe configurada com sucesso! Você já pode receber pagamentos.")
        elif account_status and account_status.get('details_submitted'):
            messages.info(request, "Seus dados foram enviados. O Stripe está verificando sua conta.")
        else:
            messages.warning(request, "Onboarding incompleto. Complete todos os passos para ativar pagamentos.")
    except Exception as e:
        messages.error(request, f"Erro ao verificar status: {e}")
    
    return redirect('payments:settings')


def onboarding_refresh(request, slug):
    """
    Regenera o link de onboarding quando expirado.
    """
    padaria = get_object_or_404(Padaria, slug=slug)
    
    try:
        onboarding_url = services.get_onboarding_link(padaria, request)
        return redirect(onboarding_url)
    except Exception as e:
        messages.error(request, f"Erro ao gerar link de onboarding: {e}")
        return redirect('payments:settings')


@login_required
def stripe_dashboard(request):
    """
    Redireciona para o dashboard Express do Stripe.
    """
    padaria = get_user_padaria(request.user)
    
    if not padaria:
        messages.error(request, "Você precisa estar associado a uma padaria.")
        return redirect('ui:dashboard')
    
    try:
        dashboard_url = services.get_dashboard_link(padaria)
        
        if dashboard_url:
            return redirect(dashboard_url)
        else:
            messages.warning(request, "Complete o onboarding antes de acessar o dashboard.")
            return redirect('payments:settings')
    except Exception as e:
        messages.error(request, f"Erro ao acessar dashboard: {e}")
        return redirect('payments:settings')


def payment_success(request):
    """Página de sucesso após pagamento."""
    session_id = request.GET.get('session_id')
    
    session_info = None
    if session_id:
        try:
            session_info = services.get_session_status(session_id)
        except Exception:
            pass
    
    return render(request, 'payments/success.html', {
        'session_id': session_id,
        'session_info': session_info,
    })


def payment_cancel(request):
    """Página de cancelamento de pagamento."""
    return render(request, 'payments/cancel.html')
