"""
Views para integração de pagamentos - Cakto + Mercado Pago.
Gerencia assinaturas do SaaS (Cakto) e configuração de MP por padaria.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
import os
import logging

logger = logging.getLogger(__name__)

from organizations.models import Padaria, PadariaUser
from .models import (
    AsaasSubscription, AsaasPayment,  # Legado - mantido para compatibilidade
    MercadoPagoConfig, MercadoPagoPayment,
    CaktoSubscription, CaktoPayment,  # Novo sistema
)
from .services.asaas_service import asaas_service, AsaasAPIError
from .services.mercadopago_service import MercadoPagoService, MercadoPagoAPIError, get_mp_service
from .services.cakto_service import cakto_service


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
    Usa CaktoSubscription como fonte primária (novo sistema).
    """
    padaria_slug = request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    # Se superuser sem padaria específica, mostrar lista
    if request.user.is_superuser and not padaria_slug:
        padarias = Padaria.objects.all().order_by('name')
        subscriptions_data = []
        for p in padarias:
            # Tentar buscar Cakto primeiro, depois Asaas (legado)
            cakto_sub = CaktoSubscription.objects.filter(padaria=p).first()
            asaas_sub = AsaasSubscription.objects.filter(padaria=p).first() if not cakto_sub else None
            subscriptions_data.append({
                'padaria': p,
                'subscription': cakto_sub or asaas_sub,
                'is_cakto': cakto_sub is not None,
            })
        return render(request, 'payments/subscription_list.html', {
            'subscriptions_data': subscriptions_data,
            'total_padarias': padarias.count(),
        })
    
    if not padaria:
        messages.error(request, "Você precisa estar associado a uma padaria.")
        return redirect('ui:dashboard')
    
    # Buscar assinatura Cakto (novo sistema)
    cakto_subscription = CaktoSubscription.objects.filter(padaria=padaria).first()
    
    # Se não tem Cakto, verificar Asaas legado
    asaas_subscription = None
    if not cakto_subscription:
        asaas_subscription = AsaasSubscription.objects.filter(padaria=padaria).first()
    
    # Se não tem nenhuma, criar Cakto nova
    if not cakto_subscription and not asaas_subscription:
        cakto_subscription = CaktoSubscription.objects.create(
            padaria=padaria,
            plan_name=settings.CAKTO_PLAN_NAME,
            plan_value=settings.CAKTO_PLAN_VALUE,
            trial_days=settings.CAKTO_DEFAULT_TRIAL_DAYS,
        )
        cakto_subscription.start_trial(settings.CAKTO_DEFAULT_TRIAL_DAYS)
    
    # Usar Cakto como fonte primária
    subscription = cakto_subscription
    is_cakto = True
    
    if not cakto_subscription and asaas_subscription:
        # Fallback para Asaas legado (padarias antigas)
        subscription = asaas_subscription
        is_cakto = False
    
    # Histórico de pagamentos
    if is_cakto and subscription:
        payments = CaktoPayment.objects.filter(
            subscription=subscription
        ).order_by('-created_at')[:10]
    elif not is_cakto and subscription:
        payments = AsaasPayment.objects.filter(
            subscription=subscription
        ).order_by('-due_date')[:10]
    else:
        payments = []
    
    # Calcular dias restantes
    days_remaining = 0
    if subscription and hasattr(subscription, 'days_remaining'):
        days_remaining = subscription.days_remaining()
    
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
        'subscription_value': settings.CAKTO_PLAN_VALUE if is_cakto else getattr(settings, 'ASAAS_SUBSCRIPTION_VALUE', 140),
        'can_edit': can_edit,
        'can_cancel': can_cancel,
        'is_superuser': request.user.is_superuser,
        'is_cakto': is_cakto,
        'days_remaining': days_remaining,
    }
    
    return render(request, 'payments/subscription_status.html', context)


