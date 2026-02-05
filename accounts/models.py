from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """
    Perfil estendido do usuário.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    
    ROLE_CHOICES = [
        ('admin', 'Administrador do Sistema'),
        ('agente_credenciado', 'Agente Credenciado'),
        ('user', 'Usuário Padaria'),
    ]
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='user',
        verbose_name="Papel no Sistema"
    )
    
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")
    cep = models.CharField(
        max_length=9, 
        blank=True, 
        null=True, 
        verbose_name="CEP",
        help_text="CEP do administrador (usado para região de atuação)"
    )
    birth_date = models.DateField(blank=True, null=True, verbose_name="Data de Nascimento")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"

    def __str__(self):
        return f"Perfil de {self.user.username} ({self.get_role_display()})"


class AgenteCredenciado(models.Model):
    """
    Agente Credenciado - pode cadastrar padarias em determinadas regiões.
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name="agente_credenciado",
        verbose_name="Usuário"
    )
    
    # Dados pessoais
    nome = models.CharField(max_length=200, verbose_name="Nome Completo")
    cpf = models.CharField(max_length=14, unique=True, verbose_name="CPF")
    telefone = models.CharField(max_length=20, verbose_name="Telefone")
    email = models.EmailField(verbose_name="E-mail")
    
    # Regiões de atuação (armazenado como JSON)
    # Formato: [{"cidade": "São Paulo", "uf": "SP"}, {"cidade": "Campinas", "uf": "SP"}]
    regioes_atuacao = models.JSONField(
        default=list, 
        blank=True,
        verbose_name="Regiões de Atuação",
        help_text="Lista de cidades/estados onde o agente pode atuar"
    )
    
    # Padarias cadastradas pelo agente (relacionamento)
    # Isso será gerenciado via ForeignKey na Padaria ou através de um campo aqui
    padarias_cadastradas_ids = models.JSONField(
        default=list, 
        blank=True,
        verbose_name="IDs das Padarias Cadastradas",
        help_text="IDs das padarias cadastradas por este agente"
    )
    
    # Controle
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="agentes_criados",
        verbose_name="Criado por"
    )

    class Meta:
        verbose_name = "Agente Credenciado"
        verbose_name_plural = "Agentes Credenciados"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.nome} ({self.cpf})"
    
    def get_regioes_display(self):
        """Retorna uma string formatada das regiões de atuação."""
        if not self.regioes_atuacao:
            return "Nenhuma região cadastrada"
        
        regioes = []
        for regiao in self.regioes_atuacao:
            if isinstance(regiao, dict):
                cidade = regiao.get('cidade', '')
                uf = regiao.get('uf', '')
                if cidade and uf:
                    regioes.append(f"{cidade}/{uf}")
                elif uf:
                    regioes.append(f"Todo o estado: {uf}")
        
        return ", ".join(regioes) if regioes else "Nenhuma região cadastrada"
    
    def pode_atuar_em(self, uf, cidade=None):
        """Verifica se o agente pode atuar em determinada região."""
        if not self.regioes_atuacao:
            return False
        
        # Garantir inputs seguros
        uf_check = (uf or '').upper()
        cidade_check = (cidade or '').lower()
        
        for regiao in self.regioes_atuacao:
            if isinstance(regiao, dict):
                # Usar (val or '') para garantir string mesmo se for None
                regiao_uf = (regiao.get('uf') or '').upper()
                regiao_cidade = (regiao.get('cidade') or '').lower()
                
                # Se a UF corresponde
                if regiao_uf == uf_check:
                    # Se não tem cidade especificada na região (vazio), vale para todo o estado
                    if not regiao_cidade:
                        return True
                    # Se tem cidade, verifica se corresponde
                    if cidade_check and regiao_cidade == cidade_check:
                        return True
        
        return False
    
    def adicionar_padaria(self, padaria_id):
        """Adiciona uma padaria à lista de padarias cadastradas."""
        if padaria_id not in self.padarias_cadastradas_ids:
            self.padarias_cadastradas_ids.append(padaria_id)
            self.save()
    
    def get_padarias_count(self):
        """Retorna o número de padarias cadastradas."""
        return len(self.padarias_cadastradas_ids)


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Cria o perfil do usuário automaticamente."""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Salva o perfil quando o usuário é salvo."""
    if hasattr(instance, 'profile'):
        instance.profile.save()

