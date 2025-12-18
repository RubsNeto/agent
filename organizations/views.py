from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.db.models import Prefetch
from .models import Padaria, PadariaUser, ApiKey
from audit.models import AuditLog
import requests


def get_user_padarias(user):
    """Retorna padarias que o usuário pode acessar."""
    if user.is_superuser:
        return Padaria.objects.all()
    user_padaria_ids = PadariaUser.objects.filter(user=user).values_list('padaria_id', flat=True)
    return Padaria.objects.filter(id__in=user_padaria_ids)


@login_required
def organization_list(request):
    """Redireciona para a padaria do usuário ou lista se for admin."""
    padarias = get_user_padarias(request.user)
    
    # Se não for superuser e tiver apenas uma padaria, redireciona direto
    if not request.user.is_superuser and padarias.count() == 1:
        padaria = padarias.first()
        return redirect('organizations:detail', slug=padaria.slug)
    
    return render(request, "organizations/list.html", {"organizations": padarias})


@login_required
def organization_detail(request, slug):
    """
    Detalhe de uma padaria.
    
    CORREÇÃO: O problema estava aqui - o objeto precisa ser passado
    corretamente no contexto do template.
    """
    # Buscar padarias com otimização (select_related/prefetch_related se necessário)
    padarias = get_user_padarias(request.user)
    
    # Buscar a organização específica
    organization = get_object_or_404(Padaria, slug=slug)
    
    # Verificar acesso
    if not request.user.is_superuser and organization not in padarias:
        messages.error(request, "Você não tem acesso a esta padaria.")
        return redirect("organizations:list")
    
    # CORREÇÃO: Passar o objeto correto no contexto
    context = {
        'organization': organization,  # Nome correto da variável
    }
    
    # CORREÇÃO: Caminho correto do template
    return render(request, "organizations/detail.html", context)


@login_required
def organization_create(request):
    """Criar nova padaria (apenas admin)."""
    if not request.user.is_superuser:
        messages.error(request, "Apenas administradores podem criar padarias.")
        return redirect("organizations:list")
    
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        cnpj = request.POST.get("cnpj", "").strip()
        phone = request.POST.get("phone", "").strip()
        email = request.POST.get("email", "").strip()
        address = request.POST.get("address", "").strip()
        
        if not name:
            messages.error(request, "Nome é obrigatório.")
            return render(request, "organizations/form.html")
        
        try:
            # Criar padaria
            org = Padaria.objects.create(
                name=name,
                owner=request.user,
                cnpj=cnpj or None,  # Evitar strings vazias
                phone=phone or None,
                email=email or None,
                address=address or None
            )
            
            # Criar membership como dono
            PadariaUser.objects.create(
                user=request.user,
                padaria=org,
                role='dono'
            )
            
            # Log de auditoria
            AuditLog.log(
                action="create",
                entity="Padaria",
                padaria=org,
                actor=request.user,
                entity_id=org.id,
                diff={
                    "name": name,
                    "cnpj": cnpj,
                    "phone": phone,
                    "email": email,
                    "address": address
                }
            )
            
            messages.success(
                request,
                f"Padaria '{name}' criada com sucesso!\n"
                f"Usuário '{request.user.email}' vinculado como dono."
            )
            return redirect("organizations:detail", slug=org.slug)
            
        except Exception as e:
            messages.error(request, f"Erro ao criar padaria: {str(e)}")
            return render(request, "organizations/form.html")
    
    return render(request, "organizations/form.html")


