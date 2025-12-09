from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Agent
from .utils import extract_text_from_pdf
from .forms import AgentSimpleForm
from .presets import get_preset_defaults, AGENT_PRESETS
from organizations.models import Organization
from audit.models import AuditLog
import requests
import json


@login_required
def agent_list(request):
    """Lista de agentes do usuário."""
    agents = Agent.objects.filter(organization__owner=request.user)
    return render(request, "agents/list.html", {"agents": agents})


@login_required
def agent_detail(request, slug):
    """Detalhe de um agente."""
    agent = get_object_or_404(Agent, slug=slug, organization__owner=request.user)
    return render(request, "agents/detail.html", {"agent": agent})


@login_required
def agent_create(request):
    """Criar novo agente com formulário simplificado."""
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
                            "organization": agent.organization.name,
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
                organization=agent.organization,
                actor=request.user,
                entity_id=agent.id,
                diff={"name": agent.name, "slug": agent.slug}
            )
            
            messages.success(request, f"Agente '{agent.name}' criado com sucesso! ✨")
            return redirect("agents:detail", slug=agent.slug)
    else:
        form = AgentSimpleForm(user=request.user)
    
    return render(request, "agents/form_new.html", {
        "form": form,
        "presets": AGENT_PRESETS,
        "is_create": True
    })


@login_required
def agent_create_old(request):
    """Criar novo agente - VERSÃO ANTIGA."""
    if request.method == "POST":
        org_id = request.POST.get("organization")
        name = request.POST.get("name")
        role = request.POST.get("role", "atendente")
        sector = request.POST.get("sector", "manicure/pedicure")
        
        organization = get_object_or_404(Organization, id=org_id, owner=request.user)
        
        # Criar agente com novos campos
        agent = Agent.objects.create(
            organization=organization,
            name=name,
            role=role,
            sector=sector,
            language=request.POST.get("language", "pt-BR"),
            status=request.POST.get("status", "ativo"),
            personality=request.POST.get("personality", "amigavel"),
            greeting=request.POST.get("greeting", ""),
            out_of_hours_message=request.POST.get("out_of_hours_message", ""),
            transfer_keywords=request.POST.get("transfer_keywords", "falar com humano, atendente, pessoa"),
            max_response_time=int(request.POST.get("max_response_time", 30)),
            tone=request.POST.get("tone", ""),
            style_guidelines=request.POST.get("style_guidelines", ""),
            knowledge_base=request.POST.get("knowledge_base", ""),
            fallback_message=request.POST.get("fallback_message", ""),
            escalation_rule=request.POST.get("escalation_rule", ""),
            n8n_webhook_url=request.POST.get("n8n_webhook_url", ""),
        )
        
        # Processar upload de PDF se houver
        if 'knowledge_pdf' in request.FILES:
            pdf_file = request.FILES['knowledge_pdf']
            agent.knowledge_pdf = pdf_file
            agent.knowledge_pdf_category = request.POST.get("knowledge_pdf_category", "")
            
            try:
                # Extrair texto do PDF automaticamente
                extracted_text = extract_text_from_pdf(pdf_file)
                agent.knowledge_pdf_text = extracted_text
                
                messages.success(request, f"PDF processado com sucesso! {len(extracted_text)} caracteres extraídos.")
            except Exception as e:
                messages.warning(request, f"Erro ao processar PDF: {str(e)}")
            
            agent.save()
        
        AuditLog.log(
            action="create",
            entity="Agent",
            organization=organization,
            actor=request.user,
            entity_id=agent.id,
            diff={"name": name, "slug": agent.slug}
        )
        
        messages.success(request, f"Agente '{name}' criado com sucesso!")
        return redirect("agents:detail", slug=agent.slug)
    
    organizations = Organization.objects.filter(owner=request.user)
    return render(request, "agents/form.html", {"organizations": organizations})


