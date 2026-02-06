from django.db import models
from django.conf import settings
from organizations.models import Padaria


# =============================================================================
# Modelos Existentes (Stripe - mantidos para retrocompatibilidade)
# =============================================================================

class StripeAccount(models.Model):
    """
    Conta Stripe Connect (Express) vinculada à Padaria.
    Armazena o ID da conta e status de onboarding.
    """
    padaria = models.OneToOneField(
        Padaria,
        on_delete=models.CASCADE,
        related_name="stripe_account",
        verbose_name="Padaria"
    )
    stripe_account_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="ID da Conta Stripe"
    )
    
    # Status da conta
    is_onboarding_complete = models.BooleanField(
        default=False,
        verbose_name="Onboarding Completo"
    )
    charges_enabled = models.BooleanField(
        default=False,
        verbose_name="Pode Receber Pagamentos"
    )
    payouts_enabled = models.BooleanField(
        default=False,
        verbose_name="Pode Receber Transferências"
    )
    details_submitted = models.BooleanField(
        default=False,
        verbose_name="Dados Enviados"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    class Meta:
        verbose_name = "Conta Stripe"
        verbose_name_plural = "Contas Stripe"
    
    def __str__(self):
        return f"Stripe - {self.padaria.name}"
    
    @property
    def is_fully_enabled(self):
        """Verifica se a conta está totalmente habilitada para pagamentos."""
        return self.charges_enabled and self.payouts_enabled and self.details_submitted


class PaymentSession(models.Model):
    """
    Sessão de pagamento criada para um pedido do chatbot.
    Armazena informações da sessão de checkout do Stripe.
    """
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('completed', 'Concluído'),
        ('expired', 'Expirado'),
        ('failed', 'Falhou'),
    ]
    
    padaria = models.ForeignKey(
        Padaria,
        on_delete=models.CASCADE,
        related_name="payment_sessions",
        verbose_name="Padaria"
    )
    
    # Stripe session info
    stripe_session_id = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        verbose_name="ID da Sessão Stripe"
    )
    checkout_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="URL de Checkout"
    )
    
    # Order info
    customer_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Telefone do Cliente"
    )
    customer_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nome do Cliente"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descrição do Pedido"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valor (R$)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Concluído em")
    
    class Meta:
        verbose_name = "Sessão de Pagamento"
        verbose_name_plural = "Sessões de Pagamento"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Pagamento #{self.id} - {self.padaria.name} - R${self.amount}"


# =============================================================================
# Modelos Novos (Asaas + Mercado Pago)
# =============================================================================

class AsaasSubscription(models.Model):
    """
    Assinatura do SaaS via Asaas.
    Gerencia o pagamento recorrente das padarias para usar o sistema.
    """
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('active', 'Ativa'),
        ('overdue', 'Inadimplente'),
        ('cancelled', 'Cancelada'),
        ('expired', 'Expirada'),
    ]
    
    BILLING_TYPE_CHOICES = [
        ('PIX', 'PIX'),
        ('CREDIT_CARD', 'Cartão de Crédito'),
        ('BOLETO', 'Boleto'),
    ]
    
    padaria = models.OneToOneField(
        Padaria,
        on_delete=models.CASCADE,
        related_name="asaas_subscription",
        verbose_name="Padaria"
    )
    
    # IDs do Asaas
    asaas_customer_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="ID do Cliente no Asaas"
    )
    asaas_subscription_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="ID da Assinatura no Asaas"
    )
    
    # Informações do plano
    plan_name = models.CharField(
        max_length=100,
        default="Plano Único",
        verbose_name="Nome do Plano"
    )
    plan_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Valor do Plano (R$)"
    )
    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        default='PIX',
        verbose_name="Forma de Pagamento"
    )
    
    # Status e datas
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    next_due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Próximo Vencimento"
    )
    last_payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Último Pagamento"
    )
    
    # Link de pagamento atual (se houver cobrança pendente)
    current_payment_link = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Link de Pagamento Atual"
    )
    current_payment_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID do Pagamento Atual"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    class Meta:
        verbose_name = "Assinatura Asaas"
        verbose_name_plural = "Assinaturas Asaas"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Assinatura - {self.padaria.name} ({self.get_status_display()})"
    
    @property
    def is_active(self):
        """Verifica se a assinatura está ativa."""
        return self.status == 'active'
    
    @property
    def is_overdue(self):
        """Verifica se a assinatura está inadimplente."""
        return self.status == 'overdue'
    
    def days_until_due(self):
        """Retorna dias até o próximo vencimento."""
        if not self.next_due_date:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        delta = self.next_due_date - today
        return delta.days


