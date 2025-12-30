import secrets
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class Padaria(models.Model):
    """
    Padaria (tenant principal do sistema).
    Antiga 'Organization' renomeada para o novo contexto.
    """
    name = models.CharField(max_length=200, verbose_name="Nome da Padaria")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="Slug")
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_padarias",
        verbose_name="Dono"
    )
    # Campos de contato
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefone")
    email = models.EmailField(blank=True, verbose_name="E-mail")
    cnpj = models.CharField(max_length=18, blank=True, verbose_name="CNPJ")
    address = models.TextField(blank=True, verbose_name="Endereço")
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name="Ativa")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Padaria"
        verbose_name_plural = "Padarias"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            
            # Garantir que o slug seja único
            while Padaria.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        super().save(*args, **kwargs)
    
    def get_agent(self):
        """Retorna o agente da padaria (limite de 1)."""
        return self.agents.first()
    
    def has_agent(self):
        """Verifica se a padaria já tem um agente."""
        return self.agents.exists()


class PadariaUser(models.Model):
    """
    Relaciona usuários com padarias e seus papéis.
    """
    ROLE_CHOICES = [
        ('dono', 'Dono'),
        ('funcionario', 'Funcionário'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="padaria_memberships",
        verbose_name="Usuário"
    )
    padaria = models.ForeignKey(
        Padaria,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name="Padaria"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='funcionario',
        verbose_name="Papel"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Adicionado em")
    
    class Meta:
        verbose_name = "Membro da Padaria"
        verbose_name_plural = "Membros da Padaria"
        unique_together = [("user", "padaria")]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.user.username} - {self.padaria.name} ({self.get_role_display()})"
    
    def is_dono(self):
        return self.role == 'dono'
    
    def is_funcionario(self):
        return self.role == 'funcionario'


class ApiKey(models.Model):
    """
    Chave de API para autenticação de integrações (n8n).
    Vinculada a um Agente específico.
    """
    key = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Chave")
    padaria = models.ForeignKey(
        Padaria,
        on_delete=models.CASCADE,
        related_name="api_keys",
        verbose_name="Padaria"
    )
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        related_name="api_keys",
        null=True,
        blank=True,
        verbose_name="Agente",
        help_text="Se definido, essa API Key só terá acesso a este agente específico"
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativa")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nome/Descrição")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name="Último uso")

    class Meta:
        verbose_name = "Chave de API"
        verbose_name_plural = "Chaves de API"
        ordering = ["-created_at"]

    def __str__(self):
        agent_info = f" - {self.agent.name}" if self.agent else ""
        return f"{self.padaria.name}{agent_info} - {self.key[:12]}..."

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = f"sk_{secrets.token_urlsafe(32)}"
        super().save(*args, **kwargs)

    @staticmethod
    def generate_key():
        """Gera uma nova chave única."""
        return f"sk_{secrets.token_urlsafe(32)}"
    
    def has_access_to_agent(self, agent):
        """
        Verifica se esta API Key tem acesso ao agente especificado.
        """
        # Se não tem agente específico, tem acesso a todos da padaria
        if not self.agent:
            return agent.padaria == self.padaria
        # Se tem agente específico, só acessa esse
        return self.agent == agent

# Alias para compatibilidade durante migração
Organization = Padaria


class Promocao(models.Model):
    """
    Promoção ou aviso para exibir no chatbot.
    Cada padaria pode ter múltiplas promoções.
    """
    padaria = models.ForeignKey(
        Padaria,
        on_delete=models.CASCADE,
        related_name="promocoes",
        verbose_name="Padaria"
    )
    titulo = models.CharField(max_length=200, verbose_name="Título")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    preco = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço Promocional"
    )
    preco_original = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço Original"
    )
    imagem = models.ImageField(
        upload_to='promocoes/',
        null=True,
        blank=True,
        verbose_name="Imagem"
    )
    data_inicio = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Início"
    )
    data_fim = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Validade"
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativa")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Promoção"
        verbose_name_plural = "Promoções"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.titulo} - {self.padaria.name}"
    
    def is_valid(self):
        """Verifica se a promoção está dentro do período de validade."""
        from django.utils import timezone
        today = timezone.now().date()
        
        if not self.is_active:
            return False
        
        if self.data_inicio and today < self.data_inicio:
            return False
        
        if self.data_fim and today > self.data_fim:
            return False
        
        return True
    
    def get_discount_percentage(self):
        """Calcula a porcentagem de desconto."""
        if self.preco and self.preco_original and self.preco_original > 0:
            discount = ((self.preco_original - self.preco) / self.preco_original) * 100
            return round(discount, 0)
        return None


