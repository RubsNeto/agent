from django.db import models
from organizations.models import Padaria


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
