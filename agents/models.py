
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from organizations.models import Padaria


# Choices para Função
ROLE_CHOICES = [
    ('atendente', 'Atendente'),
    ('recepcionista', 'Recepcionista'),
    ('consultor', 'Consultor(a)'),
    ('vendedor', 'Vendedor(a)'),
    ('suporte', 'Suporte Técnico'),
    ('assistente', 'Assistente Virtual'),
    ('gerente', 'Gerente'),
    ('especialista', 'Especialista'),
]

# Choices para Tom de Voz / Personalidade
TONE_CHOICES = [
    ('formal', 'Formal'),
    ('casual', 'Casual'),
    ('amigavel', 'Amigável'),
    ('profissional', 'Profissional'),
    ('profissional_formal', 'Profissional e Formal'),
    ('amigavel_casual', 'Amigável e Casual'),
    ('objetivo_direto', 'Objetivo e Direto'),
    ('simpatico_acolhedor', 'Simpático e Acolhedor'),
    ('energetico_entusiasmado', 'Energético e Entusiasmado'),
    ('calmo_paciente', 'Calmo e Paciente'),
    ('tecnico_detalhista', 'Técnico e Detalhista'),
    ('consultivo_educativo', 'Consultivo e Educativo'),
]

# Choices para Status do Agente
STATUS_CHOICES = [
    ('ativo', 'Ativo'),
    ('inativo', 'Inativo'),
    ('manutencao', 'Em Manutenção'),
]

# Defaults para padaria
DEFAULT_GREETING = """Olá! Eu sou {{agente_nome}}, assistente virtual da {{padaria_nome}}. Como posso te ajudar hoje?"""

DEFAULT_OUT_OF_HOURS_MESSAGE = """Olá! No momento estamos fora do horário de atendimento. Nosso horário de funcionamento é de Segunda a Sexta das 6h às 20h e Sábado das 6h às 14h. Deixe sua mensagem que retornaremos assim que possível!"""

DEFAULT_TONE = "amigavel"

DEFAULT_STYLE_GUIDELINES = """Use linguagem simples e amigável. Seja objetivo mas cordial. 
Sempre confirme detalhes importantes como pedido e horário de retirada. 
Se não souber algo, seja honesto e ofereça alternativas."""

DEFAULT_BUSINESS_HOURS = {
    "mon": "06:00-20:00",
    "tue": "06:00-20:00",
    "wed": "06:00-20:00",
    "thu": "06:00-20:00",
    "fri": "06:00-20:00",
    "sat": "06:00-14:00",
    "sun": "closed"
}

DEFAULT_KNOWLEDGE_BASE = """## Produtos da Padaria

### Pães
- **Pão Francês** - R$ 0,50 (unidade)
- **Pão de Forma** - R$ 8,00 (pacote)
- **Pão Integral** - R$ 12,00 (pacote)
- **Pão de Queijo** - R$ 3,00 (unidade)
- **Croissant** - R$ 5,00 (unidade)

### Doces
- **Bolo de Chocolate** - R$ 35,00 (inteiro) / R$ 6,00 (fatia)
- **Bolo de Cenoura** - R$ 30,00 (inteiro) / R$ 5,00 (fatia)
- **Sonho** - R$ 4,00 (unidade)
- **Brigadeiro** - R$ 2,50 (unidade)

### Salgados
- **Coxinha** - R$ 5,00
- **Esfiha** - R$ 4,00
- **Empada** - R$ 5,00
- **Pastel** - R$ 6,00

### Bebidas
- **Café Expresso** - R$ 4,00
- **Cappuccino** - R$ 7,00
- **Suco Natural** - R$ 8,00
- **Refrigerante** - R$ 5,00

## Políticas

### Encomendas
- Encomendas devem ser feitas com 24h de antecedência
- Para bolos decorados, mínimo 48h de antecedência
- Pagamento de 50% no ato da encomenda

### Entregas
- Entrega disponível para pedidos acima de R$ 50,00
- Taxa de entrega: R$ 5,00 (até 5km)
- Horário de entrega: 8h às 18h

### Formas de Pagamento
- Dinheiro
- Cartão de débito e crédito
- PIX
"""

