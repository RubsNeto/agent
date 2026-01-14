"""
Sistema de permissões para o SaaS de Padarias.
Inclui decorators e helpers para controle de acesso.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden


def is_admin_master(user):
    """Verifica se o usuário é um admin master (superuser)."""
    return user.is_authenticated and user.is_superuser


def is_system_admin(user):
    """
    Verifica se o usuário é um admin do sistema.
    Pode ser Superuser ou ter perfil com role='admin'.
    """
    if not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
        
    try:
        return hasattr(user, 'profile') and user.profile.role == 'admin'
    except Exception:
        return False


def get_user_padaria(user):
    """
    Retorna a padaria do usuário.
    Prioriza padarias onde é dono, depois funcionário.
    Retorna None se não estiver vinculado a nenhuma.
    """
    if not user.is_authenticated:
        return None
    
    # Primeiro, verificar se é dono de alguma padaria
    from organizations.models import PadariaUser
    membership = PadariaUser.objects.filter(
        user=user
    ).select_related('padaria').order_by(
        # Dono tem prioridade
        '-role'  # 'dono' vem antes de 'funcionario' alfabeticamente invertido
    ).first()
    
    if membership:
        return membership.padaria
    
    # Fallback: verificar se é owner direto (compatibilidade)
    from organizations.models import Padaria
    return Padaria.objects.filter(owner=user).first()


def get_user_role(user, padaria=None):
    """
    Retorna o papel do usuário na padaria.
    Retorna 'admin_master' se for superuser.
    Retorna None se não tiver acesso.
    """
    if not user.is_authenticated:
        return None
    
    if user.is_superuser:
        return 'admin_master'
    
    if padaria is None:
        padaria = get_user_padaria(user)
    
    if padaria is None:
        return None
    
    from organizations.models import PadariaUser
    try:
        membership = PadariaUser.objects.get(user=user, padaria=padaria)
        return membership.role
    except PadariaUser.DoesNotExist:
        # Verificar se é owner direto
        if padaria.owner == user:
            return 'dono'
        return None


def has_padaria_access(user, padaria):
    """Verifica se o usuário tem acesso à padaria."""
    if user.is_superuser:
        return True
    
    role = get_user_role(user, padaria)
    return role is not None


def require_admin_master(view_func):
    """
    Decorator que exige que o usuário seja admin master (superuser).
    Redireciona para o dashboard com mensagem de erro se não for.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not is_admin_master(request.user):
            messages.error(request, "Acesso restrito a administradores.")
            return redirect('ui:dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_system_admin(view_func):
    """
    Decorator que exige que o usuário seja admin do sistema (Role=Admin ou Superuser).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not is_system_admin(request.user):
            messages.error(request, "Acesso restrito a administradores do sistema.")
            return redirect('ui:dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_padaria_access(view_func):
    """
    Decorator que verifica se o usuário tem acesso à padaria.
    Espera que a view tenha um parâmetro 'slug' da padaria.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        slug = kwargs.get('slug') or kwargs.get('padaria_slug')
        
        if slug:
            from organizations.models import Padaria
            try:
                padaria = Padaria.objects.get(slug=slug)
                if not has_padaria_access(request.user, padaria):
                    messages.error(request, "Você não tem acesso a esta padaria.")
                    return redirect('ui:dashboard')
                # Anexar padaria ao request para uso na view
                request.padaria = padaria
                request.user_role = get_user_role(request.user, padaria)
            except Padaria.DoesNotExist:
                messages.error(request, "Padaria não encontrada.")
                return redirect('ui:dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_role(allowed_roles):
    """
    Decorator factory que exige um papel específico.
    
    Uso:
        @require_role(['dono'])
        def my_view(request):
            ...
        
        @require_role(['dono', 'admin_master'])
        def another_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            # Admin master sempre tem acesso
            if request.user.is_superuser and 'admin_master' not in allowed_roles:
                # Se admin_master não está na lista, verificar se foi explicitamente excluído
                pass  # Continua para verificar
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Obter role do usuário
            slug = kwargs.get('slug') or kwargs.get('padaria_slug')
            padaria = None
            
            if slug:
                from organizations.models import Padaria
                try:
                    padaria = Padaria.objects.get(slug=slug)
                except Padaria.DoesNotExist:
                    messages.error(request, "Padaria não encontrada.")
                    return redirect('ui:dashboard')
            
            user_role = get_user_role(request.user, padaria)
            
            if user_role not in allowed_roles:
                messages.error(request, "Você não tem permissão para esta ação.")
                return redirect('ui:dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def get_user_context(user):
    """
    Retorna um dicionário com contexto do usuário para templates.
    """
    context = {
        'is_admin_master': is_admin_master(user),
        'user_padaria': None,
        'user_role': None,
        'user_role_display': None,
    }
    
    if user.is_authenticated:
        if user.is_superuser:
            context['user_role'] = 'admin_master'
            context['user_role_display'] = 'Administrador Master'
        else:
            padaria = get_user_padaria(user)
            if padaria:
                context['user_padaria'] = padaria
                role = get_user_role(user, padaria)
                context['user_role'] = role
                context['user_role_display'] = {
                    'dono': 'Dono',
                    'funcionario': 'Funcionário'
                }.get(role, role)
    
    return context
