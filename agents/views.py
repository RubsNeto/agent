from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Agent
from .utils import extract_text_from_pdf
from .forms import AgentSimpleForm
from .presets import get_preset_defaults, AGENT_PRESETS
from organizations.models import Padaria, PadariaUser
from core.permissions import get_user_padaria, get_user_role
from audit.models import AuditLog
import requests
import json


def get_user_padarias(user):
    """Retorna padarias que o usuário pode acessar."""
    if user.is_superuser:
        return Padaria.objects.all()
    
    memberships = PadariaUser.objects.filter(user=user).values_list('padaria_id', flat=True)
    return Padaria.objects.filter(id__in=memberships)


@login_required
def agent_list(request):
    """Redireciona para o agente do usuário ou lista se tiver múltiplos."""
    padarias = get_user_padarias(request.user)
    agents = Agent.objects.filter(padaria__in=padarias).select_related('padaria')
    
    # Se não for superuser e tiver apenas um agente, redireciona direto
    if not request.user.is_superuser and agents.count() == 1:
        agent = agents.first()
        return redirect('agents:detail', slug=agent.slug)
    
    return render(request, "agents/list.html", {"agents": agents})


@login_required
def agent_detail(request, slug):
    """Detalhe de um agente."""
    padarias = get_user_padarias(request.user)
    agent = get_object_or_404(Agent, slug=slug, padaria__in=padarias)
    return render(request, "agents/detail.html", {"agent": agent})