def sync_subscription_status(subscription):
    """
    Sincroniza o status da assinatura com o Asaas.
    Verifica se há pagamentos confirmados e atualiza o status local.
    Também sincroniza os pagamentos no banco de dados.
    """
    if not subscription.asaas_subscription_id:
        return
    
    try:
        # Buscar pagamentos da assinatura no Asaas
        payments_data = asaas_service.get_subscription_payments(
            subscription.asaas_subscription_id
        )
        
        for payment_data in payments_data.get('data', []):
            payment_id = payment_data.get('id')
            payment_status = payment_data.get('status', '')
            
            # Sincronizar/criar pagamento no banco local
            AsaasPayment.objects.update_or_create(
                asaas_payment_id=payment_id,
                defaults={
                    "subscription": subscription,
                    "value": payment_data.get("value", 0),
                    "due_date": payment_data.get("dueDate"),
                    "payment_date": payment_data.get("paymentDate") if payment_status in ['RECEIVED', 'CONFIRMED'] else None,
                    "billing_type": payment_data.get("billingType", "PIX"),
                    "invoice_url": payment_data.get("invoiceUrl", ""),
                    "status": {
                        'PENDING': 'pending',
                        'RECEIVED': 'received',
                        'CONFIRMED': 'confirmed',
                        'OVERDUE': 'overdue',
                        'REFUNDED': 'refunded',
                        'RECEIVED_IN_CASH': 'received',
                    }.get(payment_status, 'pending'),
                }
            )
            
            # Se há um pagamento confirmado/recebido, ativar assinatura
            if payment_status in ['RECEIVED', 'CONFIRMED', 'RECEIVED_IN_CASH']:
                subscription.status = 'active'
                subscription.last_payment_date = timezone.now().date()
                
                # Atualizar próximo vencimento (30 dias a partir da data do último pagamento)
                subscription.next_due_date = subscription.last_payment_date + timezone.timedelta(days=30)
                
                # Limpar link de pagamento pendente
                subscription.current_payment_link = ''
                subscription.current_payment_id = ''
                subscription.save()
                
                print(f"DEBUG: Assinatura {subscription.id} ativada via sincronização")
                return  # Encontrou pagamento confirmado, pode parar
            
            # Se há pagamento vencido
            elif payment_status == 'OVERDUE':
                if subscription.status != 'active':
                    subscription.status = 'overdue'
                    subscription.save()
                    print(f"DEBUG: Assinatura {subscription.id} marcada como inadimplente")
                    
    except Exception as e:
        print(f"DEBUG: Erro ao sincronizar com Asaas: {e}")


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
        
        # Se a assinatura estava cancelada, limpar dados antigos para reativar
        if subscription.status == 'cancelled':
            print(f"DEBUG: Reativando assinatura cancelada para {padaria.name}")
            # Limpar IDs do Asaas antigos para criar nova assinatura
            subscription.asaas_subscription_id = ''
            subscription.current_payment_link = ''
            subscription.current_payment_id = ''
            subscription.status = 'pending'
            subscription.plan_value = settings.ASAAS_SUBSCRIPTION_VALUE
            subscription.save()
            messages.info(request, "Reativando sua assinatura...")
        
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
            
            # Garantir que o valor não seja zero (pode ter sido criado vazio antes)
            if not subscription.plan_value or subscription.plan_value <= 0:
                print(f"DEBUG: Valor incorreto ({subscription.plan_value}), atualizando para settings ({settings.ASAAS_SUBSCRIPTION_VALUE})")
                subscription.plan_value = settings.ASAAS_SUBSCRIPTION_VALUE
                subscription.save()

            # Se o valor for 0 ou menor, é plano gratuito
            if subscription.plan_value <= 0:
                print("DEBUG: Plano Gratuito detectado. Ativando sem Asaas.")
                subscription.status = 'active'
                subscription.save()
                messages.success(request, "Plano gratuito ativado com sucesso!")
                return redirect('payments:subscription_status')


            print(f"DEBUG: Criando assinatura Asaas com value={subscription.plan_value}")

            # Construir URL de callback para redirecionar após pagamento
            # Só envia callback se não estiver em localhost (evita erro de domínio no sandbox)
            callback_url = None
            host = request.get_host()
            if 'localhost' not in host and '127.0.0.1' not in host:
                callback_url = request.build_absolute_uri(
                    f"/payments/success/?padaria={padaria.slug}"
                )
            
            asaas_sub = asaas_service.create_subscription(
                customer_id=subscription.asaas_customer_id,
                billing_type=billing_type,
                value=float(subscription.plan_value),
                description=f"Assinatura Pandia - {padaria.name}",
                external_reference=padaria.slug,
                callback_url=callback_url,
            )
            
            subscription.asaas_subscription_id = asaas_sub.get('id')
            subscription.billing_type = billing_type
            subscription.next_due_date = asaas_sub.get('nextDueDate')
            subscription.status = 'pending'
            
            # Tenta pegar o link do pagamento inicial se tiver cobranca imediata
            payments_data = asaas_service.get_subscription_payments(subscription.asaas_subscription_id)
            for payment_data in payments_data.get('data', []):
                if payment_data.get('status') in ['PENDING', 'OVERDUE']:
                    invoice_url = payment_data.get('invoiceUrl')
                    if invoice_url:
                        # Adicionar parâmetro para forçar o tipo de pagamento na URL
                        # O Asaas aceita #paymentType= no final da URL
                        payment_type_map = {
                            'PIX': 'PIX',
                            'CREDIT_CARD': 'CREDIT_CARD',
                            'BOLETO': 'BOLETO',
                        }
                        payment_type_param = payment_type_map.get(billing_type, 'PIX')
                        
                        # Remover hash existente se houver e adicionar o novo
                        if '#' in invoice_url:
                            invoice_url = invoice_url.split('#')[0]
                        
                        # Adicionar o parâmetro de tipo de pagamento
                        invoice_url_with_type = f"{invoice_url}#paymentType={payment_type_param}"
                        
                        subscription.current_payment_link = invoice_url_with_type
                        subscription.save()
                        print(f"DEBUG: Redirecionando para checkout Asaas ({billing_type}): {invoice_url_with_type}")
                        return redirect(invoice_url_with_type)
            
            # Se não encontrou link de pagamento pendente, apenas salva
            # (link pode vir depois via webhook)
            subscription.save()
            messages.success(request, "Assinatura criada com sucesso! Aguardando pagamento.")
        
    except AsaasAPIError as e:
        messages.error(request, f"Erro ao criar assinatura: {e.message}")
    except Exception as e:
        messages.error(request, f"Erro inesperado: {str(e)}")
    
    if padaria_slug:
        base_url = reverse('payments:subscription_status')
        return redirect(f"{base_url}?padaria={padaria.slug}")
    return redirect('payments:subscription_status')


