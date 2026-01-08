"""
Views para integração de pagamentos - Asaas + Mercado Pago.
Gerencia assinaturas do SaaS e configuração de MP por padaria.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
import os

from organizations.models import Padaria, PadariaUser
from .models import AsaasSubscription, AsaasPayment, MercadoPagoConfig, MercadoPagoPayment
from .services.asaas_service import asaas_service, AsaasAPIError
from .services.mercadopago_service import MercadoPagoService, MercadoPagoAPIError, get_mp_service


def get_user_padaria(user, padaria_slug=None):
    """
    Retorna a padaria do usuário logado.
    Superusers podem especificar uma padaria via slug.
    """
    if user.is_superuser:
        if padaria_slug:
            return Padaria.objects.filter(slug=padaria_slug).first()
        # Retorna a primeira padaria se não especificada
        return Padaria.objects.first()
    
    membership = PadariaUser.objects.filter(user=user, role='dono').first()
    if membership:
        return membership.padaria
    
    membership = PadariaUser.objects.filter(user=user).first()
    return membership.padaria if membership else None


def is_owner_or_superuser(user, padaria):
    """Verifica se o usuário é dono da padaria ou superuser."""
    if user.is_superuser:
        return True
    if not padaria:
        return False
    return PadariaUser.objects.filter(
        user=user, 
        padaria=padaria, 
        role='dono'
    ).exists()


# =============================================================================
# Views de Assinatura (SaaS -> Padaria)
# =============================================================================

@login_required
def subscription_status(request):
    """
    Página de status da assinatura da padaria.
    Mostra status atual, próximo vencimento, histórico de pagamentos.
    Superusers podem ver lista de todas as padarias.
    """
    padaria_slug = request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    # Se superuser sem padaria específica, mostrar lista
    if request.user.is_superuser and not padaria_slug:
        padarias = Padaria.objects.all().order_by('name')
        subscriptions_data = []
        for p in padarias:
            subscription = AsaasSubscription.objects.filter(padaria=p).first()
            subscriptions_data.append({
                'padaria': p,
                'subscription': subscription,
            })
        return render(request, 'payments/subscription_list.html', {
            'subscriptions_data': subscriptions_data,
            'total_padarias': padarias.count(),
        })
    
    if not padaria:
        messages.error(request, "Você precisa estar associado a uma padaria.")
        return redirect('ui:dashboard')
    
    # Buscar ou criar assinatura
    subscription, created = AsaasSubscription.objects.get_or_create(
        padaria=padaria,
        defaults={
            'plan_name': 'Plano Único',
            'plan_value': settings.ASAAS_SUBSCRIPTION_VALUE,
            'status': 'pending',
        }
    )
    
    # Histórico de pagamentos
    payments = AsaasPayment.objects.filter(
        subscription=subscription
    ).order_by('-due_date')[:10]
    
    # Verificar permissões
    can_edit = is_owner_or_superuser(request.user, padaria)
    can_cancel = PadariaUser.objects.filter(
        user=request.user, 
        padaria=padaria
    ).exists() or request.user.is_superuser
    
    context = {
        'padaria': padaria,
        'subscription': subscription,
        'payments': payments,
        'subscription_value': settings.ASAAS_SUBSCRIPTION_VALUE,
        'can_edit': can_edit,
        'can_cancel': can_cancel,
        'is_superuser': request.user.is_superuser,
    }
    
    return render(request, 'payments/subscription_status.html', context)


@login_required
def subscription_list(request):
    """
    Lista todas as assinaturas (apenas para superuser).
    """
    if not request.user.is_superuser:
        messages.error(request, "Acesso negado.")
        return redirect('payments:subscription_status')
    
    padarias = Padaria.objects.all().order_by('name')
    subscriptions_data = []
    
    for padaria in padarias:
        subscription = AsaasSubscription.objects.filter(padaria=padaria).first()
        subscriptions_data.append({
            'padaria': padaria,
            'subscription': subscription,
        })
    
    return render(request, 'payments/subscription_list.html', {
        'subscriptions_data': subscriptions_data,
    })


@login_required
def create_padaria_subscription(request):
    """
    Formulário para criar nova padaria com assinatura.
    Apenas para superusers.
    """
    if not request.user.is_superuser:
        messages.error(request, "Acesso negado.")
        return redirect('payments:subscription_status')
    
    if request.method == 'POST':
        # Dados da padaria
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        cnpj = request.POST.get('cnpj', '').strip()
        
        if not name:
            messages.error(request, "Nome da padaria é obrigatório.")
            return redirect('payments:create_padaria_subscription')
        
        try:
            # Criar padaria
            from django.utils.text import slugify
            
            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while Padaria.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            padaria = Padaria.objects.create(
                name=name,
                slug=slug,
                email=email,
                phone=phone,
                cnpj=cnpj,
                owner=request.user,
            )
            
            # Criar assinatura automaticamente
            subscription = AsaasSubscription.objects.create(
                padaria=padaria,
                plan_name='Plano Único',
                plan_value=settings.ASAAS_SUBSCRIPTION_VALUE,
                status='pending',
            )
            
            messages.success(request, f"Padaria '{name}' criada com sucesso!")
            return redirect(f"/payments/assinatura/?padaria={padaria.slug}")
            
        except Exception as e:
            messages.error(request, f"Erro ao criar padaria: {str(e)}")
            return redirect('payments:create_padaria_subscription')
    
    return render(request, 'payments/create_padaria_subscription.html')


@login_required
def create_subscription(request):
    """
    Cria assinatura no Asaas e redireciona para pagamento.
    Apenas donos ou superusers podem criar.
    """
    padaria_slug = request.POST.get('padaria_slug') or request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        messages.error(request, "Você precisa estar associado a uma padaria.")
        return redirect('ui:dashboard')
    
    if not is_owner_or_superuser(request.user, padaria):
        messages.error(request, "Você não tem permissão para criar assinatura.")
        return redirect('payments:subscription_status')
    
    try:
        # Buscar ou criar subscription local
        subscription, created = AsaasSubscription.objects.get_or_create(
            padaria=padaria,
            defaults={
                'plan_name': 'Plano Único',
                'plan_value': settings.ASAAS_SUBSCRIPTION_VALUE,
            }
        )
        
        # Verificar se já está ativa
        if subscription.status == 'active':
            messages.info(request, "A assinatura já está ativa!")
            return redirect('payments:subscription_status')
        
        # Se não tem customer_id, criar no Asaas
        if not subscription.asaas_customer_id:
            # Usar email da padaria ou do owner
            email = padaria.email or padaria.owner.email or f"{padaria.slug}@pandia.com.br"
            
            # Buscar ou criar cliente no Asaas
            customer = asaas_service.find_customer_by_email(email)
            
            if not customer:
                customer = asaas_service.create_customer(
                    name=padaria.name,
                    email=email,
                    cpf_cnpj=padaria.cnpj or None,
                    phone=padaria.phone or None,
                    external_reference=padaria.slug,
                )
            
            subscription.asaas_customer_id = customer.get('id')
            subscription.save()
        
        # Se não tem assinatura no Asaas, criar
        if not subscription.asaas_subscription_id:
            billing_type = request.POST.get('billing_type', 'PIX')
            
            asaas_sub = asaas_service.create_subscription(
                customer_id=subscription.asaas_customer_id,
                billing_type=billing_type,
                description=f"Assinatura Pandia - {padaria.name}",
            )
            
            subscription.asaas_subscription_id = asaas_sub.get('id')
            subscription.billing_type = billing_type
            subscription.next_due_date = asaas_sub.get('nextDueDate')
            subscription.status = 'pending'
            subscription.save()
            
            messages.success(request, "Assinatura criada com sucesso!")
        
        # Buscar pagamentos pendentes
        if subscription.asaas_subscription_id:
            payments_data = asaas_service.get_subscription_payments(
                subscription.asaas_subscription_id
            )
            
            for payment_data in payments_data.get('data', []):
                if payment_data.get('status') in ['PENDING', 'OVERDUE']:
                    payment_url = payment_data.get('invoiceUrl', '')
                    if payment_url:
                        subscription.current_payment_link = payment_url
                        subscription.save()
                        messages.info(request, "Link de pagamento disponível!")
                        break
        
    except AsaasAPIError as e:
        messages.error(request, f"Erro ao criar assinatura: {e.message}")
    except Exception as e:
        messages.error(request, f"Erro inesperado: {str(e)}")
    
    redirect_url = 'payments:subscription_status'
    if padaria_slug:
        return redirect(f"{redirect_url}?padaria={padaria.slug}")
    return redirect(redirect_url)


@login_required
@require_http_methods(["POST"])
def cancel_subscription(request):
    """
    Cancela assinatura e envia email para suporte.
    Qualquer membro da padaria pode solicitar cancelamento.
    """
    padaria_slug = request.POST.get('padaria_slug') or request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        messages.error(request, "Padaria não encontrada.")
        return redirect('payments:subscription_status')
    
    # Verificar se tem permissão (membro da padaria ou superuser)
    is_member = PadariaUser.objects.filter(
        user=request.user, 
        padaria=padaria
    ).exists()
    
    if not is_member and not request.user.is_superuser:
        messages.error(request, "Você não tem permissão para cancelar esta assinatura.")
        return redirect('payments:subscription_status')
    
    try:
        subscription = AsaasSubscription.objects.get(padaria=padaria)
        
        # Cancelar no Asaas se existir
        if subscription.asaas_subscription_id:
            try:
                asaas_service.cancel_subscription(subscription.asaas_subscription_id)
            except AsaasAPIError:
                pass  # Continua mesmo se falhar no Asaas
        
        # Atualizar status local
        subscription.status = 'cancelled'
        subscription.save()
        
        # Enviar email para suporte
        support_email = os.getenv('EMAIL_SUPPORT', 'suporte@pandia.com.br')
        cancel_reason = request.POST.get('reason', 'Não informado')
        
        try:
            send_mail(
                subject=f"[Cancelamento] Assinatura - {padaria.name}",
                message=f"""
