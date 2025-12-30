# agents/forms.py
"""
Formulário simplificado para criação/edição de agentes.
"""
from django import forms
from .models import Agent
from .presets import get_preset_choices, get_preset_defaults
from organizations.models import Padaria, PadariaUser


class AgentSimpleForm(forms.ModelForm):
    """Formulário simplificado com foco em experiência rápida."""
    
    # Campo não persistido - apenas para UX
    agent_preset = forms.ChoiceField(
        label='Perfil do Agente',
        choices=get_preset_choices(),
        required=False,
        initial='neutral',
        help_text='Escolha um perfil para aplicar configurações padrão automaticamente',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'updatePresetDescription(this.value)'
        })
    )
    
    # Campo para aplicar defaults do preset
    apply_preset = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput()
    )
    
    # Transformar status em toggle visual
    status_toggle = forms.ChoiceField(
        label='Status do Agente',
        choices=[('ativo', 'Ativo'), ('inativo', 'Inativo')],
        initial='ativo',
        widget=forms.RadioSelect(attrs={'class': 'status-toggle'})
    )
    
    # Campo de transferência humana
    enable_human_transfer = forms.BooleanField(
        label='Permitir transferência para humano',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'toggle-checkbox', 'onchange': 'toggleTransferFields()'})
    )
    
    # Número de falhas antes de transferir
    transfer_failures_threshold = forms.ChoiceField(
        label='Transferir após quantas falhas de entendimento?',
        choices=[(1, '1 falha'), (2, '2 falhas'), (3, '3 falhas')],
        initial=2,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = Agent
        fields = [
            'padaria',
            'name',
            'language',
            'greeting',
            'out_of_hours_message',
            'fallback_message',
            'knowledge_pdf',
            'knowledge_pdf_category',
            'knowledge_base',
            'transfer_keywords',
            # Campos avançados
            'sector',
            'personality',
            'tone',
            'style_guidelines',
            'escalation_rule',
            'max_response_time',
            'n8n_webhook_url',
        ]
        
        widgets = {
            'padaria': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ex: Atendente Virtual Maria',
                'autofocus': True
            }),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'greeting': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Ex: Olá {{cliente_nome}}! Sou {{agente_nome}}, como posso ajudar?'
            }),
            'out_of_hours_message': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Mensagem exibida fora do horário de atendimento'
            }),
            'fallback_message': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 2,
                'placeholder': 'Mensagem quando não entender o que o cliente disse'
            }),
            'knowledge_pdf': forms.FileInput(attrs={
                'class': 'form-file-input',
                'accept': '.pdf'
            }),
            'knowledge_pdf_category': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ex: Catálogo de Produtos 2024'
            }),
            'knowledge_base': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Observações rápidas ou informações adicionais (opcional)'
            }),
            'transfer_keywords': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ex: falar com humano, atendente, pessoa'
            }),
            # Campos avançados
            'sector': forms.Select(attrs={'class': 'form-select'}),
            'personality': forms.Select(attrs={'class': 'form-select'}),
            'tone': forms.TextInput(attrs={'class': 'form-input'}),
            'style_guidelines': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
            'escalation_rule': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'max_response_time': forms.NumberInput(attrs={'class': 'form-input', 'min': 10, 'max': 120}),
            'n8n_webhook_url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://...'}),
        }
        
        labels = {
            'padaria': 'Padaria',
            'name': 'Nome do Agente',
            'language': 'Idioma',
            'greeting': 'Mensagem de Saudação',
            'out_of_hours_message': 'Mensagem Fora do Horário',
            'fallback_message': 'Mensagem Alternativa',
            'knowledge_pdf': 'PDF de Conhecimento',
            'knowledge_pdf_category': 'Categoria do PDF (opcional)',
            'knowledge_base': 'Observações Rápidas (opcional)',
            'transfer_keywords': 'Palavras-chave de Transferência',
            # Avançados
            'sector': 'Setor',
            'personality': 'Personalidade',
            'tone': 'Tom de Voz',
            'style_guidelines': 'Diretrizes de Estilo Completas',
            'escalation_rule': 'Regra de Escalonamento Detalhada',
            'max_response_time': 'Tempo Máximo de Resposta (segundos)',
            'n8n_webhook_url': 'N8N Webhook URL',
        }
        
        help_texts = {
            'name': 'Nome amigável que aparecerá nas conversas',
            'greeting': 'Use {{cliente_nome}}, {{agente_nome}} e {{padaria_nome}} como placeholders',
            'knowledge_pdf': 'Envie seu catálogo/FAQ. O texto será extraído automaticamente.',
            'knowledge_base': 'Informações complementares que não estão no PDF',
            'transfer_keywords': 'Palavras que acionam transferência para humano',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make message fields optional
        self.fields['greeting'].required = False
        self.fields['out_of_hours_message'].required = False
        self.fields['fallback_message'].required = False
        self.fields['knowledge_base'].required = False
        self.fields['knowledge_pdf_category'].required = False
        self.fields['transfer_keywords'].required = False
        
        # Make advanced fields optional
        self.fields['personality'].required = False
        self.fields['tone'].required = False
        self.fields['style_guidelines'].required = False
        self.fields['escalation_rule'].required = False
        self.fields['max_response_time'].required = False
        
        # Filtrar padarias do usuário (onde é dono ou funcionário)
        if self.user:
            if self.user.is_superuser:
                # Admin master pode ver todas
                self.fields['padaria'].queryset = Padaria.objects.all()
            else:
                # Usuário normal: apenas padarias onde é dono
                user_padarias = PadariaUser.objects.filter(
                    user=self.user, 
                    role='dono'
                ).values_list('padaria_id', flat=True)
                self.fields['padaria'].queryset = Padaria.objects.filter(id__in=user_padarias)
        
        # Se editando, preencher status_toggle
        if self.instance and self.instance.pk:
            self.fields['status_toggle'].initial = self.instance.status
            
            # Verificar se tem transferência habilitada
            if self.instance.transfer_keywords:
                self.fields['enable_human_transfer'].initial = True
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Mapear status_toggle para status
        status_toggle = cleaned_data.get('status_toggle')
        if status_toggle:
            cleaned_data['status'] = status_toggle
        
        # Se aplicar preset, sobrescrever campos
        apply_preset = cleaned_data.get('apply_preset')
        agent_preset = cleaned_data.get('agent_preset')
        
        if apply_preset and agent_preset:
            defaults = get_preset_defaults(agent_preset)
            
            # Aplicar defaults apenas se campos estiverem vazios
            for field, value in defaults.items():
                if field in cleaned_data and not cleaned_data.get(field):
                    cleaned_data[field] = value
        
        # Configurar escalation_rule baseado no threshold
        enable_transfer = cleaned_data.get('enable_human_transfer')
        if enable_transfer:
            threshold = cleaned_data.get('transfer_failures_threshold', 2)
            cleaned_data['escalation_rule'] = f'Transferir após {threshold} tentativas sem sucesso'
        else:
            cleaned_data['transfer_keywords'] = ''
            cleaned_data['escalation_rule'] = ''
        
        return cleaned_data