class AsaasPayment(models.Model):
    """
    Registro de pagamentos individuais da assinatura Asaas.
    Histórico de faturas pagas/pendentes.
    """
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('confirmed', 'Confirmado'),
        ('received', 'Recebido'),
        ('overdue', 'Vencido'),
        ('refunded', 'Estornado'),
        ('deleted', 'Removido'),
    ]
    
    subscription = models.ForeignKey(
        AsaasSubscription,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Assinatura"
    )
    
    # IDs do Asaas
    asaas_payment_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="ID do Pagamento no Asaas"
    )
    
    # Informações do pagamento
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valor (R$)"
    )
    due_date = models.DateField(verbose_name="Data de Vencimento")
    payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data do Pagamento"
    )
    billing_type = models.CharField(
        max_length=20,
        verbose_name="Forma de Pagamento"
    )
    
    # Link para pagamento
    invoice_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Link da Fatura"
    )
    pix_qrcode = models.TextField(
        blank=True,
        verbose_name="QR Code PIX (Base64)"
    )
    pix_copy_paste = models.TextField(
        blank=True,
        verbose_name="PIX Copia e Cola"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    class Meta:
        verbose_name = "Pagamento Asaas"
        verbose_name_plural = "Pagamentos Asaas"
        ordering = ["-due_date"]
    
    def __str__(self):
        return f"Pagamento {self.asaas_payment_id} - R${self.value}"


class MercadoPagoConfig(models.Model):
    """
    Credenciais do Mercado Pago por padaria.
    Permite que cada padaria receba pagamentos de seus clientes.
    """
    padaria = models.OneToOneField(
        Padaria,
        on_delete=models.CASCADE,
        related_name="mercadopago_config",
        verbose_name="Padaria"
    )
    
    # Credenciais (access_token deve ser tratado com cuidado)
    access_token = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Access Token",
        help_text="Token privado do Mercado Pago"
    )
    public_key = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Public Key",
        help_text="Chave pública do Mercado Pago"
    )
    
    # Status
    is_active = models.BooleanField(
        default=False,
        verbose_name="Ativo",
        help_text="Credenciais verificadas e funcionando"
    )
    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última Verificação"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    class Meta:
        verbose_name = "Configuração Mercado Pago"
        verbose_name_plural = "Configurações Mercado Pago"
    
    def __str__(self):
        status = "✓" if self.is_active else "✗"
        return f"MP {status} - {self.padaria.name}"
    
    @property
    def is_configured(self):
        """Verifica se as credenciais estão preenchidas."""
        return bool(self.access_token and self.public_key)


class MercadoPagoPayment(models.Model):
    """
    Registro de pagamentos gerados via Mercado Pago.
    Pagamentos de clientes para a padaria.
    """
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('approved', 'Aprovado'),
        ('authorized', 'Autorizado'),
        ('in_process', 'Em Processamento'),
        ('rejected', 'Rejeitado'),
        ('cancelled', 'Cancelado'),
        ('refunded', 'Estornado'),
    ]
    
    config = models.ForeignKey(
        MercadoPagoConfig,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Configuração MP"
    )
    
    # IDs do Mercado Pago
    mp_payment_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="ID do Pagamento no MP"
    )
    mp_preference_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID da Preferência no MP"
    )
    
    # Informações do pagamento
    description = models.CharField(
        max_length=255,
        verbose_name="Descrição"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valor (R$)"
    )
    
    # Cliente
    payer_email = models.EmailField(
        blank=True,
        verbose_name="E-mail do Pagador"
    )
    payer_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Telefone do Pagador"
    )
    
    # Links
    checkout_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="URL de Checkout"
    )
    
    # PIX data (para pagamentos via WhatsApp)
    pix_qr_code = models.TextField(
        blank=True,
        verbose_name="PIX Copia e Cola"
    )
    pix_qr_code_base64 = models.TextField(
        blank=True,
        verbose_name="QR Code PIX (base64)"
    )
    ticket_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="URL do Ticket"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expira em"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Pago em")
    
    class Meta:
        verbose_name = "Pagamento Mercado Pago"
        verbose_name_plural = "Pagamentos Mercado Pago"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"MP #{self.id} - R${self.amount} - {self.get_status_display()}"


# =============================================================================
# Modelos Cakto (Novo sistema de assinaturas)
# =============================================================================

