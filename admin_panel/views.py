from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Q
from django.core.paginator import Paginator

from core.permissions import require_admin_master, require_system_admin
from organizations.models import Padaria, PadariaUser, ApiKey
from agents.models import Agent
from audit.models import AuditLog


@login_required
@require_system_admin
def dashboard(request):

    """Dashboard do admin master com métricas globais."""
    # Métricas
    total_padarias = Padaria.objects.count()
    padarias_ativas = Padaria.objects.filter(is_active=True).count()
    total_agents = Agent.objects.count()
    agents_ativos = Agent.objects.filter(status='ativo').count()
    total_users = User.objects.filter(is_superuser=False).count()
    
    # Padarias recentes
    padarias_recentes = Padaria.objects.select_related('owner').order_by('-created_at')[:5]
    
    # Agentes recentes
    agents_recentes = Agent.objects.select_related('padaria').order_by('-created_at')[:5]
    
    # Logs recentes
    logs_recentes = AuditLog.objects.select_related('padaria', 'actor').order_by('-created_at')[:10]
    
    # Padarias sem agente
    padarias_sem_agente = Padaria.objects.annotate(
        num_agents=Count('agents')
    ).filter(num_agents=0, is_active=True).count()
    
    context = {
        'total_padarias': total_padarias,
        'padarias_ativas': padarias_ativas,
        'total_agents': total_agents,
        'agents_ativos': agents_ativos,
        'total_users': total_users,
        'padarias_recentes': padarias_recentes,
        'agents_recentes': agents_recentes,
        'logs_recentes': logs_recentes,
        'padarias_sem_agente': padarias_sem_agente,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@require_system_admin
def padarias_list(request):
    """Lista todas as padarias."""
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    padarias = Padaria.objects.select_related('owner').annotate(
        num_agents=Count('agents'),
        num_members=Count('members')
    ).order_by('-created_at')
    
    if search:
        padarias = padarias.filter(
            Q(name__icontains=search) | 
            Q(slug__icontains=search) |
            Q(owner__username__icontains=search)
        )
    
    if status_filter == 'ativas':
        padarias = padarias.filter(is_active=True)
    elif status_filter == 'inativas':
        padarias = padarias.filter(is_active=False)
    elif status_filter == 'sem_agente':
        padarias = padarias.filter(num_agents=0)
    
    # Paginação
    paginator = Paginator(padarias, 20)
    page = request.GET.get('page')
    padarias = paginator.get_page(page)
    
    context = {
        'padarias': padarias,
        'search': search,
        'status_filter': status_filter,
    }
    return render(request, 'admin_panel/padarias_list.html', context)


@login_required
@require_system_admin
def padaria_create(request):
    """Criar nova padaria com usuario dono."""
    if request.method == 'POST':
        # Dados da empresa
        name = request.POST.get('name', '').strip()
        cnpj = request.POST.get('cnpj', '').strip()
        phone = request.POST.get('phone', '').strip()
        company_email = request.POST.get('company_email', '').strip()
        address = request.POST.get('address', '').strip()
        
        # Dados do usuario dono
        owner_name = request.POST.get('owner_name', '').strip()
        owner_email = request.POST.get('owner_email', '').strip()
        owner_password = request.POST.get('owner_password', '').strip()
        
        # Validacoes
        errors = []
        if not name:
            errors.append('O nome da padaria e obrigatorio.')
        if not owner_name:
            errors.append('O nome do usuario dono e obrigatorio.')
        if not owner_email:
            errors.append('O email do usuario dono e obrigatorio.')
        if not owner_password:
            errors.append('A senha do usuario dono e obrigatoria.')
        if len(owner_password) < 6:
            errors.append('A senha deve ter no minimo 6 caracteres.')
        
        # Verificar se email ja existe
        if owner_email and User.objects.filter(email=owner_email).exists():
            errors.append('Ja existe um usuario com este email.')
        
        # Gerar username a partir do email
        username = owner_email.split('@')[0] if owner_email else ''
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('admin_panel:padaria_create')
        
        try:
            # Criar usuario dono
            owner = User.objects.create_user(
                username=username,
                email=owner_email,
                password=owner_password,
                first_name=owner_name.split()[0] if owner_name else '',
                last_name=' '.join(owner_name.split()[1:]) if len(owner_name.split()) > 1 else ''
            )
            
            # Criar padaria
            padaria = Padaria.objects.create(
                name=name,
                owner=owner,
                cnpj=cnpj,
                phone=phone,
                email=company_email,
                address=address
            )
            
            # Criar membership como dono
            PadariaUser.objects.create(
                user=owner,
                padaria=padaria,
                role='dono'
            )
            
            # Criar API Key
            ApiKey.objects.create(
                padaria=padaria,
                name='Chave Principal'
            )
            
            # Log
            AuditLog.log(
                action='create',
                entity='Padaria',
                padaria=padaria,
                actor=request.user,
                entity_id=padaria.id,
                diff={'name': name, 'owner': owner.username, 'cnpj': cnpj}
            )
            
            messages.success(request, f"Padaria '{name}' criada com sucesso! Usuario '{username}' criado.")
            return redirect('admin_panel:padaria_detail', slug=padaria.slug)
            
        except Exception as e:
            messages.error(request, f'Erro ao criar padaria: {str(e)}')
            return redirect('admin_panel:padaria_create')
    
    return render(request, 'admin_panel/padaria_form.html', {})


@login_required
@require_system_admin
def padaria_detail(request, slug):
    """Detalhes de uma padaria."""
    padaria = get_object_or_404(Padaria.objects.select_related('owner'), slug=slug)
    
    # Agente (se existir)
    agent = padaria.agents.first()
    
    # API Keys
    api_keys = padaria.api_keys.order_by('-created_at')
    
    # Logs recentes
    logs = AuditLog.objects.filter(padaria=padaria).order_by('-created_at')[:10]
    
    context = {
        'padaria': padaria,
        'agent': agent,
        'api_keys': api_keys,
        'logs': logs,
    }
    return render(request, 'admin_panel/padaria_detail.html', context)


@login_required
@require_system_admin
def padaria_edit(request, slug):
    """Editar padaria."""
    padaria = get_object_or_404(Padaria, slug=slug)
    
    if request.method == 'POST':
        padaria.name = request.POST.get('name', padaria.name).strip()
        padaria.phone = request.POST.get('phone', '').strip()
        padaria.email = request.POST.get('email', '').strip()
        padaria.address = request.POST.get('address', '').strip()
        padaria.is_active = request.POST.get('is_active') == 'on'
        
        owner_id = request.POST.get('owner')
        if owner_id:
            try:
                new_owner = User.objects.get(id=owner_id)
                if new_owner != padaria.owner:
                    old_owner = padaria.owner
                    padaria.owner = new_owner
                    
                    # Atualizar memberships
                    PadariaUser.objects.filter(user=old_owner, padaria=padaria).delete()
                    PadariaUser.objects.get_or_create(
                        user=new_owner, 
                        padaria=padaria,
                        defaults={'role': 'dono'}
                    )
            except User.DoesNotExist:
                pass
        
        padaria.save()
        
        AuditLog.log(
            action='update',
            entity='Padaria',
            padaria=padaria,
            actor=request.user,
            entity_id=padaria.id,
            diff={'name': padaria.name}
        )
        
        messages.success(request, 'Padaria atualizada com sucesso!')
        return redirect('admin_panel:padaria_detail', slug=padaria.slug)
    
    users = User.objects.filter(is_superuser=False).order_by('username')
    
    context = {
        'padaria': padaria,
        'users': users,
        'is_edit': True,
    }
    return render(request, 'admin_panel/padaria_form.html', context)


@login_required
@require_admin_master
def padaria_delete(request, slug):
    """Deletar padaria."""
    padaria = get_object_or_404(Padaria, slug=slug)
    
    if request.method == 'POST':
        name = padaria.name
        
        AuditLog.log(
            action='delete',
            entity='Padaria',
            actor=request.user,
            entity_id=padaria.id,
            diff={'name': name, 'slug': slug}
        )
        
        padaria.delete()
        messages.success(request, f"Padaria '{name}' deletada com sucesso!")
        return redirect('admin_panel:padarias_list')
    
    context = {
        'padaria': padaria,
    }
    return render(request, 'admin_panel/padaria_confirm_delete.html', context)


@login_required
@require_system_admin
def padaria_members(request, slug):
    """Gerenciar membros da padaria."""
    padaria = get_object_or_404(Padaria, slug=slug)
    members = padaria.members.select_related('user').order_by('-role', 'user__username')
    
    context = {
        'padaria': padaria,
        'members': members,
    }
    return render(request, 'admin_panel/padaria_members.html', context)


@login_required
@require_system_admin
def padaria_member_add(request, slug):
    """Adicionar membro à padaria."""
    padaria = get_object_or_404(Padaria, slug=slug)
    
    if request.method == 'POST':
        user_id = request.POST.get('user')
        role = request.POST.get('role', 'funcionario')
        
        try:
            user = User.objects.get(id=user_id)
            
            # Verificar se já é membro
            if PadariaUser.objects.filter(user=user, padaria=padaria).exists():
                messages.warning(request, f'{user.username} já é membro desta padaria.')
            else:
                PadariaUser.objects.create(
                    user=user,
                    padaria=padaria,
                    role=role
                )
                messages.success(request, f'{user.username} adicionado como {role}!')
                
                AuditLog.log(
                    action='add_member',
                    entity='PadariaUser',
                    padaria=padaria,
                    actor=request.user,
                    entity_id=user.id,
                    diff={'user': user.username, 'role': role}
                )
        except User.DoesNotExist:
            messages.error(request, 'Usuário não encontrado.')
        
        return redirect('admin_panel:padaria_members', slug=slug)
    
    # Usuários que não são membros ainda
    existing_members = padaria.members.values_list('user_id', flat=True)
    available_users = User.objects.filter(is_superuser=False).exclude(id__in=existing_members)
    
    context = {
        'padaria': padaria,
        'available_users': available_users,
    }
    return render(request, 'admin_panel/padaria_member_add.html', context)


@login_required
@require_system_admin
def padaria_member_remove(request, slug, member_id):
    """Remover membro da padaria."""
    padaria = get_object_or_404(Padaria, slug=slug)
    membership = get_object_or_404(PadariaUser, id=member_id, padaria=padaria)
    
    if request.method == 'POST':
        username = membership.user.username
        
        # Não permitir remover o dono principal
        if membership.user == padaria.owner and membership.role == 'dono':
            messages.error(request, 'Não é possível remover o proprietário principal.')
            return redirect('admin_panel:padaria_members', slug=slug)
        
        AuditLog.log(
            action='remove_member',
            entity='PadariaUser',
            padaria=padaria,
            actor=request.user,
            entity_id=membership.user.id,
            diff={'user': username}
        )
        
        membership.delete()
        messages.success(request, f'{username} removido da padaria.')
        return redirect('admin_panel:padaria_members', slug=slug)
    
    context = {
        'padaria': padaria,
        'membership': membership,
    }
    return render(request, 'admin_panel/padaria_member_confirm_remove.html', context)


@login_required
@require_system_admin
def agents_list(request):
    """Lista global de todos os agentes."""
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    agents = Agent.objects.select_related('padaria').order_by('-created_at')
    
    if search:
        agents = agents.filter(
            Q(name__icontains=search) |
            Q(slug__icontains=search) |
            Q(padaria__name__icontains=search)
        )
    
    if status_filter:
        agents = agents.filter(status=status_filter)
    
    # Paginação
    paginator = Paginator(agents, 20)
    page = request.GET.get('page')
    agents = paginator.get_page(page)
    
    context = {
        'agents': agents,
        'search': search,
        'status_filter': status_filter,
    }
    return render(request, 'admin_panel/agents_list.html', context)


@login_required
@require_system_admin
def agent_detail(request, slug):
    """Detalhes de um agente (visão admin)."""
    agent = get_object_or_404(Agent.objects.select_related('padaria'), slug=slug)
    
    context = {
        'agent': agent,
    }
    return render(request, 'admin_panel/agent_detail.html', context)


@login_required
@require_system_admin
def padaria_apikey(request, slug):
    """Gerenciar API Keys da padaria."""
    padaria = get_object_or_404(Padaria, slug=slug)
    api_keys = padaria.api_keys.order_by('-created_at')
    
    context = {
        'padaria': padaria,
        'api_keys': api_keys,
    }
    return render(request, 'admin_panel/padaria_apikey.html', context)


@login_required
@require_system_admin
def padaria_apikey_generate(request, slug):
    """Gerar nova API Key para a padaria."""
    padaria = get_object_or_404(Padaria, slug=slug)
    
    if request.method == 'POST':
        name = request.POST.get('name', 'Nova Chave').strip()
        
        api_key = ApiKey.objects.create(
            padaria=padaria,
            name=name
        )
        
        AuditLog.log(
            action='create_apikey',
            entity='ApiKey',
            padaria=padaria,
            actor=request.user,
            entity_id=api_key.id,
            diff={'name': name}
        )
        
        messages.success(request, f'Nova API Key gerada! Chave: {api_key.key}')
        return redirect('admin_panel:padaria_apikey', slug=slug)
    
    return redirect('admin_panel:padaria_apikey', slug=slug)


@login_required
@require_admin_master
def users_list(request):
    """Lista todos os usuarios do sistema."""
    search = request.GET.get('search', '')
    
    users = User.objects.filter(is_superuser=False).order_by('username')
    
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Paginacao
    paginator = Paginator(users, 20)
    page = request.GET.get('page')
    users = paginator.get_page(page)
    
    context = {
        'users': users,
        'search': search,
    }
    return render(request, 'admin_panel/users_list.html', context)


@login_required
@require_admin_master
def user_create(request):
    """Criar novo usuario."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', 'user')
        
        if not username:
            messages.error(request, 'O nome de usuario e obrigatorio.')
            return redirect('admin_panel:user_create')
        
        if not password:
            messages.error(request, 'A senha e obrigatoria.')
            return redirect('admin_panel:user_create')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Este nome de usuario ja existe.')
            return redirect('admin_panel:user_create')
        
        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'Este email ja esta em uso.')
            return redirect('admin_panel:user_create')
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Atribuir papel
        if hasattr(user, 'profile'):
            user.profile.role = role
            user.profile.save()
        
        AuditLog.log(
            action='create',
            entity='User',
            actor=request.user,
            entity_id=user.id,
            diff={'username': username, 'email': email, 'role': role}
        )
        
        messages.success(request, f"Usuario '{username}' criado com sucesso!")
        return redirect('admin_panel:users_list')
    
    return render(request, 'admin_panel/user_form.html', {'is_edit': False})


@login_required
@require_admin_master
def user_edit(request, user_id):
    """Editar usuario."""
    user_obj = get_object_or_404(User, id=user_id, is_superuser=False)
    
    if request.method == 'POST':
        user_obj.email = request.POST.get('email', '').strip()
        user_obj.first_name = request.POST.get('first_name', '').strip()
        user_obj.last_name = request.POST.get('last_name', '').strip()
        user_obj.is_active = request.POST.get('is_active') == 'on'
        
        role = request.POST.get('role')
        if role and hasattr(user_obj, 'profile'):
            user_obj.profile.role = role
            user_obj.profile.save()
        
        new_password = request.POST.get('password', '')
        if new_password:
            user_obj.set_password(new_password)
        
        user_obj.save()
        
        AuditLog.log(
            action='update',
            entity='User',
            actor=request.user,
            entity_id=user_obj.id,
            diff={'username': user_obj.username, 'role': role}
        )
        
        messages.success(request, f"Usuario '{user_obj.username}' atualizado!")
        return redirect('admin_panel:users_list')
    
    context = {
        'user_obj': user_obj,
        'is_edit': True,
    }
    return render(request, 'admin_panel/user_form.html', context)


@login_required
@require_admin_master
def user_delete(request, user_id):
    """Deletar usuario."""
    user_obj = get_object_or_404(User, id=user_id, is_superuser=False)
    
    if request.method == 'POST':
        username = user_obj.username
        
        AuditLog.log(
            action='delete',
            entity='User',
            actor=request.user,
            entity_id=user_obj.id,
            diff={'username': username}
        )
        
        user_obj.delete()
        messages.success(request, f"Usuario '{username}' deletado!")
        return redirect('admin_panel:users_list')
    
    context = {
        'user_obj': user_obj,
    }
    return render(request, 'admin_panel/user_confirm_delete.html', context)