class Cliente(models.Model):
    """
    Cliente cadastrado de uma padaria.
    Armazena informações de contato para envio de promoções via WhatsApp.
    """
    padaria = models.ForeignKey(
        Padaria,
        on_delete=models.CASCADE,
        related_name="clientes",
        verbose_name="Padaria"
    )
    nome = models.CharField(max_length=200, verbose_name="Nome")
    telefone = models.CharField(
        max_length=20,
        verbose_name="Telefone/WhatsApp",
        help_text="Número com DDD, ex: (11) 99999-9999"
    )
    email = models.EmailField(blank=True, verbose_name="E-mail")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    aceita_promocoes = models.BooleanField(
        default=True,
        verbose_name="Aceita receber promoções",
        help_text="Cliente autoriza receber mensagens de promoções"
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Cadastrado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nome"]
        unique_together = [("padaria", "telefone")]

    def __str__(self):
        return f"{self.nome} - {self.telefone}"
    
    def get_telefone_formatado(self):
        """Retorna telefone apenas com números para envio."""
        import re
        return re.sub(r'\D', '', self.telefone)
    
    def get_telefone_whatsapp(self):
        """Retorna telefone no formato WhatsApp (com 55 se necessário)."""
        telefone = self.get_telefone_formatado()
        if not telefone.startswith('55'):
            telefone = '55' + telefone
        return telefone


class CampanhaWhatsApp(models.Model):
    """
    Campanha de envio de promoções via WhatsApp.
    Implementa delay entre mensagens para evitar ban (estilo Astra Campaign).
    """
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('agendada', 'Agendada'),
        ('enviando', 'Em Envio'),
        ('pausada', 'Pausada'),
        ('concluida', 'Concluída'),
        ('cancelada', 'Cancelada'),
        ('erro', 'Erro'),
    ]
    
    padaria = models.ForeignKey(
        Padaria,
        on_delete=models.CASCADE,
        related_name="campanhas",
        verbose_name="Padaria"
    )
    promocao = models.ForeignKey(
        Promocao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campanhas",
        verbose_name="Promoção vinculada"
    )
    nome = models.CharField(max_length=200, verbose_name="Nome da Campanha")
    mensagem = models.TextField(
        verbose_name="Mensagem",
        help_text="Use {{nome_cliente}} para personalizar"
    )
    imagem = models.ImageField(
        upload_to='campanhas/',
        null=True,
        blank=True,
        verbose_name="Imagem (opcional)"
    )
    
    # Configurações de envio (estilo Astra Campaign)
    delay_minimo = models.IntegerField(
        default=10,
        verbose_name="Delay mínimo (segundos)",
        help_text="Tempo mínimo entre cada mensagem"
    )
    delay_maximo = models.IntegerField(
        default=30,
        verbose_name="Delay máximo (segundos)",
        help_text="Tempo máximo entre cada mensagem"
    )
    lote_tamanho = models.IntegerField(
        default=10,
        verbose_name="Tamanho do lote",
        help_text="Quantidade de mensagens por lote antes de pausa maior"
    )
    pausa_entre_lotes = models.IntegerField(
        default=60,
        verbose_name="Pausa entre lotes (segundos)",
        help_text="Tempo de pausa após cada lote"
    )
    
    # Agendamento
    data_agendamento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de agendamento"
    )
    
    # Status e estatísticas
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='rascunho',
        verbose_name="Status"
    )
    total_destinatarios = models.IntegerField(default=0, verbose_name="Total de destinatários")
    enviados = models.IntegerField(default=0, verbose_name="Enviados")
    falhas = models.IntegerField(default=0, verbose_name="Falhas")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    iniciado_em = models.DateTimeField(null=True, blank=True, verbose_name="Iniciado em")
    concluido_em = models.DateTimeField(null=True, blank=True, verbose_name="Concluído em")

    class Meta:
        verbose_name = "Campanha WhatsApp"
        verbose_name_plural = "Campanhas WhatsApp"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nome} - {self.padaria.name}"
    
    def get_progresso(self):
        """Retorna porcentagem de progresso."""
        if self.total_destinatarios > 0:
            return round((self.enviados / self.total_destinatarios) * 100, 1)
        return 0
    
    def get_delay_aleatorio(self):
        """Retorna um delay aleatório entre mínimo e máximo."""
        import random
        return random.randint(self.delay_minimo, self.delay_maximo)


class MensagemCampanha(models.Model):
    """
    Registro de cada mensagem enviada em uma campanha.
    """
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('enviando', 'Enviando'),
        ('enviado', 'Enviado'),
        ('falha', 'Falha'),
    ]
    
    campanha = models.ForeignKey(
        CampanhaWhatsApp,
        on_delete=models.CASCADE,
        related_name="mensagens",
        verbose_name="Campanha"
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="mensagens_recebidas",
        verbose_name="Cliente"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente',
        verbose_name="Status"
    )
    erro_mensagem = models.TextField(blank=True, verbose_name="Mensagem de erro")
    enviado_em = models.DateTimeField(null=True, blank=True, verbose_name="Enviado em")
    
    class Meta:
        verbose_name = "Mensagem de Campanha"
        verbose_name_plural = "Mensagens de Campanha"
        ordering = ["id"]
        unique_together = [("campanha", "cliente")]

    def __str__(self):
        return f"{self.campanha.nome} -> {self.cliente.nome}"

