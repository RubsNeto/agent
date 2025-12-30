"""
Serviço de envio de campanhas WhatsApp com delay.
Inspirado no Astra Campaign Open Source para evitar ban no número.

Implementa:
- Delay aleatório entre mensagens
- Envio em lotes com pausas
- Tratamento de erros
- Logging de status
"""

import time
import random
import logging
import threading
import requests
import base64
import os
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Armazena campanhas em execução (para pausar/cancelar)
campanhas_em_execucao = {}


class CampaignService:
    """
    Serviço para envio de mensagens de campanha via Evolution API.
    Implementa delays e lotes para evitar ban no WhatsApp.
    """
    
    def __init__(self, campanha):
        self.campanha = campanha
        self.padaria = campanha.padaria
        self.api_url = getattr(settings, 'EVOLUTION_API_URL', None)
        self.api_key = getattr(settings, 'EVOLUTION_API_KEY', None)
        self.instance_name = f"padaria_{self.padaria.slug}"
        self._stop_requested = False
    
    def is_configured(self):
        """Verifica se a API está configurada."""
        return bool(self.api_url and self.api_key)
    
    def get_headers(self):
        """Retorna headers para a API."""
        return {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }
    
    def verificar_conexao(self):
        """Verifica se o WhatsApp está conectado."""
        if not self.is_configured():
            return False, "Evolution API não configurada"
        
        try:
            url = f"{self.api_url}/instance/connectionState/{self.instance_name}"
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                state = data.get("state") or data.get("instance", {}).get("state")
                if state == "open":
                    return True, "Conectado"
                return False, f"WhatsApp não conectado (estado: {state})"
            
            return False, f"Erro ao verificar conexão: {response.status_code}"
        except Exception as e:
            logger.error(f"Erro ao verificar conexão WhatsApp: {e}")
            return False, str(e)
    
    def enviar_mensagem_texto(self, telefone, mensagem):
        """
        Envia mensagem de texto via Evolution API.
        
        Args:
            telefone: Número no formato 5511999999999
            mensagem: Texto da mensagem
            
        Returns:
            (sucesso: bool, mensagem_erro: str ou None)
        """
        if not self.is_configured():
            return False, "Evolution API não configurada"
        
        try:
            url = f"{self.api_url}/message/sendText/{self.instance_name}"
            payload = {
                "number": telefone,
                "text": mensagem
            }
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                return True, None
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("message", response.text or "Erro desconhecido")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            return False, "Timeout ao enviar mensagem"
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return False, str(e)
    
    def enviar_mensagem_imagem(self, telefone, imagem_base64, legenda="", mimetype="image/jpeg"):
        """
        Envia imagem com legenda via Evolution API.
        
        Args:
            telefone: Número no formato 5511999999999
            imagem_base64: Imagem em base64
            legenda: Texto opcional
            mimetype: Tipo MIME da imagem
            
        Returns:
            (sucesso: bool, mensagem_erro: str ou None)
        """
        if not self.is_configured():
            return False, "Evolution API não configurada"
        
        try:
            url = f"{self.api_url}/message/sendMedia/{self.instance_name}"
            payload = {
                "number": telefone,
                "mediatype": "image",
                "media": imagem_base64,
                "mimetype": mimetype,
                "caption": legenda
            }
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=60
            )
            
            if response.status_code in [200, 201]:
                return True, None
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("message", response.text or "Erro desconhecido")
                return False, str(error_msg)
                
        except requests.exceptions.Timeout:
            return False, "Timeout ao enviar imagem"
        except Exception as e:
            logger.error(f"Erro ao enviar imagem: {e}")
            return False, str(e)
    
    def converter_imagem_para_base64(self, imagem_field):
        """
        Converte um ImageField do Django para base64.
        
        Args:
            imagem_field: Campo ImageField do modelo
            
        Returns:
            (base64_string, mimetype) ou (None, None) se falhar
        """
        try:
            # Obter o caminho completo do arquivo
            caminho_arquivo = imagem_field.path
            
            if not os.path.exists(caminho_arquivo):
                logger.error(f"Arquivo de imagem não encontrado: {caminho_arquivo}")
                return None, None
            
            # Determinar o mimetype baseado na extensão
            extensao = os.path.splitext(caminho_arquivo)[1].lower()
            mimetypes = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            mimetype = mimetypes.get(extensao, 'image/jpeg')
            
            # Ler e converter para base64
            with open(caminho_arquivo, 'rb') as f:
                imagem_bytes = f.read()
                imagem_base64 = base64.b64encode(imagem_bytes).decode('utf-8')
            
            # Retornar no formato data URI
            data_uri = f"data:{mimetype};base64,{imagem_base64}"
            return data_uri, mimetype
            
        except Exception as e:
            logger.error(f"Erro ao converter imagem para base64: {e}")
            return None, None
    
    def personalizar_mensagem(self, mensagem, cliente):
        """Substitui placeholders na mensagem."""
        texto = mensagem
        texto = texto.replace("{{nome_cliente}}", cliente.nome)
        texto = texto.replace("{{nome}}", cliente.nome.split()[0])  # Primeiro nome
        texto = texto.replace("{{padaria}}", self.padaria.name)
        return texto
    
    def pausar(self):
        """Solicita pausa na campanha."""
        self._stop_requested = True
    
    def executar_campanha(self, async_mode=True):
        """
        Executa o envio da campanha.
        
        Args:
            async_mode: Se True, executa em thread separada
        """
        if async_mode:
            thread = threading.Thread(target=self._executar_envios)
            thread.daemon = True
            thread.start()
            campanhas_em_execucao[self.campanha.id] = self
            return True
        else:
            return self._executar_envios()
    
    def _executar_envios(self):
        """Execução interna dos envios com delay."""
        from .models import MensagemCampanha
        
        campanha = self.campanha
        
        # Atualizar status
        campanha.status = 'enviando'
        campanha.iniciado_em = timezone.now()
        campanha.save()
        
        logger.info(f"[Campanha {campanha.id}] Iniciando envio para {campanha.total_destinatarios} destinatários")
        
        # Buscar mensagens pendentes
        mensagens = MensagemCampanha.objects.filter(
            campanha=campanha,
            status='pendente'
        ).select_related('cliente')
        
        contador_lote = 0
        
        for msg in mensagens:
            # Verificar se deve parar
            if self._stop_requested:
                campanha.status = 'pausada'
                campanha.save()
                logger.info(f"[Campanha {campanha.id}] Pausada pelo usuário")
                break
            
            cliente = msg.cliente
            telefone = cliente.get_telefone_whatsapp()
            texto_personalizado = self.personalizar_mensagem(campanha.mensagem, cliente)
            
            # Atualizar status para enviando
            msg.status = 'enviando'
            msg.save()
            
            # Enviar mensagem
            if campanha.imagem:
                # Se tem imagem, converter para base64 e enviar com legenda
                imagem_base64, mimetype = self.converter_imagem_para_base64(campanha.imagem)
                
                if imagem_base64:
                    sucesso, erro = self.enviar_mensagem_imagem(telefone, imagem_base64, texto_personalizado, mimetype)
                else:
                    # Falha ao converter imagem, enviar apenas texto
                    logger.warning(f"[Campanha {campanha.id}] Falha ao converter imagem, enviando apenas texto")
                    sucesso, erro = self.enviar_mensagem_texto(telefone, texto_personalizado)
            else:
                # Apenas texto
                sucesso, erro = self.enviar_mensagem_texto(telefone, texto_personalizado)
            
            # Atualizar resultado
            if sucesso:
                msg.status = 'enviado'
                msg.enviado_em = timezone.now()
                campanha.enviados += 1
                logger.info(f"[Campanha {campanha.id}] Mensagem enviada para {cliente.nome} ({telefone})")
            else:
                msg.status = 'falha'
                msg.erro_mensagem = erro or "Erro desconhecido"
                campanha.falhas += 1
                logger.warning(f"[Campanha {campanha.id}] Falha ao enviar para {cliente.nome}: {erro}")
            
            msg.save()
            campanha.save()
            
            contador_lote += 1
            
            # Delay entre mensagens (anti-ban)
            delay = campanha.get_delay_aleatorio()
            logger.debug(f"[Campanha {campanha.id}] Aguardando {delay}s antes da próxima mensagem")
            time.sleep(delay)
            
            # Pausa maior entre lotes
            if contador_lote >= campanha.lote_tamanho:
                logger.info(f"[Campanha {campanha.id}] Lote concluído, pausando {campanha.pausa_entre_lotes}s")
                time.sleep(campanha.pausa_entre_lotes)
                contador_lote = 0
        
        # Finalizar campanha
        if not self._stop_requested:
            campanha.status = 'concluida'
            campanha.concluido_em = timezone.now()
            campanha.save()
            logger.info(f"[Campanha {campanha.id}] Concluída! Enviados: {campanha.enviados}, Falhas: {campanha.falhas}")
        
        # Remover da lista de campanhas em execução
        if campanha.id in campanhas_em_execucao:
            del campanhas_em_execucao[campanha.id]
        
        return True


