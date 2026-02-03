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
        
        # Validação de UF: CNPJ da padaria deve ser da mesma UF do CEP do admin
        admin_cep = None
        if hasattr(request.user, 'profile') and request.user.profile.cep:
            admin_cep = request.user.profile.cep
        
        if cnpj and admin_cep:
            from core.uf_validator import validate_same_uf
            
            try:
                uf_result = validate_same_uf(cnpj, admin_cep)
                
                if uf_result.get('error'):
                    # Erro na validação (API indisponível, formato inválido, etc)
                    messages.warning(
                        request, 
                        f"Aviso: Não foi possível validar a região do CNPJ. {uf_result['error']}"
                    )
                elif not uf_result.get('valid'):
                    # UFs diferentes - bloquear criação
                    errors.append(
                        f"O CNPJ pertence ao estado {uf_result['cnpj_uf']}, "
                        f"mas sua região de atuação é {uf_result['cep_uf']}. "
                        f"Você só pode criar padarias na sua região."
                    )
            except Exception as e:
                # Em caso de erro inesperado, apenas avisa mas não bloqueia
                messages.warning(request, f"Aviso: Erro ao validar região do CNPJ: {str(e)}")
        elif cnpj and not admin_cep:
            # Admin não tem CEP cadastrado - apenas avisa
            messages.warning(
                request, 
                "Aviso: Seu CEP não está cadastrado. "
                "A validação de região foi ignorada. "
                "Recomendamos que atualize seu perfil."
            )
        
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
        cep = request.POST.get('cep', '').strip()
        
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
        
        # Atribuir papel e CEP (para admins)
        if hasattr(user, 'profile'):
            user.profile.role = role
            if role == 'admin' and cep:
                user.profile.cep = cep
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
        cep = request.POST.get('cep', '').strip()
        
        if role and hasattr(user_obj, 'profile'):
            user_obj.profile.role = role
            # Salvar CEP apenas para admins
            if role == 'admin':
                user_obj.profile.cep = cep if cep else None
            else:
                user_obj.profile.cep = None  # Limpar CEP se não for admin
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