@login_required
def agent_edit(request, slug):
    """Editar agente com formulário simplificado."""
    agent = get_object_or_404(Agent, slug=slug, organization__owner=request.user)
    
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
            
            # DEBUG: Log para verificar condições
            print(f"DEBUG - agent.knowledge_pdf: {agent.knowledge_pdf}")
            print(f"DEBUG - agent.knowledge_pdf_text existe: {bool(agent.knowledge_pdf_text)}")
            print(f"DEBUG - Tamanho do texto: {len(agent.knowledge_pdf_text) if agent.knowledge_pdf_text else 0}")
            
            # Se tem PDF (novo ou existente), enviar para n8n
            if agent.knowledge_pdf and agent.knowledge_pdf_text:
                print("DEBUG - Entrou no bloco de envio para n8n")
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
                        "organization": agent.organization.name,
                        "uploaded_by": request.user.email,
                        "action": "new_upload" if pdf_updated else "update"
                    }
                    
                    print(f"DEBUG - Enviando para webhook: {webhook_url}")
                    print(f"DEBUG - Payload keys: {payload.keys()}")
                    
                    response = requests.post(
                        webhook_url,
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    
                    print(f"DEBUG - Response status: {response.status_code}")
                    print(f"DEBUG - Response body: {response.text[:200]}")
                    
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
                    print(f"DEBUG - Erro no webhook: {webhook_error}")
                    if pdf_updated:
                        messages.success(request, f"PDF atualizado! {len(extracted_text)} caracteres extraídos.")
                    messages.warning(request, f"Erro ao enviar para n8n: {str(webhook_error)}")
            else:
                print(f"DEBUG - NÃO entrou no bloco de envio. PDF: {bool(agent.knowledge_pdf)}, Text: {bool(agent.knowledge_pdf_text)}")
            
            AuditLog.log(
                action="update",
                entity="Agent",
                organization=agent.organization,
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
def agent_edit_old(request, slug):
    """Editar agente - VERSÃO ANTIGA."""
    agent = get_object_or_404(Agent, slug=slug, organization__owner=request.user)
    
    if request.method == "POST":
        agent.name = request.POST.get("name", agent.name)
        agent.role = request.POST.get("role", agent.role)
        agent.sector = request.POST.get("sector", agent.sector)
        agent.language = request.POST.get("language", agent.language)
        agent.status = request.POST.get("status", agent.status)
        agent.personality = request.POST.get("personality", agent.personality)
        agent.greeting = request.POST.get("greeting", agent.greeting)
        agent.out_of_hours_message = request.POST.get("out_of_hours_message", agent.out_of_hours_message)
        agent.transfer_keywords = request.POST.get("transfer_keywords", agent.transfer_keywords)
        agent.max_response_time = int(request.POST.get("max_response_time", agent.max_response_time))
        agent.tone = request.POST.get("tone", agent.tone)
        agent.style_guidelines = request.POST.get("style_guidelines", agent.style_guidelines)
        agent.knowledge_base = request.POST.get("knowledge_base", agent.knowledge_base)
        agent.fallback_message = request.POST.get("fallback_message", agent.fallback_message)
        agent.escalation_rule = request.POST.get("escalation_rule", agent.escalation_rule)
        agent.n8n_webhook_url = request.POST.get("n8n_webhook_url", agent.n8n_webhook_url)
        agent.is_active = request.POST.get("is_active") == "on"
        
        # Processar upload de PDF se houver
        if 'knowledge_pdf' in request.FILES:
            pdf_file = request.FILES['knowledge_pdf']
            agent.knowledge_pdf = pdf_file
            agent.knowledge_pdf_category = request.POST.get("knowledge_pdf_category", agent.knowledge_pdf_category)
            
            try:
                # Extrair texto do PDF automaticamente
                extracted_text = extract_text_from_pdf(pdf_file)
                agent.knowledge_pdf_text = extracted_text
                    
                messages.success(request, f"PDF processado com sucesso! {len(extracted_text)} caracteres extraídos.")
            except Exception as e:
                messages.warning(request, f"Erro ao processar PDF: {str(e)}")
        
        # Atualizar categoria do PDF sem fazer novo upload
        elif request.POST.get("knowledge_pdf_category"):
            agent.knowledge_pdf_category = request.POST.get("knowledge_pdf_category")
        
        agent.save()
        
        AuditLog.log(
            action="update",
            entity="Agent",
            organization=agent.organization,
            actor=request.user,
            entity_id=agent.id,
            diff={"name": agent.name}
        )
        
        messages.success(request, "Agente atualizado com sucesso!")
        return redirect("agents:detail", slug=agent.slug)
    
    return render(request, "agents/form.html", {"agent": agent})


@login_required
def agent_delete(request, slug):
    """Deletar agente."""
    agent = get_object_or_404(Agent, slug=slug, organization__owner=request.user)
    
    if request.method == "POST":
        organization = agent.organization
        agent_name = agent.name
        
        AuditLog.log(
            action="delete",
            entity="Agent",
            organization=organization,
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
    agent = get_object_or_404(Agent, slug=slug, organization__owner=request.user)
    
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
    agent = get_object_or_404(Agent, slug=slug, organization__owner=request.user)
    
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
                organization=agent.organization,
                actor=request.user,
                entity_id=agent.id,
                diff={"agent": agent.name, "action": "PDF deletado"}
            )
            
            messages.success(request, "PDF deletado com sucesso!")
        else:
            messages.warning(request, "Este agente não possui PDF.")
        
        return redirect("agents:detail", slug=agent.slug)
    
    return render(request, "agents/confirm_delete_pdf.html", {"agent": agent})