Uma assinatura foi cancelada:

Padaria: {padaria.name}
Slug: {padaria.slug}
Email: {padaria.email or padaria.owner.email}
Telefone: {padaria.phone or 'N/A'}

Solicitante: {request.user.email}
Data: {timezone.now().strftime('%d/%m/%Y %H:%M')}

Motivo do cancelamento:
{cancel_reason}

---
Este é um email automático do sistema Pandia.
                """,
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@pandia.com.br',
                recipient_list=[support_email],
                fail_silently=True,
            )
        except Exception:
            pass  # Não bloqueia se email falhar
        
        messages.success(request, "Assinatura cancelada. A equipe de suporte foi notificada.")
        
    except AsaasSubscription.DoesNotExist:
        messages.error(request, "Assinatura não encontrada.")
    except Exception as e:
        messages.error(request, f"Erro ao cancelar: {str(e)}")
    
    return redirect('payments:subscription_status')


@login_required
def subscription_payment_link(request):
    """
    Gera/obtém link de pagamento para a assinatura pendente.
    """
    padaria_slug = request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        return JsonResponse({'error': 'Padaria não encontrada'}, status=400)
    
    try:
        subscription = AsaasSubscription.objects.get(padaria=padaria)
        
        if subscription.current_payment_link:
            return JsonResponse({
                'success': True,
                'payment_url': subscription.current_payment_link,
            })
        
        # Buscar pagamento pendente no Asaas
        if subscription.asaas_subscription_id:
            payments_data = asaas_service.get_subscription_payments(
                subscription.asaas_subscription_id
            )
            
            for payment_data in payments_data.get('data', []):
                if payment_data.get('status') in ['PENDING', 'OVERDUE']:
                    return JsonResponse({
                        'success': True,
                        'payment_url': payment_data.get('invoiceUrl', ''),
                    })
        
        return JsonResponse({
            'success': False,
            'message': 'Nenhum pagamento pendente encontrado',
        })
        
    except AsaasSubscription.DoesNotExist:
        return JsonResponse({'error': 'Assinatura não encontrada'}, status=404)
    except AsaasAPIError as e:
        return JsonResponse({'error': e.message}, status=500)


# =============================================================================
# Views de Mercado Pago (Padaria -> Cliente)
# =============================================================================

@login_required
def mercadopago_config(request):
    """
    Página de configuração do Mercado Pago para a padaria.
    Permite cadastrar credenciais e testar conexão.
    """
    padaria_slug = request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        messages.error(request, "Você precisa estar associado a uma padaria.")
        return redirect('ui:dashboard')
    
    # Buscar ou criar config
    mp_config, created = MercadoPagoConfig.objects.get_or_create(
        padaria=padaria
    )
    
    if request.method == 'POST':
        access_token = request.POST.get('access_token', '').strip()
        public_key = request.POST.get('public_key', '').strip()
        
        if access_token:
            mp_config.access_token = access_token
        if public_key:
            mp_config.public_key = public_key
        
        # Testar conexão
        if mp_config.access_token:
            try:
                mp_service = MercadoPagoService(mp_config.access_token)
                user_info = mp_service.test_credentials()
                
                mp_config.is_active = True
                mp_config.last_verified_at = timezone.now()
                mp_config.save()
                
                messages.success(
                    request, 
                    f"Mercado Pago configurado com sucesso! Conta: {user_info.get('nickname', 'N/A')}"
                )
            except MercadoPagoAPIError as e:
                mp_config.is_active = False
                mp_config.save()
                messages.error(request, f"Erro ao verificar credenciais: {e.message}")
        else:
            mp_config.save()
            messages.warning(request, "Credenciais salvas, mas não verificadas (falta Access Token)")
        
        return redirect('payments:mercadopago_config')
    
    # Histórico de pagamentos recentes
    recent_payments = MercadoPagoPayment.objects.filter(
        config=mp_config
    ).order_by('-created_at')[:10]
    
    context = {
        'padaria': padaria,
        'mp_config': mp_config,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'payments/mercadopago_config.html', context)


@login_required
def mercadopago_test_connection(request):
    """
    Testa conexão com Mercado Pago (AJAX).
    """
    padaria_slug = request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        return JsonResponse({'error': 'Padaria não encontrada'}, status=400)
    
    try:
        mp_config = padaria.mercadopago_config
        mp_service = MercadoPagoService(mp_config.access_token)
        user_info = mp_service.test_credentials()
        
        mp_config.is_active = True
        mp_config.last_verified_at = timezone.now()
        mp_config.save()
        
        return JsonResponse({
            'success': True,
            'user_id': user_info.get('id'),
            'nickname': user_info.get('nickname'),
            'email': user_info.get('email'),
        })
    except MercadoPagoConfig.DoesNotExist:
        return JsonResponse({'error': 'Mercado Pago não configurado'}, status=404)
    except MercadoPagoAPIError as e:
        return JsonResponse({'error': e.message}, status=400)


@login_required
@require_http_methods(["POST"])
def mercadopago_create_payment(request):
    """
    Cria um link de pagamento via Mercado Pago.
    """
    padaria_slug = request.POST.get('padaria_slug') or request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        return JsonResponse({'error': 'Padaria não encontrada'}, status=400)
    
    try:
        mp_config = padaria.mercadopago_config
        if not mp_config.is_active:
            return JsonResponse({'error': 'Mercado Pago não está ativo'}, status=400)
        
        # Dados do pagamento
        title = request.POST.get('title', 'Pagamento')
        amount = float(request.POST.get('amount', 0))
        description = request.POST.get('description', '')
        payer_email = request.POST.get('payer_email', '')
        
        if amount <= 0:
            return JsonResponse({'error': 'Valor inválido'}, status=400)
        
        # Criar preferência no MP
        mp_service = MercadoPagoService(mp_config.access_token)
        preference = mp_service.create_preference(
            title=title,
            amount=amount,
            description=description,
            payer_email=payer_email if payer_email else None,
        )
        
        # Salvar no banco
        mp_payment = MercadoPagoPayment.objects.create(
            config=mp_config,
            mp_preference_id=preference.get('id', ''),
            description=title,
            amount=amount,
            payer_email=payer_email,
            checkout_url=preference.get('init_point', ''),
            status='pending',
        )
        
        return JsonResponse({
            'success': True,
            'payment_id': mp_payment.id,
            'checkout_url': preference.get('init_point', ''),
            'sandbox_url': preference.get('sandbox_init_point', ''),
        })
        
    except MercadoPagoConfig.DoesNotExist:
        return JsonResponse({'error': 'Mercado Pago não configurado'}, status=404)
    except MercadoPagoAPIError as e:
        return JsonResponse({'error': e.message}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# Views Legadas (Stripe - mantidas para retrocompatibilidade)
# =============================================================================

@login_required
def payment_settings(request):
    """Página de configurações de pagamento (legado Stripe)."""
    return redirect('payments:subscription_status')


@login_required
def start_onboarding(request):
    """Inicia onboarding Stripe (legado)."""
    messages.info(request, "Integração Stripe não está ativa. Use Asaas para assinaturas.")
    return redirect('payments:subscription_status')


def onboarding_return(request, slug):
    """Callback Stripe (legado)."""
    return redirect('payments:subscription_status')


def onboarding_refresh(request, slug):
    """Refresh Stripe (legado)."""
    return redirect('payments:subscription_status')


@login_required
def stripe_dashboard(request):
    """Dashboard Stripe (legado)."""
    messages.info(request, "Integração Stripe não está ativa.")
    return redirect('payments:subscription_status')


def payment_success(request):
    """Página de sucesso."""
    return render(request, 'payments/success.html')


def payment_cancel(request):
    """Página de cancelamento."""
    return render(request, 'payments/cancel.html')
