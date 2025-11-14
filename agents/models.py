from django.db import models
from django.utils.text import slugify
from organizations.models import Organization


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

# Choices para Tom de Voz
TONE_CHOICES = [
    ('profissional_formal', 'Profissional e Formal'),
    ('amigavel_casual', 'Amigável e Casual'),
    ('objetivo_direto', 'Objetivo e Direto'),
    ('simpatico_acolhedor', 'Simpático e Acolhedor'),
    ('energetico_entusiasmado', 'Energético e Entusiasmado'),
    ('calmo_paciente', 'Calmo e Paciente'),
    ('tecnico_detalhista', 'Técnico e Detalhista'),
    ('consultivo_educativo', 'Consultivo e Educativo'),
]

# Defaults para manicure/pedicure
DEFAULT_GREETING = """Olá {{cliente_nome}}! Eu sou {{agente_nome}}, atendente da Unhas Fast 💅. Como posso te ajudar hoje?"""

DEFAULT_TONE = "simpatico_acolhedor"

DEFAULT_STYLE_GUIDELINES = """Use linguagem simples e amigável. Seja objetivo mas cordial. 
Sempre confirme detalhes importantes como data, horário e serviço. 
Se não souber algo, seja honesto e ofereça alternativas."""

DEFAULT_BUSINESS_HOURS = {
    "mon": "09:00-18:00",
    "tue": "09:00-18:00",
    "wed": "09:00-18:00",
    "thu": "09:00-18:00",
    "fri": "09:00-18:00",
    "sat": "09:00-14:00",
    "sun": "closed"
}

DEFAULT_KNOWLEDGE_BASE = """## Serviços Oferecidos

- **Manicure básica** (30min) - R$ 25,00
- **Pedicure básica** (45min) - R$ 35,00
- **Manicure + Pedicure** (1h15min) - R$ 55,00
- **Spa de mãos** (45min) - R$ 40,00
- **Spa de pés** (1h) - R$ 50,00
- **Alongamento de unhas** (1h30min) - R$ 80,00
- **Nail art personalizada** (30min adicional) - R$ 20,00

## Políticas do Salão

### Agendamento
- Agendamentos podem ser feitos por telefone, WhatsApp ou pessoalmente
- Recomendamos agendar com pelo menos 24h de antecedência
- Horários disponíveis: Segunda a Sexta 09:00-18:00, Sábado 09:00-14:00

### Atrasos e Remarcações
- Tolerância de atraso: 10 minutos
- Remarcação gratuita: até 24h de antecedência
- Cancelamento com menos de 24h: taxa de 50% do valor do serviço
- Falta sem aviso: taxa de 100%

### Formas de Pagamento
- Dinheiro
- Cartão de débito e crédito
- PIX
- Não trabalhamos com cheque

## Cuidados Pós-Atendimento

### Após Esmaltação
- Evite água quente por 2h após a aplicação
- Não mergulhe as mãos em água nas primeiras 4h
- Use luvas ao fazer limpeza pesada ou lavar louça
- Evite piscina e mar nas primeiras 24h

### Cuidados Diários
- Hidrate cutículas diariamente com óleo específico
- Use base fortalecedora se as unhas forem frágeis
- Lixe sempre na mesma direção
- Não use as unhas como ferramenta

### Alongamento de Unhas
- Retoque recomendado a cada 15-20 dias
- Nunca arranque ou force a remoção
- Mantenha as unhas hidratadas
- Evite impactos fortes

## Perguntas Frequentes

**Precisa agendar para todos os serviços?**
Sim, trabalhamos apenas com agendamento para garantir melhor atendimento.

**Pode levar esmalte próprio?**
Sim, mas verificamos a qualidade antes da aplicação.

**Fazem atendimento a domicílio?**
Não, apenas no salão.

**Atendem homens?**
Sim, oferecemos serviços de manicure e pedicure masculina.

**Tem estacionamento?**
Temos convênio com estacionamento ao lado (2h grátis).
"""

DEFAULT_FALLBACK_MESSAGE = """Desculpe, não entendi bem sua solicitação. Pode reformular? 
Ou se preferir, posso transferir para um atendente humano."""

DEFAULT_ESCALATION_RULE = """Transferir para atendente humano quando:
- Cliente solicitar explicitamente
- Reclamação ou problema não resolvido
- Situação complexa que exija decisão humana
- Cliente demonstrar insatisfação após 2 tentativas"""


class Agent(models.Model):
    """
    Agente de IA configurável por organização.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="agents",
        verbose_name="Organização"
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
        default="manicure/pedicure",
        verbose_name="Setor",
        help_text="Ex: manicure/pedicure, beleza, estética"
    )
    language = models.CharField(
        max_length=10,
        default="pt-BR",
        verbose_name="Idioma",
        help_text="Código do idioma (pt-BR, en-US, etc)"
    )
    
    # Configuração de comportamento
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    greeting = models.TextField(
        default=DEFAULT_GREETING,
        verbose_name="Saudação Inicial",
        help_text="Use {{cliente_nome}} e {{agente_nome}} para personalização"
    )
    tone = models.CharField(
        max_length=50,
        choices=TONE_CHOICES,
        default=DEFAULT_TONE,
        verbose_name="Tom de Voz",
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
    
    # Base de conhecimento
    knowledge_base = models.TextField(
        default=DEFAULT_KNOWLEDGE_BASE,
        verbose_name="Base de Conhecimento",
        help_text="Informações sobre serviços, políticas, etc (Markdown)"
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
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["-created_at"]
        unique_together = [("organization", "slug")]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = f"{base_slug}-{self.organization.slug}"
            self.slug = slug
        
        # Garantir business_hours default
        if not self.business_hours:
            self.business_hours = DEFAULT_BUSINESS_HOURS
            
        super().save(*args, **kwargs)

    def render_greeting(self, cliente_nome="Cliente", agente_nome=None):
        """Renderiza a saudação com placeholders substituídos."""
        if agente_nome is None:
            agente_nome = self.name
        
        greeting = self.greeting
        greeting = greeting.replace("{{cliente_nome}}", cliente_nome)
        greeting = greeting.replace("{{agente_nome}}", agente_nome)
        return greeting
    
    def get_role_display_custom(self):
        """Retorna o nome legível da função."""
        return dict(ROLE_CHOICES).get(self.role, self.role)
    
    def get_tone_display_custom(self):
        """Retorna o nome legível do tom de voz."""
        return dict(TONE_CHOICES).get(self.tone, self.tone)
