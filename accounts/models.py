from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """
    Perfil estendido do usuário.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
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