class CaktoSubscription(models.Model):
    """
    Assinatura via Cakto Gateway.
    Gerencia o pagamento recorrente das padarias para usar o sistema.
    """
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Ativa'),
        ('inactive', 'Inativa'),
        ('cancelled', 'Cancelada'),
    ]
    
    padaria = models.OneToOneField(
        Padaria,
        on_delete=models.CASCADE,
        related_name="cakto_subscription",
        verbose_name="Padaria"
    )
    
    # Trial
    trial_days = models.IntegerField(
        default=15,
        verbose_name="Dias de Trial",
        help_text="Quantidade de dias de uso gratuito"
    )
    trial_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Início do Trial"
    )
    trial_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fim do Trial"
    )
    
    # Cakto IDs
    cakto_offer_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID da Oferta Cakto"
    )
    cakto_subscription_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID da Assinatura Cakto"
    )
    cakto_order_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name="ID do Pedido Cakto"
    )
    
    # Cartão cadastrado
    card_registered = models.BooleanField(
        default=False,
        verbose_name="Cartão Cadastrado"
    )
    card_last_4 = models.CharField(
        max_length=4,
        blank=True,
        verbose_name="Últimos 4 dígitos"
    )
    card_brand = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Bandeira"
    )
    
    # Status e datas
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial',
        verbose_name="Status"
    )
    next_billing_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Próxima Cobrança"
    )
    last_payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Último Pagamento"
    )
    
    # Valor
    plan_name = models.CharField(
        max_length=100,
        default="Plano Mensal",
        verbose_name="Nome do Plano"
    )
    plan_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=140.00,
        verbose_name="Valor do Plano (R$)"
    )
    
    # Link de checkout (quando precisa cadastrar cartão)
    checkout_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="URL de Checkout"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Cancelado em")
    
    class Meta:
        verbose_name = "Assinatura Cakto"
        verbose_name_plural = "Assinaturas Cakto"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Cakto - {self.padaria.name} ({self.get_status_display()})"
    
    @property
    def is_trial(self):
        """Verifica se está em período de trial."""
        return self.status == 'trial'
    
    @property
    def is_active(self):
        """Verifica se a assinatura está ativa (trial ou paga)."""
        return self.status in ['trial', 'active']
    
    def days_remaining(self):
        """Retorna dias restantes até próxima cobrança ou fim do trial."""
        from django.utils import timezone
        today = timezone.now().date()
        
        if self.status == 'trial' and self.trial_end_date:
            delta = self.trial_end_date - today
            return max(0, delta.days)
        elif self.status == 'active' and self.next_billing_date:
            delta = self.next_billing_date - today
            return max(0, delta.days)
        return 0
    
    def should_show_card_urgency(self):
        """Verifica se deve mostrar urgência para cadastrar cartão (3 dias ou menos)."""
        if self.status == 'trial' and not self.card_registered:
            return self.days_remaining() <= 3
        return False
    
    def start_trial(self, trial_days=None):
        """Inicia o período de trial."""
        from django.utils import timezone
        from datetime import timedelta
        
        if trial_days is not None:
            self.trial_days = trial_days
        
        today = timezone.now().date()
        self.trial_start_date = today
        self.trial_end_date = today + timedelta(days=self.trial_days)
        self.status = 'trial'
        self.save()
    
    def activate(self):
        """Ativa a assinatura após pagamento."""
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        self.status = 'active'
        self.last_payment_date = today
        self.next_billing_date = today + timedelta(days=30)
        
        # Ativar padaria
        self.padaria.is_active = True
        self.padaria.save()
        self.save()
    
    def deactivate(self):
        """Desativa a assinatura por falta de pagamento."""
        self.status = 'inactive'
        
        # Desativar padaria
        self.padaria.is_active = False
        self.padaria.save()
        self.save()
    
    def cancel(self):
        """Cancela a assinatura."""
        from django.utils import timezone
        
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        
        # Desativar padaria
        self.padaria.is_active = False
        self.padaria.save()
        self.save()


class CaktoPayment(models.Model):
    """
    Histórico de pagamentos Cakto.
    Registra cada transação de cobrança.
    """
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('approved', 'Aprovado'),
        ('rejected', 'Rejeitado'),
        ('refunded', 'Estornado'),
    ]
    
    subscription = models.ForeignKey(
        CaktoSubscription,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Assinatura"
    )
    
    # Cakto ID
    cakto_order_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="ID do Pedido Cakto"
    )
    
    # Informações do pagamento
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valor (R$)"
    )
    billing_period_start = models.DateField(
        null=True,
        blank=True,
        verbose_name="Início do Período"
    )
    billing_period_end = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fim do Período"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    error_message = models.TextField(
        blank=True,
        verbose_name="Mensagem de Erro"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Pago em")
    
    class Meta:
        verbose_name = "Pagamento Cakto"
        verbose_name_plural = "Pagamentos Cakto"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Cakto #{self.id} - R${self.amount} - {self.get_status_display()}"

