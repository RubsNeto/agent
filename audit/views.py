from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import AuditLog


@login_required
def audit_log_list(request):
    """Lista de logs de auditoria - apenas para desenvolvedores/superusers."""
    # Verificar se é superuser (desenvolvedor)
    if not request.user.is_superuser:
        messages.error(request, "Acesso restrito. Apenas desenvolvedores podem acessar os logs de auditoria.")
        return redirect('ui:dashboard')
    
    logs = AuditLog.objects.all().select_related('padaria', 'actor').order_by('-created_at')[:100]  # Últimos 100 logs
    
    return render(request, "audit/list.html", {"logs": logs})

