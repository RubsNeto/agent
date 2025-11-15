"""
Signals para o app agents.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Agent
import requests
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Agent)
def notify_n8n_on_update(sender, instance, created, **kwargs):
    """
    Envia o arquivo PDF para o N8N quando um agente é atualizado.
    """
    # Só notificar se o agente tem webhook configurado
    if not instance.n8n_webhook_url:
        return
    
    # Só enviar se tiver PDF
    if not instance.knowledge_pdf:
        logger.info(f"Agente {instance.slug} não tem PDF, webhook não disparado")
        return
    
    # Disparar webhook em background (não bloquear salvamento)
    try:
        # Abrir e enviar o arquivo PDF
        with instance.knowledge_pdf.open('rb') as pdf_file:
            files = {
                'file': (instance.knowledge_pdf.name, pdf_file, 'application/pdf')
            }
            
            # Enviar dados básicos como form data
            data = {
                'agent_slug': instance.slug,
                'agent_name': instance.name,
            }
            
            response = requests.post(
                instance.n8n_webhook_url,
                files=files,
                data=data,
                timeout=10
            )
        
        if response.status_code == 200:
            logger.info(f"PDF enviado com sucesso para N8N - agente {instance.slug}")
        else:
            logger.warning(f"Webhook N8N retornou status {response.status_code} para agente {instance.slug}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao enviar PDF para N8N - agente {instance.slug}: {str(e)}")
    except Exception as e:
        logger.error(f"Erro inesperado ao processar PDF para N8N - agente {instance.slug}: {str(e)}")