@login_required
@require_system_admin
def clientes_report(request):
    """Relatório completo de controle de clientes (padarias)."""
    from datetime import datetime, timedelta
    from django.db.models import Count, Sum, Q, Max
    from organizations.models import Produto, Promocao, Cliente, CampanhaWhatsApp
    from payments.models import AsaasSubscription
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    
    # Filtros
    status_filter = request.GET.get('status', '')
    whatsapp_filter = request.GET.get('whatsapp', '')
    subscription_filter = request.GET.get('subscription', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    # Query base
    padarias = Padaria.objects.select_related('owner').annotate(
        num_agents=Count('agents', distinct=True),
        num_users=Count('members', distinct=True),
        num_produtos=Count('produtos', distinct=True),
        num_promocoes=Count('promocoes', distinct=True),
        num_clientes=Count('clientes', distinct=True),
        num_campanhas=Count('campanhas', distinct=True),
        ultima_atividade=Max('audit_logs__created_at')
    )
    
    # Aplicar filtros
    if status_filter == 'ativas':
        padarias = padarias.filter(is_active=True)
    elif status_filter == 'inativas':
        padarias = padarias.filter(is_active=False)
    
    if whatsapp_filter == 'conectado':
        # Padarias com pelo menos 1 agente ativo
        padarias = padarias.filter(num_agents__gt=0)
    elif whatsapp_filter == 'desconectado':
        padarias = padarias.filter(num_agents=0)
    
    if subscription_filter == 'ativa':
        # Padarias com subscription ativa
        active_subs = AsaasSubscription.objects.filter(
            status__in=['ACTIVE', 'active']
        ).values_list('padaria_id', flat=True)
        padarias = padarias.filter(id__in=active_subs)
    elif subscription_filter == 'inativa':
        active_subs = AsaasSubscription.objects.filter(
            status__in=['ACTIVE', 'active']
        ).values_list('padaria_id', flat=True)
        padarias = padarias.exclude(id__in=active_subs)
    
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            padarias = padarias.filter(created_at__gte=date_from_dt)
        except:
            pass
    
    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
            padarias = padarias.filter(created_at__lte=date_to_dt)
        except:
            pass
    
    if search:
        padarias = padarias.filter(
            Q(name__icontains=search) |
            Q(slug__icontains=search) |
            Q(owner__username__icontains=search) |
            Q(owner__email__icontains=search)
        )
    
    # Métricas Gerais
    total_padarias = padarias.count()
    padarias_ativas = padarias.filter(is_active=True).count()
    padarias_inativas = padarias.filter(is_active=False).count()
    
    total_agentes = Agent.objects.filter(padaria__in=padarias).count()
    total_usuarios = PadariaUser.objects.filter(padaria__in=padarias).count()
    total_produtos = Produto.objects.filter(padaria__in=padarias).count()
    total_clientes = Cliente.objects.filter(padaria__in=padarias).count()
    
    # Padarias com WhatsApp conectado (com agentes)
    padarias_com_whatsapp = padarias.filter(num_agents__gt=0).count()
    
    # Padarias com assinatura ativa
    active_subs = AsaasSubscription.objects.filter(
        status__in=['ACTIVE', 'active']
    ).values_list('padaria_id', flat=True)
    padarias_com_sub_ativa = padarias.filter(id__in=active_subs).count()
    
    # Crescimento (últimos 30 dias)
    trinta_dias_atras = datetime.now() - timedelta(days=30)
    novas_padarias_30d = Padaria.objects.filter(
        created_at__gte=trinta_dias_atras
    ).count()
    
    # Gráfico de cadastros por mês (últimos 6 meses)
    from collections import defaultdict
    seis_meses_atras = datetime.now() - timedelta(days=180)
    cadastros_por_mes = defaultdict(int)
    
    for padaria in Padaria.objects.filter(created_at__gte=seis_meses_atras):
        mes_ano = padaria.created_at.strftime('%Y-%m')
        cadastros_por_mes[mes_ano] += 1
    
    meses_labels = sorted(cadastros_por_mes.keys())
    cadastros_data = [cadastros_por_mes[m] for m in meses_labels]
    
    # Formatar labels para português
    meses_labels_pt = []
    for m in meses_labels:
        try:
            dt = datetime.strptime(m, '%Y-%m')
            meses_labels_pt.append(dt.strftime('%b/%y'))
        except:
            meses_labels_pt.append(m)
    
    # Distribuição por status de assinatura
    subs_status = AsaasSubscription.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    sub_labels = [s['status'] for s in subs_status]
    sub_data = [s['count'] for s in subs_status]
    
    # Ordenar padarias por data de criação (mais recentes primeiro)
    padarias_list = padarias.order_by('-created_at')
    
    # Paginação
    paginator = Paginator(padarias_list, 25)
    page = request.GET.get('page')
    padarias_page = paginator.get_page(page)
    
    # Adicionar informação de subscription para cada padaria
    subs_dict = {}
    for sub in AsaasSubscription.objects.filter(padaria__in=padarias_list).select_related('padaria'):
        subs_dict[sub.padaria_id] = sub
    
    for padaria in padarias_page:
        padaria.subscription = subs_dict.get(padaria.id, None)
    
    context = {
        'total_padarias': total_padarias,
        'padarias_ativas': padarias_ativas,
        'padarias_inativas': padarias_inativas,
        'total_agentes': total_agentes,
        'total_usuarios': total_usuarios,
        'total_produtos': total_produtos,
        'total_clientes': total_clientes,
        'padarias_com_whatsapp': padarias_com_whatsapp,
        'padarias_com_sub_ativa': padarias_com_sub_ativa,
        'novas_padarias_30d': novas_padarias_30d,
        'padarias': padarias_page,
        # Gráficos
        'meses_labels': json.dumps(meses_labels_pt, cls=DjangoJSONEncoder),
        'cadastros_data': json.dumps(cadastros_data, cls=DjangoJSONEncoder),
        'sub_labels': json.dumps(sub_labels, cls=DjangoJSONEncoder),
        'sub_data': json.dumps(sub_data, cls=DjangoJSONEncoder),
        # Filtros
        'status_filter': status_filter,
        'whatsapp_filter': whatsapp_filter,
        'subscription_filter': subscription_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
    }
    
    return render(request, 'admin_panel/clientes_report.html', context)


@login_required
@require_system_admin
def clientes_export_excel(request):
    """Exportar relatório de clientes para Excel."""
    from datetime import datetime, timedelta
    from django.db.models import Count, Q, Max
    from django.http import HttpResponse
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from organizations.models import Produto, Promocao, Cliente, CampanhaWhatsApp
    from payments.models import AsaasSubscription
    
    # Aplicar os mesmos filtros da view principal
    status_filter = request.GET.get('status', '')
    whatsapp_filter = request.GET.get('whatsapp', '')
    subscription_filter = request.GET.get('subscription', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    # Query base
    padarias = Padaria.objects.select_related('owner').annotate(
        num_agents=Count('agents', distinct=True),
        num_users=Count('members', distinct=True),
        num_produtos=Count('produtos', distinct=True),
        num_promocoes=Count('promocoes', distinct=True),
        num_clientes=Count('clientes', distinct=True),
        num_campanhas=Count('campanhas', distinct=True),
        ultima_atividade=Max('audit_logs__created_at')
    )
    
    # Aplicar filtros
    if status_filter == 'ativas':
        padarias = padarias.filter(is_active=True)
    elif status_filter == 'inativas':
        padarias = padarias.filter(is_active=False)
    
    if whatsapp_filter == 'conectado':
        padarias = padarias.filter(num_agents__gt=0)
    elif whatsapp_filter == 'desconectado':
        padarias = padarias.filter(num_agents=0)
    
    if subscription_filter == 'ativa':
        active_subs = AsaasSubscription.objects.filter(
            status__in=['ACTIVE', 'active']
        ).values_list('padaria_id', flat=True)
        padarias = padarias.filter(id__in=active_subs)
    elif subscription_filter == 'inativa':
        active_subs = AsaasSubscription.objects.filter(
            status__in=['ACTIVE', 'active']
        ).values_list('padaria_id', flat=True)
        padarias = padarias.exclude(id__in=active_subs)
    
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            padarias = padarias.filter(created_at__gte=date_from_dt)
        except:
            pass
    
    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
            padarias = padarias.filter(created_at__lte=date_to_dt)
        except:
            pass
    
    if search:
        padarias = padarias.filter(
            Q(name__icontains=search) |
            Q(slug__icontains=search) |
            Q(owner__username__icontains=search) |
            Q(owner__email__icontains=search)
        )
    
    # Buscar assinaturas
    subs_dict = {}
    for sub in AsaasSubscription.objects.filter(padaria__in=padarias).select_related('padaria'):
        subs_dict[sub.padaria_id] = sub
    
    # Criar Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório de Clientes"
    
    # Estilos
    header_fill = PatternFill(start_color="667EEA", end_color="667EEA", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Cabeçalhos
    headers = [
        'Nome', 'Slug', 'CNPJ', 'Responsável', 'Email Responsável', 
        'Status', 'WhatsApp Conectado', 'Status Assinatura', 
        'Qtd. Agentes', 'Qtd. Usuários', 'Qtd. Produtos', 
        'Qtd. Promoções', 'Qtd. Clientes', 'Qtd. Campanhas',
        'Data Cadastro', 'Última Atividade', 'Telefone', 'Endereço'
    ]
    
    # Adicionar título
    ws.merge_cells('A1:R1')
    ws['A1'] = 'RELATÓRIO DE CONTROLE DE CLIENTES (PADARIAS)'
    ws['A1'].font = Font(bold=True, size=16, color="667EEA")
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    
    # Adicionar info de geração
    ws.merge_cells('A2:R2')
    ws['A2'] = f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")} - Total: {padarias.count()} clientes'
    ws['A2'].font = Font(size=10, italic=True)
    ws['A2'].alignment = Alignment(horizontal='center')
    
    # Cabeçalhos na linha 4
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Dados
    row_num = 5
    for padaria in padarias.order_by('name'):
        subscription = subs_dict.get(padaria.id, None)
        
        # Status da assinatura
        if subscription:
            if subscription.status in ['ACTIVE', 'active']:
                sub_status = 'Ativa'
            elif subscription.status in ['TRIAL', 'trialing']:
                sub_status = 'Trial'
            elif subscription.status == 'OVERDUE':
                sub_status = 'Vencida'
            elif subscription.status == 'EXPIRED':
                sub_status = 'Expirada'
            else:
                sub_status = subscription.status
        else:
            sub_status = 'Sem assinatura'
        
        # Dados da linha
        row_data = [
            padaria.name,
            padaria.slug,
            padaria.cnpj or '-',
            padaria.owner.username,
            padaria.owner.email,
            'Ativa' if padaria.is_active else 'Inativa',
            'Sim' if padaria.num_agents > 0 else 'Não',
            sub_status,
            padaria.num_agents,
            padaria.num_users,
            padaria.num_produtos,
            padaria.num_promocoes,
            padaria.num_clientes,
            padaria.num_campanhas,
            padaria.created_at.strftime('%d/%m/%Y') if padaria.created_at else '-',
            padaria.ultima_atividade.strftime('%d/%m/%Y %H:%M') if padaria.ultima_atividade else '-',
            padaria.phone or '-',
            padaria.address or '-'
        ]
        
        for col_num, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.value = value
            cell.border = border
            cell.alignment = Alignment(horizontal='left', vertical='center')
            
            # Colorir status
            if col_num == 6:  # Status
                if value == 'Ativa':
                    cell.fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
                else:
                    cell.fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
            elif col_num == 7:  # WhatsApp
                if value == 'Sim':
                    cell.fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
        
        row_num += 1
    
    # Ajustar largura das colunas
    from openpyxl.utils import get_column_letter
    column_widths = [25, 20, 18, 20, 30, 12, 18, 18, 12, 12, 12, 12, 12, 12, 15, 18, 15, 30]
    for col_num, width in enumerate(column_widths, 1):
        col_letter = get_column_letter(col_num)
        ws.column_dimensions[col_letter].width = width
    
    # Ajustar altura das linhas
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[4].height = 25
    
    # Preparar resposta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'relatorio_clientes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response