@login_required
def organization_edit(request, slug):
    """Editar padaria."""
    padarias = get_user_padarias(request.user)
    organization = get_object_or_404(Padaria, slug=slug)
    
    # Verificar acesso
    if not request.user.is_superuser and organization not in padarias:
        messages.error(request, "Você não tem acesso a esta padaria.")
        return redirect("organizations:list")
    
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        cnpj = request.POST.get("cnpj", "").strip()
        phone = request.POST.get("phone", "").strip()
        email = request.POST.get("email", "").strip()
        address = request.POST.get("address", "").strip()
        
        if not name:
            messages.error(request, "Nome é obrigatório.")
            return render(request, "organizations/form.html", {"organization": organization})
        
        try:
            # Preparar diff para auditoria
            diff = {}
            
            if organization.name != name:
                diff['name'] = {'old': organization.name, 'new': name}
            if organization.cnpj != cnpj:
                diff['cnpj'] = {'old': organization.cnpj or '', 'new': cnpj}
            if organization.phone != phone:
                diff['phone'] = {'old': organization.phone or '', 'new': phone}
            if organization.email != email:
                diff['email'] = {'old': organization.email or '', 'new': email}
            if organization.address != address:
                diff['address'] = {'old': organization.address or '', 'new': address}
            
            # Atualizar campos
            organization.name = name
            organization.cnpj = cnpj or None
            organization.phone = phone or None
            organization.email = email or None
            organization.address = address or None
            organization.save()
            
            # Log de auditoria apenas se houve mudanças
            if diff:
                AuditLog.log(
                    action="update",
                    entity="Padaria",
                    padaria=organization,
                    actor=request.user,
                    entity_id=organization.id,
                    diff=diff
                )
            
            messages.success(request, "Informações atualizadas com sucesso!")
            return redirect("organizations:detail", slug=organization.slug)
            
        except Exception as e:
            messages.error(request, f"Erro ao atualizar padaria: {str(e)}")
    
    context = {'organization': organization}
    return render(request, "organizations/form.html", context)


@login_required
def organization_delete(request, slug):
    """Deletar padaria (apenas admin)."""
    if not request.user.is_superuser:
        messages.error(request, "Apenas administradores podem deletar padarias.")
        return redirect("organizations:list")
    
    organization = get_object_or_404(Padaria, slug=slug)
    
    if request.method == "POST":
        org_name = organization.name
        org_id = organization.id
        
        try:
            # Log antes de deletar
            AuditLog.log(
                action="delete",
                entity="Padaria",
                padaria=None,  # Não passar a instância pois será deletada
                actor=request.user,
                entity_id=org_id,
                diff={"name": org_name, "slug": slug}
            )
            
            organization.delete()
            messages.success(request, f"Padaria '{org_name}' deletada com sucesso!")
            return redirect("organizations:list")
            
        except Exception as e:
            messages.error(request, f"Erro ao deletar padaria: {str(e)}")
            return redirect("organizations:detail", slug=slug)
    
    context = {'organization': organization}
    return render(request, "organizations/confirm_delete.html", context)


@login_required
def apikey_list(request):
    """Lista de API keys do usuário."""
    padarias = get_user_padarias(request.user)
    
    # Admin vê todas as API Keys das padarias dele
    if request.user.is_superuser:
        api_keys = ApiKey.objects.filter(
            padaria__in=padarias
        ).select_related('padaria', 'agent')
    else:
        # Usuários normais só veem API Keys dos seus agentes
        from agents.models import Agent
        user_agents = Agent.objects.filter(padaria__in=padarias)
        api_keys = ApiKey.objects.filter(
            agent__in=user_agents
        ).select_related('padaria', 'agent')
    
    context = {'api_keys': api_keys}
    return render(request, "organizations/apikey_list.html", context)


