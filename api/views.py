from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from agents.models import Agent
from audit.models import AuditLog
from core.utils import require_api_key, rate_limited, get_client_ip


@require_http_methods(["GET"])
@require_api_key
def get_agent_config(request, slug):
    """
    Retorna configuração de um agente para o n8n.
    Requer autenticação via API key.
    """
    # Rate limiting
    org = request.api_key.organization
    cache_key = f"api_rate_{org.id}_{get_client_ip(request)}"
    
    if not rate_limited(cache_key, limit=60, window_seconds=60):
        return JsonResponse({"error": "Rate limit exceeded"}, status=429)
    
    # Buscar agente
    try:
        agent = Agent.objects.get(slug=slug, organization=org, is_active=True)
    except Agent.DoesNotExist:
        return JsonResponse({"error": "Agent not found"}, status=404)
    
    # Log da requisição
    AuditLog.log(
        action="api_call",
        entity="Agent",
        organization=org,
        entity_id=agent.id,
        diff={
            "endpoint": "get_agent_config",
            "slug": slug
        },
        ip=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")
    )
    
    # Atualizar last_used_at da API key
    from django.utils import timezone
    request.api_key.last_used_at = timezone.now()
    request.api_key.save(update_fields=["last_used_at"])
    
    # Retornar configuração
    config = {
        "name": agent.name,
        "slug": agent.slug,
        "role": agent.role,
        "sector": agent.sector,
        "language": agent.language,
        "greeting": agent.greeting,
        "tone": agent.tone,
        "style_guidelines": agent.style_guidelines,
        "business_hours": agent.business_hours,
        "knowledge_base": agent.knowledge_base,
        "fallback_message": agent.fallback_message,
        "escalation_rule": agent.escalation_rule,
    }
    
    return JsonResponse(config)
