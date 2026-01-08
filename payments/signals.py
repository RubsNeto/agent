"""
Signals para criação automática de assinatura quando uma padaria é criada.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from organizations.models import Padaria
from .models import AsaasSubscription


@receiver(post_save, sender=Padaria)
def create_subscription_on_padaria_create(sender, instance, created, **kwargs):
    """
    Cria automaticamente uma assinatura quando uma nova padaria é criada.
    """
    if created:
        # Verificar se já existe assinatura (evita duplicação)
        if not AsaasSubscription.objects.filter(padaria=instance).exists():
            AsaasSubscription.objects.create(
                padaria=instance,
                plan_name='Plano Único',
                plan_value=getattr(settings, 'ASAAS_SUBSCRIPTION_VALUE', 0),
                status='pending',
            )
