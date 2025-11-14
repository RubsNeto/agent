from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Agent
from organizations.models import Organization
from audit.models import AuditLog


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
    """Criar novo agente."""
    if request.method == "POST":
        org_id = request.POST.get("organization")
        name = request.POST.get("name")
        role = request.POST.get("role", "atendente")
        sector = request.POST.get("sector", "manicure/pedicure")
        
        organization = get_object_or_404(Organization, id=org_id, owner=request.user)
        
        agent = Agent.objects.create(
            organization=organization,
            name=name,
            role=role,
            sector=sector,
            greeting=request.POST.get("greeting", ""),
            tone=request.POST.get("tone", ""),
            style_guidelines=request.POST.get("style_guidelines", ""),
            knowledge_base=request.POST.get("knowledge_base", ""),
            fallback_message=request.POST.get("fallback_message", ""),
            escalation_rule=request.POST.get("escalation_rule", ""),
        )
        
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
    """Editar agente."""
    agent = get_object_or_404(Agent, slug=slug, organization__owner=request.user)
    
    if request.method == "POST":
        agent.name = request.POST.get("name", agent.name)
        agent.role = request.POST.get("role", agent.role)
        agent.sector = request.POST.get("sector", agent.sector)
        agent.greeting = request.POST.get("greeting", agent.greeting)
        agent.tone = request.POST.get("tone", agent.tone)
        agent.style_guidelines = request.POST.get("style_guidelines", agent.style_guidelines)
        agent.knowledge_base = request.POST.get("knowledge_base", agent.knowledge_base)
        agent.fallback_message = request.POST.get("fallback_message", agent.fallback_message)
        agent.escalation_rule = request.POST.get("escalation_rule", agent.escalation_rule)
        agent.is_active = request.POST.get("is_active") == "on"
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