DEFAULT_FALLBACK_MESSAGE = """Desculpe, não entendi bem sua solicitação. Pode reformular de outra forma?"""

DEFAULT_ESCALATION_RULE = """Transferir para atendente humano quando:
- Cliente solicitar explicitamente
- Reclamação ou problema não resolvido
- Situação complexa que exija decisão humana
- Cliente demonstrar insatisfação após 2 tentativas"""


class Agent(models.Model):
    """
    Agente de IA configurável por padaria.
    Limite: 1 agente por padaria.
    """
    padaria = models.ForeignKey(
        Padaria,
        on_delete=models.CASCADE,
        related_name="agents",
        verbose_name="Padaria"
    )
    name = models.CharField(max_length=100, verbose_name="Nome do Agente")
    slug = models.SlugField(max_length=120, unique=True, verbose_name="Slug")
    
    # Papel e contexto
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default="atendente",
        verbose_name="Função",
        help_text="Selecione a função do agente"
    )
    sector = models.CharField(
        max_length=100,
        default="padaria",
        verbose_name="Setor",
        help_text="Ex: padaria, confeitaria, café"
    )
    language = models.CharField(
        max_length=10,
        default="pt-BR",
        verbose_name="Idioma",
        help_text="Código do idioma (pt-BR, en-US, etc)"
    )
    
    # Configuração de comportamento
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ativo',
        verbose_name="Status",
        help_text="Status atual do agente"
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo (deprecated - usar status)")
    
    # Personalidade e Tom
    personality = models.CharField(
        max_length=50,
        choices=TONE_CHOICES,
        default=DEFAULT_TONE,
        verbose_name="Personalidade/Tom",
        help_text="Define o tom de voz e personalidade do agente"
    )
    
    # Mensagens customizáveis
    greeting = models.TextField(
        default=DEFAULT_GREETING,
        verbose_name="Mensagem de Boas-vindas",
        help_text="Primeira mensagem enviada ao usuário. Use {{agente_nome}} e {{padaria_nome}} para personalização"
    )
    out_of_hours_message = models.TextField(
        default=DEFAULT_OUT_OF_HOURS_MESSAGE,
        verbose_name="Mensagem Fora do Horário",
        help_text="Mensagem enviada quando fora do horário de atendimento"
    )
    
    # Palavras-chave para transferência
    transfer_keywords = models.TextField(
        blank=True,
        default="falar com humano, atendente, pessoa, reclamação, problema sério",
        verbose_name="Palavras-chave de Transferência",
        help_text="Palavras separadas por vírgula que acionam transferência para humano"
    )
    
    # Tempo de resposta
    max_response_time = models.IntegerField(
        default=30,
        verbose_name="Tempo Máximo de Resposta (segundos)",
        help_text="Tempo máximo esperado para o agente responder"
    )
    
    tone = models.CharField(
        max_length=50,
        choices=TONE_CHOICES,
        default=DEFAULT_TONE,
        verbose_name="Tom de Voz (deprecated - usar personality)",
        help_text="Selecione o tom de voz do agente"
    )
    style_guidelines = models.TextField(
        default=DEFAULT_STYLE_GUIDELINES,
        verbose_name="Diretrizes de Estilo",
        help_text="Instruções sobre como o agente deve se comunicar"
    )
    
    # Horário e disponibilidade
    business_hours = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Horário de Funcionamento",
        help_text="JSON com horários por dia da semana"
    )
    
    # Novos campos para cronograma de atendimento
    working_days = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Dias de Funcionamento",
        help_text="Lista de dias que funciona: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']"
    )
    morning_start = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Horário Inicial - Matutino",
        help_text="Ex: 07:00"
    )
    morning_end = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Horário Final - Matutino",
        help_text="Ex: 11:00"
    )
    afternoon_start = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Horário Inicial - Vespertino",
        help_text="Ex: 13:00"
    )
    afternoon_end = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Horário Final - Vespertino",
        help_text="Ex: 17:00"
    )
    
    # Base de conhecimento
    knowledge_base = models.TextField(
        default=DEFAULT_KNOWLEDGE_BASE,
        verbose_name="Base de Conhecimento",
        help_text="Informações sobre produtos, serviços, políticas, etc (Markdown)"
    )
    knowledge_pdf = models.FileField(
        upload_to="knowledge_pdfs/",
        null=True,
        blank=True,
        verbose_name="PDF de Conhecimento",
        help_text="Upload do PDF com informações do negócio"
    )
    knowledge_pdf_text = models.TextField(
        blank=True,
        default="",
        verbose_name="Texto Extraído do PDF",
        help_text="Texto extraído automaticamente do PDF para busca e preview"
    )
    knowledge_pdf_category = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Categoria do PDF",
        help_text="Ex: Produtos, FAQ, Políticas, Procedimentos"
    )
    knowledge_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Conhecimento Atualizado em",
        help_text="Data da última atualização do conhecimento (PDF ou texto)"
    )
    
    # Tratamento de exceções
    fallback_message = models.TextField(
        default=DEFAULT_FALLBACK_MESSAGE,
        verbose_name="Mensagem de Fallback",
        help_text="Quando o agente não entende a solicitação"
    )
    escalation_rule = models.TextField(
        default=DEFAULT_ESCALATION_RULE,
        verbose_name="Regra de Escalonamento",
        help_text="Quando e como transferir para atendente humano"
    )
    
    # Integração com N8N
    n8n_webhook_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Webhook N8N",
        help_text="URL do webhook do N8N para notificar atualizações (ex: quando PDF é upado)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["-created_at"]
        unique_together = [("padaria", "slug")]

    def __str__(self):
        return f"{self.name} ({self.padaria.name})"

    def clean(self):
        """Validação para garantir limite de 1 agente por padaria."""
        if self.padaria_id:
            existing = Agent.objects.filter(padaria=self.padaria).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    "Esta padaria já possui um agente. Cada padaria pode ter apenas 1 agente."
                )

    def save(self, *args, **kwargs):
        from django.utils import timezone
        
        # Validar limite de 1 agente por padaria
        self.clean()
        
        if not self.slug:
            base_slug = slugify(self.name)
            slug = f"{base_slug}-{self.padaria.slug}"
            self.slug = slug
        
        # Garantir business_hours default
        if not self.business_hours:
            self.business_hours = DEFAULT_BUSINESS_HOURS
        
        # Atualizar knowledge_updated_at se PDF ou knowledge_base mudou
        if self.pk:
            try:
                old_instance = Agent.objects.get(pk=self.pk)
                if (old_instance.knowledge_pdf != self.knowledge_pdf or 
                    old_instance.knowledge_base != self.knowledge_base):
                    self.knowledge_updated_at = timezone.now()
            except Agent.DoesNotExist:
                pass
        else:
            # Novo agente
            if self.knowledge_pdf or self.knowledge_base != DEFAULT_KNOWLEDGE_BASE:
                self.knowledge_updated_at = timezone.now()
            
        super().save(*args, **kwargs)

    def render_greeting(self, cliente_nome="Cliente", agente_nome=None):
        """Renderiza a saudação com placeholders substituídos."""
        if agente_nome is None:
            agente_nome = self.name
        
        greeting = self.greeting
        greeting = greeting.replace("{{cliente_nome}}", cliente_nome)
        greeting = greeting.replace("{{agente_nome}}", agente_nome)
        greeting = greeting.replace("{{padaria_nome}}", self.padaria.name)
        return greeting
    
    def get_role_display_custom(self):
        """Retorna o nome legível da função."""
        return dict(ROLE_CHOICES).get(self.role, self.role)
    
    def get_tone_display_custom(self):
        """Retorna o nome legível do tom de voz."""
        return dict(TONE_CHOICES).get(self.tone, self.tone)


# Alias para compatibilidade
Organization = Padaria