def criar_campanha_promocao(promocao, mensagem_personalizada=None):
    """
    Cria uma campanha a partir de uma promoção.
    
    Args:
        promocao: Instância de Promocao
        mensagem_personalizada: Mensagem customizada (opcional)
    
    Returns:
        CampanhaWhatsApp: Campanha criada
    """
    from .models import CampanhaWhatsApp, MensagemCampanha, Cliente
    
    padaria = promocao.padaria
    
    # Montar mensagem padrão se não fornecida
    if not mensagem_personalizada:
        mensagem = f"""🎉 *PROMOÇÃO ESPECIAL* 🎉

Olá, {{{{nome}}}}! 

*{promocao.titulo}*

{promocao.descricao}

"""
        if promocao.preco_original and promocao.preco:
            desconto = promocao.get_discount_percentage()
            mensagem += f"💰 De R$ {promocao.preco_original:.2f} por apenas *R$ {promocao.preco:.2f}*"
            if desconto:
                mensagem += f" ({int(desconto)}% OFF!)"
            mensagem += "\n\n"
        elif promocao.preco:
            mensagem += f"💰 Apenas *R$ {promocao.preco:.2f}*\n\n"
        
        if promocao.data_fim:
            mensagem += f"⏰ Válido até {promocao.data_fim.strftime('%d/%m/%Y')}\n\n"
        
        mensagem += f"📍 {padaria.name}\n"
        mensagem += "Venha conferir! 🥐🍞"
    else:
        mensagem = mensagem_personalizada
    
    # Criar campanha
    campanha = CampanhaWhatsApp.objects.create(
        padaria=padaria,
        promocao=promocao,
        nome=f"Promoção: {promocao.titulo}",
        mensagem=mensagem,
        imagem=promocao.imagem if promocao.imagem else None,
        delay_minimo=15,
        delay_maximo=45,
        lote_tamanho=10,
        pausa_entre_lotes=120,
        status='rascunho'
    )
    
    # Adicionar clientes que aceitam promoções
    clientes = Cliente.objects.filter(
        padaria=padaria,
        is_active=True,
        aceita_promocoes=True
    )
    
    for cliente in clientes:
        MensagemCampanha.objects.create(
            campanha=campanha,
            cliente=cliente,
            status='pendente'
        )
    
    campanha.total_destinatarios = clientes.count()
    campanha.save()
    
    return campanha


def pausar_campanha(campanha_id):
    """Pausa uma campanha em execução."""
    if campanha_id in campanhas_em_execucao:
        campanhas_em_execucao[campanha_id].pausar()
        return True
    return False


def retomar_campanha(campanha):
    """Retoma uma campanha pausada."""
    if campanha.status != 'pausada':
        return False, "Campanha não está pausada"
    
    service = CampaignService(campanha)
    conectado, msg = service.verificar_conexao()
    
    if not conectado:
        return False, f"WhatsApp não conectado: {msg}"
    
    service.executar_campanha(async_mode=True)
    return True, "Campanha retomada"