@login_required
def agent_create(request):
    """Criar novo agente com formulário simplificado."""
    # Verificar se o usuário é dono de alguma padaria
    user_role = get_user_role(request.user)
    if user_role not in ['admin_master', 'dono']:
        messages.error(request, "Apenas donos de padaria podem criar agentes.")
        return redirect("agents:list")
    
    if request.method == "POST":
        print("DEBUG CREATE - POST recebido")
        print(f"DEBUG CREATE - action: {request.POST.get('action')}")
        
        # Verificar se é aplicação de preset
        apply_preset_action = request.POST.get('action') == 'apply_preset'
        
        form = AgentSimpleForm(request.POST, request.FILES, user=request.user)
        
        if apply_preset_action:
            # Aplicar defaults do preset selecionado
            preset_key = request.POST.get('agent_preset', 'neutral')
            defaults = get_preset_defaults(preset_key)
            
            # Criar novo form com defaults aplicados
            initial_data = request.POST.copy()
            for field, value in defaults.items():
                if field in form.fields:
                    initial_data[field] = value
            
            form = AgentSimpleForm(initial_data, request.FILES, user=request.user)
            messages.info(request, f"Padrões do perfil aplicados! Revise e salve quando estiver pronto.")
            
            return render(request, "agents/form_new.html", {
                "form": form,
                "presets": AGENT_PRESETS,
                "is_create": True
            })
        
        print(f"DEBUG CREATE - form.is_valid(): {form.is_valid()}")
        if not form.is_valid():
            print(f"DEBUG CREATE - Erros do formulário: {form.errors}")
            print(f"DEBUG CREATE - Erros por campo:")
            for field, errors in form.errors.items():
                print(f"  - {field}: {errors}")
        
        if form.is_valid():
            padaria = form.cleaned_data.get('padaria')
            
            # Verificar limite de 1 agente por padaria
            if padaria.has_agent():
                messages.error(request, f"A padaria '{padaria.name}' já possui um agente. Cada padaria pode ter apenas 1 agente.")
                return render(request, "agents/form_new.html", {
                    "form": form,
                    "presets": AGENT_PRESETS,
                    "is_create": True
                })
            
            agent = form.save(commit=False)
            agent.status = form.cleaned_data.get('status', 'ativo')
            
            # Aplicar role do preset se selecionado
            preset_key = form.cleaned_data.get('agent_preset')
            if preset_key and preset_key != 'neutral':
                defaults = get_preset_defaults(preset_key)
                if not agent.personality:
                    agent.personality = defaults.get('personality', 'profissional')
                if not agent.tone:
                    agent.tone = defaults.get('tone', 'profissional')
            
            agent.save()
            
            # Processar PDF se enviado
            if 'knowledge_pdf' in request.FILES:
                try:
                    pdf_file = request.FILES['knowledge_pdf']
                    extracted_text = extract_text_from_pdf(pdf_file)
                    agent.knowledge_pdf_text = extracted_text
                    agent.save()
                    
                    # Enviar para n8n
                    try:
                        webhook_url = "https://n8n.newcouros.com.br/webhook/memoria"
                        payload = {
                            "agent_id": agent.id,
                            "agent_name": agent.name,
                            "agent_slug": agent.slug,
                            "pdf_filename": pdf_file.name,
                            "pdf_category": agent.knowledge_pdf_category or "Sem categoria",
                            "extracted_text": extracted_text,
                            "text_length": len(extracted_text),
                            "padaria": agent.padaria.name,
                            "uploaded_by": request.user.email
                        }
                        
                        response = requests.post(
                            webhook_url,
                            json=payload,
                            headers={'Content-Type': 'application/json'},
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            messages.success(request, f"PDF processado e enviado para n8n! {len(extracted_text)} caracteres extraídos.")
                        else:
                            messages.success(request, f"PDF processado! {len(extracted_text)} caracteres extraídos.")
                            messages.warning(request, f"Webhook n8n retornou status {response.status_code}")
                    except requests.exceptions.RequestException as webhook_error:
                        messages.success(request, f"PDF processado! {len(extracted_text)} caracteres extraídos.")
                        messages.warning(request, f"Erro ao enviar para n8n: {str(webhook_error)}")
                        
                except Exception as e:
                    messages.warning(request, f"Erro ao processar PDF: {str(e)}")
            
            AuditLog.log(
                action="create",
                entity="Agent",
                padaria=agent.padaria,
                actor=request.user,
                entity_id=agent.id,
                diff={"name": agent.name, "slug": agent.slug}
            )
            
            # Gerar API Key automaticamente para usuários não-admin
            if not request.user.is_superuser:
                from organizations.models import ApiKey
                api_key = ApiKey.objects.create(
                    padaria=agent.padaria,
                    agent=agent,
                    name=f"Auto - {agent.name}"
                )
                messages.success(
                    request, 
                    f"Agente '{agent.name}' criado com sucesso! ✨\n\n"
                    f"🔑 API Key gerada: {api_key.key}\n\n"
                    f"⚠️ Copie a chave agora! Ela não será exibida novamente."
                )
            else:
                messages.success(request, f"Agente '{agent.name}' criado com sucesso! ✨")
            
            return redirect("agents:detail", slug=agent.slug)
    else:
        # Check for padaria query param to pre-select
        padaria_slug = request.GET.get('padaria')
        initial = {}
        if padaria_slug:
            from organizations.models import Padaria
            try:
                padaria = Padaria.objects.get(slug=padaria_slug)
                initial['padaria'] = padaria.id
            except Padaria.DoesNotExist:
                pass
        form = AgentSimpleForm(user=request.user, initial=initial)
    
    return render(request, "agents/form_new.html", {
        "form": form,
        "presets": AGENT_PRESETS,
        "is_create": True
    })


@login_required
def agent_edit(request, slug):
    """Editar agente com formulário simplificado."""
    padarias = get_user_padarias(request.user)
    agent = get_object_or_404(Agent, slug=slug, padaria__in=padarias)
    
    # Verificar permissão (dono ou funcionário pode editar)
    user_role = get_user_role(request.user, agent.padaria)
    if user_role not in ['admin_master', 'dono', 'funcionario']:
        messages.error(request, "Você não tem permissão para editar este agente.")
        return redirect("agents:list")
    
    if request.method == "POST":
        # Verificar se é aplicação de preset
        apply_preset_action = request.POST.get('action') == 'apply_preset'
        
        form = AgentSimpleForm(request.POST, request.FILES, instance=agent, user=request.user)
        
        print(f"DEBUG EDIT - POST recebido para agente: {agent.slug}")
        print(f"DEBUG EDIT - apply_preset_action: {apply_preset_action}")
        
        if apply_preset_action:
            # Aplicar defaults do preset selecionado
            preset_key = request.POST.get('agent_preset', 'neutral')
            defaults = get_preset_defaults(preset_key)
            
            # Criar novo form com defaults aplicados
            initial_data = request.POST.copy()
            for field, value in defaults.items():
                if field in form.fields:
                    initial_data[field] = value
            
            form = AgentSimpleForm(initial_data, request.FILES, instance=agent, user=request.user)
            messages.info(request, f"Padrões do perfil aplicados! Revise e salve quando estiver pronto.")
            
            return render(request, "agents/form_new.html", {
                "form": form,
                "agent": agent,
                "presets": AGENT_PRESETS,
                "is_create": False
            })
        
        print(f"DEBUG EDIT - form.is_valid(): {form.is_valid()}")
        if not form.is_valid():
            print(f"DEBUG EDIT - Erros do formulário: {form.errors}")
        
        if form.is_valid():
            agent = form.save(commit=False)
            agent.status = form.cleaned_data.get('status', agent.status)
            agent.save()
            
            pdf_updated = False
            extracted_text = None
            pdf_filename = None
            
            # Processar PDF se enviado (novo upload)
            if 'knowledge_pdf' in request.FILES:
                try:
                    pdf_file = request.FILES['knowledge_pdf']
                    extracted_text = extract_text_from_pdf(pdf_file)
                    agent.knowledge_pdf_text = extracted_text
                    agent.save()
                    pdf_updated = True
                    pdf_filename = pdf_file.name
                except Exception as e:
                    messages.warning(request, f"Erro ao processar PDF: {str(e)}")
            
            # Se tem PDF (novo ou existente), enviar para n8n
            if agent.knowledge_pdf and agent.knowledge_pdf_text:
                try:
                    webhook_url = "https://n8n.newcouros.com.br/webhook/memoria"
                    payload = {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "agent_slug": agent.slug,
                        "pdf_filename": pdf_filename or agent.knowledge_pdf.name,
                        "pdf_category": agent.knowledge_pdf_category or "Sem categoria",
                        "extracted_text": extracted_text or agent.knowledge_pdf_text,
                        "text_length": len(extracted_text or agent.knowledge_pdf_text),
                        "padaria": agent.padaria.name,
                        "uploaded_by": request.user.email,
                        "action": "new_upload" if pdf_updated else "update"
                    }
                    
                    response = requests.post(
                        webhook_url,
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        if pdf_updated:
                            messages.success(request, f"PDF atualizado e enviado para n8n! {len(extracted_text)} caracteres extraídos.")
                        else:
                            messages.success(request, "Agente e conhecimento atualizados no n8n! ✨")
                    else:
                        if pdf_updated:
                            messages.success(request, f"PDF atualizado! {len(extracted_text)} caracteres extraídos.")
                        messages.warning(request, f"Webhook n8n retornou status {response.status_code}")
                except requests.exceptions.RequestException as webhook_error:
                    if pdf_updated:
                        messages.success(request, f"PDF atualizado! {len(extracted_text)} caracteres extraídos.")
                    messages.warning(request, f"Erro ao enviar para n8n: {str(webhook_error)}")
            
            AuditLog.log(
                action="update",
                entity="Agent",
                padaria=agent.padaria,
                actor=request.user,
                entity_id=agent.id,
                diff={"name": agent.name}
            )
            
            messages.success(request, "Agente atualizado com sucesso! ✨")
            return redirect("agents:detail", slug=agent.slug)
    else:
        form = AgentSimpleForm(instance=agent, user=request.user)
    
    return render(request, "agents/form_new.html", {
        "form": form,
        "agent": agent,
        "presets": AGENT_PRESETS,
        "is_create": False
    })


@login_required
def agent_delete(request, slug):
    """Deletar agente."""
    padarias = get_user_padarias(request.user)
    agent = get_object_or_404(Agent, slug=slug, padaria__in=padarias)
    
    # Verificar permissão (apenas dono pode deletar)
    user_role = get_user_role(request.user, agent.padaria)
    if user_role not in ['admin_master', 'dono']:
        messages.error(request, "Apenas donos de padaria podem deletar agentes.")
        return redirect("agents:list")
    
    if request.method == "POST":
        padaria = agent.padaria
        agent_name = agent.name
        
        AuditLog.log(
            action="delete",
            entity="Agent",
            padaria=padaria,
            actor=request.user,
            entity_id=agent.id,
            diff={"name": agent_name, "slug": slug}
        )
        
        agent.delete()
        messages.success(request, f"Agente '{agent_name}' deletado com sucesso!")
        return redirect("agents:list")
    
    return render(request, "agents/confirm_delete.html", {"agent": agent})


@login_required
def agent_playground(request, slug):
    """Playground para testar agente."""
    padarias = get_user_padarias(request.user)
    agent = get_object_or_404(Agent, slug=slug, padaria__in=padarias)
    
    # Renderizar greeting com valores de exemplo
    cliente_nome = request.POST.get("cliente_nome", "Maria")
    rendered_greeting = agent.render_greeting(cliente_nome=cliente_nome)
    
    context = {
        "agent": agent,
        "rendered_greeting": rendered_greeting,
        "cliente_nome": cliente_nome,
    }
    
    return render(request, "agents/playground.html", context)


@login_required
def agent_delete_pdf(request, slug):
    """Deletar PDF de conhecimento do agente."""
    padarias = get_user_padarias(request.user)
    agent = get_object_or_404(Agent, slug=slug, padaria__in=padarias)
    
    # Verificar permissão
    user_role = get_user_role(request.user, agent.padaria)
    if user_role not in ['admin_master', 'dono', 'funcionario']:
        messages.error(request, "Você não tem permissão para esta ação.")
        return redirect("agents:list")
    
    if request.method == "POST":
        if agent.knowledge_pdf:
            # Deletar arquivo físico
            agent.knowledge_pdf.delete(save=False)
            # Limpar campos relacionados
            agent.knowledge_pdf_text = ""
            agent.knowledge_pdf_category = ""
            agent.save()
            
            AuditLog.log(
                action="delete_pdf",
                entity="Agent",
                padaria=agent.padaria,
                actor=request.user,
                entity_id=agent.id,
                diff={"agent": agent.name, "action": "PDF deletado"}
            )
            
            messages.success(request, "PDF deletado com sucesso!")
        else:
            messages.warning(request, "Este agente não possui PDF.")
        
        return redirect("agents:detail", slug=agent.slug)
    
    return render(request, "agents/confirm_delete_pdf.html", {"agent": agent})