@login_required
def apikey_create(request):
    """Criar nova API key."""
    padarias = get_user_padarias(request.user)
    
    if request.method == "POST":
        org_id = request.POST.get("organization")
        agent_id = request.POST.get("agent")
        name = request.POST.get("name", "").strip()
        
        if not org_id:
            messages.error(request, "Selecione uma organização.")
            return redirect("organizations:apikey_create")
        
        organization = get_object_or_404(Padaria, id=org_id)
        
        # Verificar acesso
        if not request.user.is_superuser and organization not in padarias:
            messages.error(request, "Você não tem acesso a esta padaria.")
            return redirect("organizations:apikeys")
        
        # Para usuários não-admin, agente é obrigatório
        if not request.user.is_superuser and not agent_id:
            messages.error(request, "Você deve selecionar um agente específico para a API Key.")
            return redirect("organizations:apikey_create")
        
        # Buscar agente se fornecido
        agent = None
        if agent_id:
            from agents.models import Agent
            agent = get_object_or_404(Agent, id=agent_id, padaria=organization)
            
            # Verificar se usuário tem acesso a este agente (não-admin)
            if not request.user.is_superuser:
                user_padarias = PadariaUser.objects.filter(
                    user=request.user
                ).values_list('padaria_id', flat=True)
                
                if agent.padaria_id not in user_padarias:
                    messages.error(request, "Você não tem acesso a este agente.")
                    return redirect("organizations:apikeys")
        
        try:
            api_key = ApiKey.objects.create(
                padaria=organization,
                agent=agent,
                name=name
            )
            
            agent_info = f" para agente '{agent.name}'" if agent else " (acesso a todos os agentes)"
            
            AuditLog.log(
                action="create",
                entity="ApiKey",
                padaria=organization,
                actor=request.user,
                entity_id=api_key.id,
                diff={
                    "name": name,
                    "agent": agent.name if agent else "Todos"
                }
            )
            
            messages.success(request, f"API Key criada{agent_info}: {api_key.key}")
            messages.warning(request, "⚠️ Copie a chave agora! Ela não será exibida novamente.")
            return redirect("organizations:apikeys")
            
        except Exception as e:
            messages.error(request, f"Erro ao criar API Key: {str(e)}")
            return redirect("organizations:apikey_create")
    
    # Buscar agentes para o formulário
    from agents.models import Agent
    agents_by_org = {}
    
    for padaria in padarias:
        agents_by_org[padaria.id] = list(
            Agent.objects.filter(
                padaria=padaria,
                is_active=True
            ).values('id', 'name')
        )
    
    context = {
        "organizations": padarias,
        "agents_by_org": agents_by_org,
        "is_admin": request.user.is_superuser
    }
    
    return render(request, "organizations/apikey_form.html", context)


@login_required
def apikey_delete(request, pk):
    """Deletar API key."""
    padarias = get_user_padarias(request.user)
    api_key = get_object_or_404(ApiKey, pk=pk)
    
    # Verificar acesso - admin pode deletar qualquer uma da padaria
    if request.user.is_superuser:
        if api_key.padaria not in padarias:
            messages.error(request, "Você não tem acesso a esta API key.")
            return redirect("organizations:apikeys")
    else:
        # Usuários normais só podem deletar API Keys dos seus agentes
        from agents.models import Agent
        user_agents = Agent.objects.filter(padaria__in=padarias)
        
        if not api_key.agent or api_key.agent not in user_agents:
            messages.error(request, "Você não tem acesso a esta API key.")
            return redirect("organizations:apikeys")
    
    if request.method == "POST":
        organization = api_key.padaria
        key_preview = api_key.key[:12]
        api_key_id = api_key.id
        
        try:
            AuditLog.log(
                action="delete",
                entity="ApiKey",
                padaria=organization,
                actor=request.user,
                entity_id=api_key_id,
                diff={"key_preview": key_preview}
            )
            
            api_key.delete()
            messages.success(request, "API Key deletada com sucesso!")
            return redirect("organizations:apikeys")
            
        except Exception as e:
            messages.error(request, f"Erro ao deletar API Key: {str(e)}")
            return redirect("organizations:apikeys")
    
    context = {'api_key': api_key}
    return render(request, "organizations/apikey_confirm_delete.html", context)