@login_required
@require_http_methods(["POST"])
def cancel_subscription(request):
    """
    Cancela assinatura Cakto e envia email para suporte.
    Qualquer membro da padaria pode solicitar cancelamento.
    """
    print(f"DEBUG: cancel_subscription chamada")
    print(f"DEBUG: POST data: {request.POST}")
    
    padaria_slug = request.POST.get('padaria_slug') or request.GET.get('padaria')
    print(f"DEBUG: padaria_slug = {padaria_slug}")
    
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
        # Tentar primeiro CaktoSubscription (sistema novo)
        subscription = CaktoSubscription.objects.get(padaria=padaria)
        
        # Cancelar na Cakto se existir ID da assinatura
        if subscription.cakto_subscription_id:
            try:
                result = cakto_service.cancel_subscription(subscription.cakto_subscription_id)
                if not result.get("success"):
                    logger.warning(f"Falha ao cancelar na Cakto: {result.get('error')}")
            except Exception as e:
                logger.error(f"Erro ao cancelar na Cakto: {str(e)}")
        
        # Atualizar status local
        subscription.status = 'cancelled'
        subscription.save()
        
        # Desativar padaria
        padaria.is_active = False
        padaria.save()
        
        # Enviar email para suporte
        support_email = os.getenv('EMAIL_SUPPORT', 'suporte@pandia.com.br')
        cancel_reason = request.POST.get('reason', 'Não informado')
        
        try:
            send_mail(
                subject=f"[Cancelamento] Assinatura Cakto - {padaria.name}",
                message=f"""
Uma assinatura foi cancelada:

Padaria: {padaria.name}
Slug: {padaria.slug}
Email: {padaria.responsavel_email or padaria.email or padaria.owner.email}
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
        
    except CaktoSubscription.DoesNotExist:
        # Fallback para AsaasSubscription (sistema legado)
        try:
            subscription = AsaasSubscription.objects.get(padaria=padaria)
            
            if subscription.asaas_subscription_id:
                try:
                    asaas_service.cancel_subscription(subscription.asaas_subscription_id)
                except AsaasAPIError:
                    pass
            
            subscription.status = 'cancelled'
            subscription.save()
            messages.success(request, "Assinatura cancelada.")
            
        except AsaasSubscription.DoesNotExist:
            messages.error(request, "Assinatura não encontrada.")
            
    except Exception as e:
        messages.error(request, f"Erro ao cancelar: {str(e)}")
    
    # Redirecionar com o slug da padaria
    if padaria_slug:
        return redirect(f"/payments/assinatura/?padaria={padaria_slug}")
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
                    payment_url = payment_data.get('invoiceUrl', '')
                    
                    # Adicionar parâmetro de tipo de pagamento
                    if payment_url and subscription.billing_type:
                        if '#' in payment_url:
                            payment_url = payment_url.split('#')[0]
                        payment_url = f"{payment_url}#paymentType={subscription.billing_type}"
                    
                    return JsonResponse({
                        'success': True,
                        'payment_url': payment_url,
                    })
        
        return JsonResponse({
            'success': False,
            'message': 'Nenhum pagamento pendente encontrado',
        })
        
    except AsaasSubscription.DoesNotExist:
        return JsonResponse({'error': 'Assinatura não encontrada'}, status=404)
    except AsaasAPIError as e:
        return JsonResponse({'error': e.message}, status=500)


@login_required
@require_http_methods(["POST"])
def cakto_register_card(request):
    """
    Cadastra cartão para débito automático via Cakto.
    Cria oferta de assinatura e redireciona para checkout.
    """
    padaria_slug = request.POST.get('padaria_slug') or request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        messages.error(request, "Você precisa estar associado a uma padaria.")
        return redirect('ui:dashboard')
    
    if not is_owner_or_superuser(request.user, padaria):
        messages.error(request, "Você não tem permissão para gerenciar assinatura.")
        return redirect('payments:subscription_status')
    
    try:
        # Buscar assinatura Cakto
        subscription = CaktoSubscription.objects.get(padaria=padaria)
        
        # Se já tem cartão cadastrado E assinatura está ativa, não precisa cadastrar novamente
        # Mas se está inativa, permite ir para o checkout para regularizar
        if subscription.card_registered and subscription.status == 'active':
            messages.info(request, "Cartão já cadastrado!")
            return redirect('payments:subscription_status')
        
        # Gerar nova URL de checkout (sem cache para permitir novo pagamento)
        # Criar oferta na Cakto
        email = padaria.responsavel_email or padaria.email or padaria.owner.email
        name = padaria.responsavel_nome or padaria.name
        
        # Construir URL de retorno após pagamento
        return_url = request.build_absolute_uri(
            reverse('payments:cakto_return') + f"?padaria={padaria.slug}"
        )
        
        result = cakto_service.create_subscription_offer(
            padaria=padaria,
            customer_email=email,
            customer_name=name,
            return_url=return_url
        )
        
        if result.get("success"):
            # Salvar IDs e URL
            subscription.cakto_offer_id = result.get("offer_id", "")
            subscription.checkout_url = result.get("checkout_url", "")
            subscription.save()
            
            # Redirecionar para checkout
            checkout_url = subscription.checkout_url
            if checkout_url:
                return redirect(checkout_url)
            else:
                messages.error(request, "URL de checkout não foi gerada. Tente novamente.")
        else:
            error_msg = result.get("error", "Erro desconhecido")
            messages.error(request, f"Erro ao criar oferta: {error_msg}")
            
    except CaktoSubscription.DoesNotExist:
        messages.error(request, "Assinatura não encontrada. Entre em contato com o suporte.")
    except Exception as e:
        messages.error(request, f"Erro inesperado: {str(e)}")
    
    if padaria_slug:
        return redirect(f"/payments/assinatura/?padaria={padaria_slug}")
    return redirect('payments:subscription_status')


@login_required
def sync_cakto_status(request):
    """
    Força sincronização do status da assinatura Cakto consultando a API.
    """
    padaria_slug = request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        messages.error(request, "Padaria não encontrada.")
        return redirect('payments:subscription_status')
    
    try:
        subscription = CaktoSubscription.objects.get(padaria=padaria)
        
        # Tentar consultar status pelo ID do pedido
        if subscription.cakto_order_id:
            try:
                result = cakto_service.get_order_status(subscription.cakto_order_id)
                
                if result.get("success"):
                    status = result.get("status")
                    # Se aprovado na API mas não local, ativar
                    if status == "approved" and subscription.status != 'active':
                        subscription.activate()
                        messages.success(request, "Status sincronizado: Assinatura Ativa!")
                    else:
                        messages.info(request, f"Status verificado na Cakto: {status}")
                else:
                    messages.error(request, f"Não foi possível consultar o status: {result.get('error')}")
            except Exception as e:
                logger.error(f"Erro ao consultar Cakto: {e}")
                messages.error(request, "Erro ao conectar com a Cakto.")
        else:
            messages.warning(request, "Não foi possível localizar o pedido automaticamente. Se pagou agora, aguarde alguns instantes ou use 'Simular Pagamento' em ambiente de teste.")
            
    except CaktoSubscription.DoesNotExist:
        messages.error(request, "Assinatura Cakto não encontrada.")
    except Exception as e:
        messages.error(request, f"Erro ao sincronizar: {str(e)}")
        
    url = reverse('payments:subscription_status')
    if padaria_slug:
        url += f"?padaria={padaria_slug}"
    return redirect(url)



@login_required
@require_http_methods(["POST"])
def subscription_test_action(request):
    """
    Ações de teste para simular cenários de assinatura.
    Temporário: disponível para todos os usuários para testes.
    """
    # Temporariamente removido para testes
    # if not request.user.is_superuser:
    #     messages.error(request, "Acesso negado.")
    #     return redirect('payments:subscription_status')
    
    padaria_slug = request.POST.get('padaria_slug')
    action = request.POST.get('action')
    
    padaria = get_user_padaria(request.user, padaria_slug)
    if not padaria:
        messages.error(request, "Padaria não encontrada.")
        return redirect('payments:subscription_status')
    
    try:
        subscription = CaktoSubscription.objects.get(padaria=padaria)
        today = timezone.now().date()
        
        if action == 'update_plan_value':
            from decimal import Decimal
            subscription.plan_value = Decimal("140.00")
            subscription.save()
            messages.success(request, "Valor do plano atualizado para R$ 140,00.")
            
        elif action == 'trial_3_days':
            # Simular trial expirando em 3 dias
            subscription.status = 'trial'
            subscription.trial_end_date = today + timezone.timedelta(days=3)
            subscription.save()
            padaria.is_active = True
            padaria.save()
            messages.success(request, f"Trial configurado para expirar em 3 dias ({subscription.trial_end_date}).")
            
        elif action == 'trial_expired':
            # Simular trial expirado (ontem)
            subscription.status = 'inactive'
            subscription.trial_end_date = today - timezone.timedelta(days=1)
            subscription.save()
            padaria.is_active = False
            padaria.save()
            messages.warning(request, "Trial expirado! Padaria desativada.")
            
        elif action == 'payment_approved':
            # Simular pagamento aprovado
            subscription.status = 'active'
            subscription.card_registered = True
            subscription.card_last_4 = '4242'
            subscription.card_brand = 'Visa'
            subscription.last_payment_date = today
            subscription.next_billing_date = today + timezone.timedelta(days=30)
            subscription.save()
            padaria.is_active = True
            padaria.save()
            
            # Criar pagamento de teste
            CaktoPayment.objects.create(
                subscription=subscription,
                cakto_order_id=f"test_{timezone.now().timestamp()}",
                amount=subscription.plan_value,
                status='approved',
                paid_at=timezone.now(),
                billing_period_start=today,
                billing_period_end=today + timezone.timedelta(days=30),
            )
            messages.success(request, "Pagamento simulado! Assinatura ativada.")
            
        elif action == 'reset_trial':
            # Resetar para trial novo de 15 dias
            subscription.status = 'trial'
            subscription.trial_days = settings.CAKTO_DEFAULT_TRIAL_DAYS
            subscription.trial_end_date = today + timezone.timedelta(days=settings.CAKTO_DEFAULT_TRIAL_DAYS)
            subscription.card_registered = False
            subscription.card_last_4 = ''
            subscription.card_brand = ''
            subscription.next_billing_date = None
            subscription.last_payment_date = None
            subscription.save()
            padaria.is_active = True
            padaria.save()
            messages.success(request, f"Trial resetado para {settings.CAKTO_DEFAULT_TRIAL_DAYS} dias.")
            
        else:
            messages.error(request, f"Ação desconhecida: {action}")
            
    except CaktoSubscription.DoesNotExist:
        messages.error(request, "Assinatura Cakto não encontrada.")
    except Exception as e:
        messages.error(request, f"Erro: {str(e)}")
    
    if padaria_slug:
        return redirect(f"/payments/assinatura/?padaria={padaria_slug}")
    return redirect('payments:subscription_status')


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
def mercadopago_payment_status(request, payment_id):
    """
    Retorna o status atual de um pagamento Mercado Pago.
    Usado pelo frontend para polling e atualização automática.
    
    Se o pagamento ainda estiver 'pending', consulta a API do MP diretamente
    para verificar se foi pago (bypass para quando webhook não funciona em localhost).
    """
    padaria_slug = request.GET.get('padaria')
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        return JsonResponse({'error': 'Padaria não encontrada'}, status=400)
    
    try:
        mp_config = padaria.mercadopago_config
        payment = MercadoPagoPayment.objects.get(
            id=payment_id,
            config=mp_config
        )
        
        # Se ainda está pendente, verificar diretamente na API do MP
        # APENAS para pagamentos que têm external_reference (criados após a correção)
        if payment.status == 'pending':
            try:
                # Usar external_reference se disponível (armazenado em pix_qr_code)
                external_ref = payment.pix_qr_code if payment.pix_qr_code and payment.pix_qr_code.startswith('pandia_') else None
                
                # Só consultar API se tiver external_reference (para evitar falsos positivos)
                if external_ref:
                    mp_service = MercadoPagoService(mp_config.access_token)
                    
                    print(f"DEBUG: Buscando por external_reference: {external_ref}")
                    search_result = mp_service.search_payments(
                        external_reference=external_ref,
                        limit=5
                    )
                    
                    # Verificar se encontrou o pagamento específico
                    for mp_payment_data in search_result.get('results', []):
                        mp_status = mp_payment_data.get('status', '')
                        mp_external_ref = mp_payment_data.get('external_reference', '')
                        
                        # Match APENAS por external_reference (é único)
                        if mp_external_ref == external_ref:
                            print(f"DEBUG: Match por external_reference! Status: {mp_status}")
                            
                            if mp_status in ['approved', 'authorized']:
                                # Pagamento aprovado! Atualizar banco
                                payment.status = 'approved'
                                payment.mp_payment_id = str(mp_payment_data.get('id', ''))
                                payment.paid_at = timezone.now()
                                payment.save()
                                
                                print(f"DEBUG: Pagamento {payment.id} atualizado para approved via polling direto")
                                break
                            elif mp_status in ['rejected', 'cancelled', 'refunded']:
                                payment.status = mp_status
                                payment.mp_payment_id = str(mp_payment_data.get('id', ''))
                                payment.save()
                                print(f"DEBUG: Pagamento {payment.id} atualizado para {mp_status}")
                                break
                else:
                    # Pagamento antigo sem external_reference - não atualizar automaticamente
                    print(f"DEBUG: Pagamento {payment.id} sem external_reference, ignorando polling")
                            
            except Exception as e:
                print(f"DEBUG: Erro ao consultar MP API: {e}")
                import traceback
                traceback.print_exc()
                # Continua e retorna o status atual do banco
        
        return JsonResponse({
            'success': True,
            'payment_id': payment.id,
            'status': payment.status,
            'status_display': payment.get_status_display(),
            'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
        })
        
    except MercadoPagoConfig.DoesNotExist:
        return JsonResponse({'error': 'Mercado Pago não configurado'}, status=404)
    except MercadoPagoPayment.DoesNotExist:
        return JsonResponse({'error': 'Pagamento não encontrado'}, status=404)


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
        
        # Construir notification_url para receber webhook
        notification_url = None
        host = request.get_host()
        if 'localhost' not in host and '127.0.0.1' not in host:
            notification_url = request.build_absolute_uri('/webhooks/mercadopago/')
        
        # Gerar external_reference único para identificar o pagamento
        import uuid
        external_reference = f"pandia_{padaria.slug}_{uuid.uuid4().hex[:8]}"
        
        # Criar preferência no MP
        mp_service = MercadoPagoService(mp_config.access_token)
        preference = mp_service.create_preference(
            title=title,
            amount=amount,
            description=description,
            payer_email=payer_email if payer_email else None,
            notification_url=notification_url,
            external_reference=external_reference,
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
        
        # Armazenar external_reference no pix_qr_code (campo livre) para poder buscar depois
        mp_payment.pix_qr_code = external_reference
        mp_payment.save()
        
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
    """Página de sucesso após pagamento confirmado."""
    # Tentar buscar a assinatura do usuário
    padaria = None
    subscription = None
    is_cakto = False
    
    if request.user.is_authenticated:
        padaria_slug = request.GET.get('padaria')
        padaria = get_user_padaria(request.user, padaria_slug)
        
        if padaria:
            # Tentar Cakto primeiro
            try:
                subscription = CaktoSubscription.objects.get(padaria=padaria)
                is_cakto = True
                
                # Se ainda estiver em trial/inactive e tivermos order_id, consultar API
                if subscription.status not in ['active'] and subscription.cakto_order_id:
                    try:
                        result = cakto_service.get_order_status(subscription.cakto_order_id)
                        if result.get("success") and result.get("status") == "approved":
                            subscription.activate()
                            messages.success(request, "Pagamento confirmado! Sua assinatura está ativa.")
                    except Exception:
                        pass
                
            except CaktoSubscription.DoesNotExist:
                subscription = AsaasSubscription.objects.filter(padaria=padaria).first()
    
    # Se temos assinatura, mostrar página detalhada
    if padaria and subscription:
        return render(request, 'payments/subscription_success.html', {
            'padaria': padaria,
            'subscription': subscription,
            'is_cakto': is_cakto,
        })
    
    # Fallback para página genérica
    return render(request, 'payments/success.html')


def payment_cancel(request):
    """Página de cancelamento/erro no pagamento."""
    messages.warning(request, "O pagamento não foi concluído. Você pode tentar novamente.")
    
    if request.user.is_authenticated:
        padaria_slug = request.GET.get('padaria')
        padaria = get_user_padaria(request.user, padaria_slug)
        
        if padaria:
            return redirect(f"/payments/assinatura/?padaria={padaria.slug}")
    
    return render(request, 'payments/cancel.html')


# =============================================================================
# Views de Retorno Cakto (Checkout callback)
# =============================================================================

def cakto_return(request):
    """
    Página de retorno após checkout da Cakto.
    Faz polling automático para verificar se o pagamento foi confirmado.
    
    Esta página é usada quando o usuário clica em "Voltar ao site" após pagar.
    Como a Cakto não tem parâmetro de redirect automático, o usuário deve
    clicar manualmente no botão de voltar após o pagamento.
    
    Parâmetros opcionais via query string:
    - padaria: slug da padaria (para identificar assinatura)
    - order_id: ID do pedido na Cakto (se disponível)
    """
    padaria_slug = request.GET.get('padaria')
    order_id = request.GET.get('order_id')
    
    # Se usuário não está logado ou não temos padaria, redirecionar para login
    if not request.user.is_authenticated:
        if padaria_slug:
            return redirect(f'/accounts/login/?next=/payments/cakto/return/?padaria={padaria_slug}')
        return redirect('accounts:login')
    
    # Obter padaria
    padaria = get_user_padaria(request.user, padaria_slug)
    
    if not padaria:
        messages.error(request, "Você precisa estar associado a uma padaria.")
        return redirect('ui:dashboard')
    
    # Buscar assinatura Cakto
    try:
        subscription = CaktoSubscription.objects.get(padaria=padaria)
        
        # Se temos order_id, salvar na subscription
        if order_id and not subscription.cakto_order_id:
            subscription.cakto_order_id = order_id
            subscription.save(update_fields=['cakto_order_id', 'updated_at'])
        
        # Tentar sincronizar status imediatamente
        if subscription.cakto_order_id and subscription.status not in ['active']:
            try:
                result = cakto_service.get_order_status(subscription.cakto_order_id)
                if result.get("success"):
                    status = result.get("status", "")
                    if status in ["approved", "paid"]:
                        subscription.activate()
                        logger.info(f"Assinatura {padaria_slug} ativada via cakto_return")
            except Exception as e:
                logger.warning(f"Erro ao consultar Cakto na página de retorno: {e}")
        
    except CaktoSubscription.DoesNotExist:
        # Criar assinatura se não existir
        subscription = CaktoSubscription.objects.create(
            padaria=padaria,
            plan_name=settings.CAKTO_PLAN_NAME,
            plan_value=settings.CAKTO_PLAN_VALUE,
            cakto_order_id=order_id or "",
        )
    
    return render(request, 'payments/cakto_return.html', {
        'padaria': padaria,
        'subscription': subscription,
    })


# =============================================================================
# Views de Retorno do Mercado Pago
# =============================================================================

def mp_payment_return(request):
    """
    Página de retorno após pagamento no Mercado Pago.
    Recebe parâmetros do MP e atualiza o status do pagamento.
    
    Query params do MP:
        - collection_id: ID do pagamento no MP
        - collection_status: approved, pending, rejected
        - external_reference: nossa referência
        - payment_id: nosso ID interno (passado na back_url)
        - status: status passado por nós na back_url
    """
    # Parâmetros que nós passamos
    payment_id = request.GET.get('payment_id')
    our_status = request.GET.get('status', '')
    external_reference = request.GET.get('external_reference', '')
    
    # Parâmetros que o MP adiciona
    collection_id = request.GET.get('collection_id')
    collection_status = request.GET.get('collection_status', '')
    payment_status = request.GET.get('payment_status', '')
    
    # Status final (prioriza o que o MP retorna)
    final_status = collection_status or payment_status or our_status
    
    payment = None
    
    if payment_id:
        try:
            payment = MercadoPagoPayment.objects.select_related('config', 'config__padaria').get(id=payment_id)
            
            # Atualizar com os dados do MP
            if collection_id and not payment.mp_payment_id:
                payment.mp_payment_id = str(collection_id)
            
            # Atualizar status se mudou
            old_status = payment.status
            if final_status and final_status != old_status:
                # Mapear status do MP para nosso
                status_map = {
                    'approved': 'approved',
                    'pending': 'pending',
                    'in_process': 'in_process',
                    'rejected': 'rejected',
                    'cancelled': 'cancelled',
                    'refunded': 'refunded',
                }
                new_status = status_map.get(final_status, final_status)
                
                if new_status in [s[0] for s in MercadoPagoPayment.STATUS_CHOICES]:
                    payment.status = new_status
                    
                    if new_status == 'approved':
                        payment.paid_at = timezone.now()
                    
                    payment.save()
                    print(f"DEBUG: Pagamento {payment.id} atualizado via return: {old_status} -> {new_status}")
            
            # Se ainda está pendente, tentar consultar a API do MP diretamente
            if payment.status == 'pending' and payment.config and payment.config.access_token:
                try:
                    from .services.mercadopago_service import MercadoPagoService
                    mp_service = MercadoPagoService(payment.config.access_token)
                    
                    # Buscar por external_reference
                    ext_ref = payment.pix_qr_code if payment.pix_qr_code and payment.pix_qr_code.startswith('pandia_') else external_reference
                    if ext_ref:
                        search_result = mp_service.search_payments(external_reference=ext_ref, limit=5)
                        for mp_data in search_result.get('results', []):
                            if mp_data.get('external_reference') == ext_ref:
                                mp_status = mp_data.get('status', '')
                                if mp_status == 'approved':
                                    payment.status = 'approved'
                                    payment.mp_payment_id = str(mp_data.get('id', ''))
                                    payment.paid_at = timezone.now()
                                    payment.save()
                                    print(f"DEBUG: Pagamento {payment.id} confirmado via API lookup")
                                break
                except Exception as e:
                    print(f"DEBUG: Erro ao consultar MP API no return: {e}")
                    
        except MercadoPagoPayment.DoesNotExist:
            print(f"DEBUG: Pagamento {payment_id} não encontrado")
    
    # Renderizar página baseada no status
    context = {
        'payment': payment,
        'status': payment.status if payment else final_status,
        'amount': payment.amount if payment else None,
        'description': payment.description if payment else None,
        'padaria_name': payment.config.padaria.name if payment and payment.config and payment.config.padaria else None,
    }
    
    if payment and payment.status == 'approved':
        return render(request, 'payments/mp_success.html', context)
    elif payment and payment.status in ['rejected', 'cancelled']:
        return render(request, 'payments/mp_failure.html', context)
    else:
        return render(request, 'payments/mp_pending.html', context)


def mp_checkout_gate(request, payment_id):
    """
    Página intermediária que verifica se o pagamento já foi realizado
    antes de redirecionar para o checkout do Mercado Pago.
    
    Se já foi pago, mostra mensagem e bloqueia o acesso ao link.
    """
    try:
        payment = MercadoPagoPayment.objects.select_related('config', 'config__padaria').get(id=payment_id)
        
        context = {
            'payment': payment,
            'padaria_name': payment.config.padaria.name if payment.config and payment.config.padaria else 'Loja',
        }
        
        # Verificar se já foi pago
        if payment.status == 'approved':
            return render(request, 'payments/mp_already_paid.html', context)
        
        # Verificar se foi cancelado ou rejeitado
        if payment.status in ['cancelled', 'rejected', 'refunded']:
            return render(request, 'payments/mp_expired.html', context)
        
        # Se ainda está pendente, tentar sincronizar antes de redirecionar
        if payment.status == 'pending' and payment.config and payment.config.access_token:
            try:
                from .services.mercadopago_service import MercadoPagoService
                mp_service = MercadoPagoService(payment.config.access_token)
                
                ext_ref = payment.pix_qr_code if payment.pix_qr_code and payment.pix_qr_code.startswith('pandia_') else None
                if ext_ref:
                    search_result = mp_service.search_payments(external_reference=ext_ref, limit=1)
                    for mp_data in search_result.get('results', []):
                        if mp_data.get('external_reference') == ext_ref and mp_data.get('status') == 'approved':
                            payment.status = 'approved'
                            payment.mp_payment_id = str(mp_data.get('id', ''))
                            payment.paid_at = timezone.now()
                            payment.save()
                            return render(request, 'payments/mp_already_paid.html', context)
            except Exception:
                pass
        
        # Redirecionar para o checkout do MP
        if payment.checkout_url:
            return redirect(payment.checkout_url)
        else:
            return render(request, 'payments/mp_error.html', {
                'error': 'Link de pagamento não disponível',
                **context
            })
            
    except MercadoPagoPayment.DoesNotExist:
        return render(request, 'payments/mp_error.html', {
            'error': 'Pagamento não encontrado'
        })
