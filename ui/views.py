from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from organizations.models import Padaria, PadariaUser, ApiKey
from agents.models import Agent
from audit.models import AuditLog
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta


@login_required
def guia(request):
    """Guia de implementação do sistema."""
    return render(request, "ui/guia.html")


@login_required
def welcome(request):
    """Tela de boas-vindas após login."""
    user = request.user
    
    # Pegar perfil do usuário
    profile = getattr(user, 'profile', None)
    user_role = profile.role if profile else 'user'
    
    # Buscar padaria do usuário (onde é membro)
    padaria = None
    agente = None
    
    if not user.is_superuser:
        user_membership = PadariaUser.objects.filter(user=user).first()
        if user_membership:
            padaria = user_membership.padaria
            agente = padaria.agents.first() if padaria else None
    
    context = {
        'user': user,
        'profile': profile,
        'user_role': user_role,
        'padaria': padaria,
        'agente': agente,
    }
    
    return render(request, "ui/welcome.html", context)


@login_required
def dashboard(request):
    """Dashboard principal."""
    user = request.user
    
    # Buscar padarias do usuário (onde é membro ou dono)
    if user.is_superuser:
        padarias = Padaria.objects.all()
        agents = Agent.objects.all()
        logs = AuditLog.objects.all().order_by("-created_at")[:10]
        api_keys = ApiKey.objects.all()
    else:
        # Padarias onde o usuário é membro
        user_padaria_ids = PadariaUser.objects.filter(user=user).values_list('padaria_id', flat=True)
        padarias = Padaria.objects.filter(id__in=user_padaria_ids)
        
        # Agentes das padarias do usuário
        agents = Agent.objects.filter(padaria__in=padarias)
        
        # API Keys do usuário
        api_keys = ApiKey.objects.filter(padaria__in=padarias)
        
        # Logs recentes das padarias do usuário
        logs = AuditLog.objects.filter(padaria__in=padarias).order_by("-created_at")[:10]
    
    # Estatísticas para clientes
    hoje = timezone.now()
    dias_30 = hoje - timedelta(days=30)
    dias_7 = hoje - timedelta(days=7)
    
    # Atividade nos últimos 30 dias
    atividade_30_dias = AuditLog.objects.filter(
        padaria__in=padarias,
        created_at__gte=dias_30
    ).count()
    
    # Atividade nos últimos 7 dias
    atividade_7_dias = AuditLog.objects.filter(
        padaria__in=padarias,
        created_at__gte=dias_7
    ).count()
    
    # Chamadas de API nos últimos 30 dias
    api_calls_30_dias = AuditLog.objects.filter(
        padaria__in=padarias,
        created_at__gte=dias_30,
        action='api_call'
    ).count()
    
    # Gráfico de atividade por dia (últimos 7 dias)
    atividade_diaria = []
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        dia_inicio = dia.replace(hour=0, minute=0, second=0, microsecond=0)
        dia_fim = dia_inicio + timedelta(days=1)
        
        count = AuditLog.objects.filter(
            padaria__in=padarias,
            created_at__gte=dia_inicio,
            created_at__lt=dia_fim
        ).count()
        
        atividade_diaria.append({
            'dia': dia.strftime('%d/%m'),
            'count': count
        })
    
    # Ações mais frequentes
    acoes_frequentes = AuditLog.objects.filter(
        padaria__in=padarias,
        created_at__gte=dias_30
    ).values('action').annotate(
        total=Count('id')
    ).order_by('-total')[:5]
    
    # Status do agente (se existe)
    agente = agents.first() if agents.exists() else None
    
    context = {
        "organizations": padarias,
        "padarias": padarias,
        "agents": agents,
        "agente": agente,
        "logs": logs,
        "api_keys": api_keys,
        "api_keys_count": api_keys.count(),
        "atividade_30_dias": atividade_30_dias,
        "atividade_7_dias": atividade_7_dias,
        "api_calls_30_dias": api_calls_30_dias,
        "atividade_diaria": atividade_diaria,
        "acoes_frequentes": acoes_frequentes,
    }
    
    return render(request, "ui/dashboard.html", context)