@login_required
def whatsapp_connect(request, slug):
    """Gerar QR Code para conectar WhatsApp via Evolution API."""
    padarias = get_user_padarias(request.user)
    organization = get_object_or_404(Padaria, slug=slug)
    
    # Verificar acesso
    if not request.user.is_superuser and organization not in padarias:
        messages.error(request, "Você não tem acesso a esta padaria.")
        return redirect("organizations:list")
    
    # Nome da instância baseado no slug da padaria
    instance_name = f"padaria_{organization.slug}"
    
    context = {
        "organization": organization,
        "instance_name": instance_name,
        "qr_code": None,
        "is_connected": False,
        "error": None,
        "pairing_code": None,
    }
    
    # Se for requisição AJAX para buscar QR Code
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Configurar Evolution API
            api_url = getattr(settings, 'EVOLUTION_API_URL', None)
            api_key = getattr(settings, 'EVOLUTION_API_KEY', None)
            
            if not api_url or not api_key:
                return JsonResponse({
                    "success": False,
                    "error": "Sistema não configurado corretamente. Entre em contato com o suporte."
                })
            
            headers = {
                "apikey": api_key,
                "Content-Type": "application/json"
            }
            
            # Passo 1: Tentar criar a instância (se não existir)
            create_url = f"{api_url}/instance/create"
            create_payload = {
                "instanceName": instance_name,
                "qrcode": True,
                "integration": "WHATSAPP-BAILEYS"
            }
            
            try:
                create_response = requests.post(
                    create_url,
                    headers=headers,
                    json=create_payload,
                    timeout=10
                )
                
                # Se retornar 201 (criado) ou 200 (já existe), seguir em frente
                if create_response.status_code in [200, 201]:
                    # Registrar criação da instância
                    AuditLog.log(
                        action="whatsapp_instance_created",
                        entity="Padaria",
                        padaria=organization,
                        actor=request.user,
                        entity_id=organization.id,
                        diff={"instance": instance_name}
                    )
                    
                    # Configurar webhook automaticamente
                    _configure_webhook(api_url, headers, instance_name)
                    
                elif create_response.status_code in [403, 409]:
                    # Instância já existe, está OK - continuar
                    pass
                else:
                    # Outro erro ao criar
                    error_msg = _extract_error_message(create_response)
                    return JsonResponse({
                        "success": False,
                        "error": f"Erro ao criar instância: {error_msg}"
                    })
                    
            except requests.exceptions.RequestException:
                # Se falhar ao criar, tentar conectar (pode já existir)
                pass
            
            # Passo 2: Buscar QR Code da instância
            connect_url = f"{api_url}/instance/connect/{instance_name}"
            response = requests.get(connect_url, headers=headers, timeout=10)
            
            # Tratar resposta
            if response.status_code == 200:
                data = response.json()
                
                # Verificar se já está conectado
                instance_data = data.get("instance", {})
                state = data.get("state") or instance_data.get("state")
                status = data.get("status") or instance_data.get("status")
                
                if state == "open" or status == "connected":
                    return JsonResponse({
                        "success": True,
                        "is_connected": True,
                        "message": "WhatsApp já está conectado!"
                    })
                
                # Extrair QR Code e pairing code
                qr_code = _extract_qr_code(data)
                pairing_code = _extract_pairing_code(data)
                
                if qr_code:
                    # Adicionar prefixo data:image se necessário
                    if not qr_code.startswith("data:image"):
                        qr_code = f"data:image/png;base64,{qr_code}"
                    
                    # Registrar auditoria
                    AuditLog.log(
                        action="whatsapp_qr_generated",
                        entity="Padaria",
                        padaria=organization,
                        actor=request.user,
                        entity_id=organization.id,
                        diff={"instance": instance_name}
                    )
                    
                    return JsonResponse({
                        "success": True,
                        "qr_code": qr_code,
                        "pairing_code": pairing_code,
                        "is_connected": False
                    })
                else:
                    # Aguardando inicialização
                    return JsonResponse({
                        "success": False,
                        "error": "O WhatsApp ainda está inicializando. "
                                "Por favor, aguarde alguns segundos e tente novamente."
                    })
                    
            elif response.status_code == 404:
                return JsonResponse({
                    "success": False,
                    "error": "Instância WhatsApp não encontrada. "
                            "Tente recarregar a página e gerar novamente."
                })
            else:
                error_msg = _extract_error_message(response)
                return JsonResponse({
                    "success": False,
                    "error": error_msg
                })
                
        except requests.exceptions.Timeout:
            return JsonResponse({
                "success": False,
                "error": "A conexão demorou muito para responder. "
                        "Verifique sua internet e tente novamente."
            })
        except requests.exceptions.ConnectionError:
            return JsonResponse({
                "success": False,
                "error": "Não foi possível conectar ao serviço WhatsApp. "
                        "Tente novamente em alguns instantes."
            })
        except Exception as e:
            # Log do erro real para debug
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro no WhatsApp connect: {str(e)}", exc_info=True)
            
            return JsonResponse({
                "success": False,
                "error": "Ocorreu um erro inesperado. Por favor, tente novamente."
            })
    
    # Renderizar página
    return render(request, "organizations/whatsapp_connect.html", context)


