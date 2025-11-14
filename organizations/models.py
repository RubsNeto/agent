import secrets
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class Organization(models.Model):
    """
    Organização (empresa/salão).
    """
    name = models.CharField(max_length=200, verbose_name="Nome")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="Slug")
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_organizations",
        verbose_name="Proprietário"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Organização"
        verbose_name_plural = "Organizações"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ApiKey(models.Model):
    """
    Chave de API para autenticação de integrações (n8n).
    """
    key = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Chave")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="api_keys",
        verbose_name="Organização"
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
        return f"{self.organization.name} - {self.key[:12]}..."

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = f"sk_{secrets.token_urlsafe(32)}"
        super().save(*args, **kwargs)

    @staticmethod
    def generate_key():
        """Gera uma nova chave única."""
        return f"sk_{secrets.token_urlsafe(32)}"