# Funções auxiliares
def _extract_error_message(response):
    """Extrai mensagem de erro de forma amigável."""
    try:
        error_data = response.json()
        
        # Tentar extrair de response.message primeiro
        if isinstance(error_data.get("response"), dict):
            error_msg = error_data["response"].get("message", "")
        else:
            error_msg = error_data.get("message", "")
        
        # Se message é uma lista, extrair primeiro item
        if isinstance(error_msg, list) and len(error_msg) > 0:
            error_msg = error_msg[0]
        
        if not error_msg:
            error_msg = response.text or "Erro desconhecido"
            
        return error_msg
    except Exception:
        return "Ocorreu um erro inesperado. Tente novamente."


def _extract_qr_code(data):
    """Extrai QR Code de diferentes estruturas de resposta."""
    qr_code = None
    
    # Verificar diferentes estruturas
    if "base64" in data:
        qr_code = data["base64"]
    elif "qrcode" in data:
        qr_code = data["qrcode"]
        if isinstance(qr_code, dict):
            qr_code = qr_code.get("base64") or qr_code.get("code")
    elif "code" in data:
        qr_code = data["code"]
    
    return qr_code


def _extract_pairing_code(data):
    """Extrai pairing code da resposta."""
    pairing_code = None
    
    if "pairingCode" in data:
        pairing_code = data["pairingCode"]
    elif "code" in data and not _extract_qr_code(data):
        pairing_code = data["code"]
    
    return pairing_code


def _configure_webhook(api_url, headers, instance_name):
    """
    Configura webhook automaticamente para a instância.
    
    Configura:
    - URL: https://n8n.newcouros.com.br/webhook/vendedorrr
    - Enabled: True
    - Evento: MESSAGES_UPSERT
    """
    try:
        webhook_url = f"{api_url}/webhook/set/{instance_name}"
        webhook_payload = {
            "url": "https://n8n.newcouros.com.br/webhook/vendedorrr",
            "enabled": True,
            "webhookByEvents": False,
            "webhookBase64": False,
            "events": [
                "MESSAGES_UPSERT"
            ]
        }
        
        response = requests.post(
            webhook_url,
            headers=headers,
            json=webhook_payload,
            timeout=10
        )
        
        # Log para debug (opcional)
        import logging
        logger = logging.getLogger(__name__)
        
        if response.status_code in [200, 201]:
            logger.info(f"Webhook configurado com sucesso para {instance_name}")
        else:
            logger.warning(f"Erro ao configurar webhook para {instance_name}: {response.text}")
            
    except Exception as e:
        # Não interromper o fluxo se o webhook falhar
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Exceção ao configurar webhook para {instance_name}: {str(e)}")