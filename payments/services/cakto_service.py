"""
Cakto Gateway Service
Integração com a API da Cakto para assinaturas recorrentes.

Autenticação: OAuth2 com client_credentials
1. POST /token/ com client_id + client_secret para obter access_token
2. Usar access_token em todas as requisições subsequentes
"""
import requests
import logging
from django.conf import settings
from django.core.cache import cache
from decimal import Decimal
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cache key para o access token
CAKTO_TOKEN_CACHE_KEY = "cakto_access_token"


class CaktoService:
    """
    Serviço para integração com a API Cakto.
    
    Endpoints:
    - POST /token/ - Obter access token (OAuth2)
    - POST /offers/ - Criar oferta de assinatura
    - GET /orders/{order_id}/ - Consultar status do pedido
    """
    
    def __init__(self):
        self.client_id = settings.CAKTO_CLIENT_ID
        self.client_secret = settings.CAKTO_CLIENT_SECRET
        self.base_url = settings.CAKTO_API_URL
        self.test_mode = settings.CAKTO_TEST_MODE
        self.plan_value = settings.CAKTO_PLAN_VALUE
        self.plan_name = settings.CAKTO_PLAN_NAME
        self._access_token = None
        self._token_expires_at = None
    
    def _get_access_token(self):
        """
        Obtém access token via OAuth2.
        Faz cache do token para evitar requisições desnecessárias.
        """
        # Verificar cache primeiro
        cached_token = cache.get(CAKTO_TOKEN_CACHE_KEY)
        if cached_token:
            logger.debug("Usando token Cakto do cache")
            return cached_token
        
        # Verificar token em memória
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return self._access_token
        
        # Obter novo token
        token_url = f"{self.base_url}/token/"
        
        try:
            response = requests.post(
                token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 36000)  # Default 10 horas
                
                # Cachear token (com margem de segurança de 5 minutos)
                cache_time = max(expires_in - 300, 60)
                cache.set(CAKTO_TOKEN_CACHE_KEY, access_token, cache_time)
                
                # Salvar em memória também
                self._access_token = access_token
                self._token_expires_at = datetime.now() + timedelta(seconds=cache_time)
                
                logger.info(f"Novo token Cakto obtido, expira em {expires_in}s")
                return access_token
            else:
                logger.error(f"Erro ao obter token Cakto: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao obter token Cakto: {str(e)}")
            return None
    
    def _get_headers(self):
        """Retorna headers para requisições à API com Bearer Token."""
        access_token = self._get_access_token()
        
        if not access_token:
            logger.error("Não foi possível obter access token Cakto")
            return None
        
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def _make_request(self, method, endpoint, data=None):
        """Faz requisição à API Cakto."""
        headers = self._get_headers()
        
        if not headers:
            return {"success": False, "error": "Falha na autenticação com Cakto"}
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Método HTTP não suportado: {method}")
            
            # Log da resposta
            logger.info(f"Cakto API {method} {endpoint}: {response.status_code}")
            
            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json()}
            elif response.status_code == 401:
                # Token expirado, limpar cache e tentar novamente
                cache.delete(CAKTO_TOKEN_CACHE_KEY)
                self._access_token = None
                logger.warning("Token Cakto expirado, limpando cache")
                return {"success": False, "error": "Token expirado, tente novamente", "status_code": 401}
            else:
                logger.error(f"Cakto API error: {response.text}")
                return {"success": False, "error": response.text, "status_code": response.status_code}
                
        except requests.exceptions.Timeout:
            logger.error("Cakto API timeout")
            return {"success": False, "error": "Timeout na conexão com Cakto"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Cakto API request error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_subscription_offer(self, padaria, customer_email, customer_name=None):
        """
        Cria oferta de assinatura para cadastro de cartão.
        
        Args:
            padaria: Padaria Model instance
            customer_email: Email do cliente
            customer_name: Nome do cliente (opcional)
            
        Returns:
            dict com checkout_url e offer_id ou error
        """
        data = {
            "type": "subscription",
            "name": f"{self.plan_name} - {padaria.name}",
            "description": f"Assinatura mensal do sistema PanDia para {padaria.name}",
            "price": float(self.plan_value),
            "currency": "BRL",
            "billing_cycle": "monthly",
            "customer": {
                "email": customer_email,
                "name": customer_name or padaria.responsavel_nome or padaria.name,
            },
            "metadata": {
                "padaria_id": str(padaria.id),
                "padaria_slug": padaria.slug,
            }
        }
        
        result = self._make_request("POST", "offers/", data)
        
        if result.get("success"):
            offer_data = result.get("data", {})
            return {
                "success": True,
                "offer_id": offer_data.get("id"),
                "checkout_url": offer_data.get("checkout_url"),
                "data": offer_data
            }
        else:
            return result
    
    def get_order_status(self, order_id):
        """
        Consulta status do pedido.
        
        Args:
            order_id: ID do pedido Cakto
            
        Returns:
            dict com status e detalhes do pedido
        """
        result = self._make_request("GET", f"orders/{order_id}/")
        
        if result.get("success"):
            order_data = result.get("data", {})
            return {
                "success": True,
                "status": order_data.get("status"),
                "data": order_data
            }
        else:
            return result
    
    def process_payment_approved(self, webhook_data):
        """
        Processa evento de pagamento aprovado.
        
        Args:
            webhook_data: Dados do webhook purchase_approved
            
        Returns:
            dict com resultado do processamento
        """
        from payments.models import CaktoSubscription, CaktoPayment
        from organizations.models import Padaria
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            # Extrair dados do webhook
            order_id = webhook_data.get("order_id") or webhook_data.get("id")
            metadata = webhook_data.get("metadata", {})
            padaria_id = metadata.get("padaria_id")
            
            if not padaria_id:
                # Tentar buscar pelo order_id salvo
                try:
                    subscription = CaktoSubscription.objects.get(cakto_order_id=order_id)
                    padaria = subscription.padaria
                except CaktoSubscription.DoesNotExist:
                    logger.error(f"Padaria não encontrada para order {order_id}")
                    return {"success": False, "error": "Padaria não encontrada"}
            else:
                padaria = Padaria.objects.get(id=padaria_id)
                subscription = padaria.cakto_subscription
            
            # Registrar pagamento
            amount = Decimal(str(webhook_data.get("amount", self.plan_value)))
            today = timezone.now().date()
            
            payment, created = CaktoPayment.objects.update_or_create(
                cakto_order_id=order_id,
                defaults={
                    "subscription": subscription,
                    "amount": amount,
                    "status": "approved",
                    "paid_at": timezone.now(),
                    "billing_period_start": today,
                    "billing_period_end": today + timedelta(days=30),
                }
            )
            
            # Extrair dados do cartão se disponíveis
            card_data = webhook_data.get("card", {}) or webhook_data.get("payment_method", {})
            if card_data:
                subscription.card_registered = True
                subscription.card_last_4 = card_data.get("last4", "")[:4]
                subscription.card_brand = card_data.get("brand", "")[:20]
            
            # Ativar assinatura
            subscription.cakto_order_id = order_id
            subscription.activate()
            
            logger.info(f"Pagamento aprovado para {padaria.name} - Order {order_id}")
            
            return {"success": True, "subscription": subscription, "payment": payment}
            
        except Padaria.DoesNotExist:
            logger.error(f"Padaria {padaria_id} não encontrada")
            return {"success": False, "error": "Padaria não encontrada"}
        except Exception as e:
            logger.error(f"Erro ao processar pagamento: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def process_subscription_canceled(self, webhook_data):
        """
        Processa evento de assinatura cancelada.
        
        Args:
            webhook_data: Dados do webhook subscription_canceled
            
        Returns:
            dict com resultado do processamento
        """
        from payments.models import CaktoSubscription
        
        try:
            order_id = webhook_data.get("order_id") or webhook_data.get("subscription_id")
            
            try:
                subscription = CaktoSubscription.objects.get(cakto_order_id=order_id)
            except CaktoSubscription.DoesNotExist:
                logger.warning(f"Assinatura não encontrada para order {order_id}")
                return {"success": False, "error": "Assinatura não encontrada"}
            
            # Cancelar assinatura
            subscription.cancel()
            
            logger.info(f"Assinatura cancelada: {subscription.padaria.name}")
            
            return {"success": True, "subscription": subscription}
            
        except Exception as e:
            logger.error(f"Erro ao processar cancelamento: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def process_payment_rejected(self, webhook_data):
        """
        Processa evento de pagamento rejeitado.
        
        Args:
            webhook_data: Dados do webhook payment_rejected
            
        Returns:
            dict com resultado do processamento
        """
        from payments.models import CaktoSubscription, CaktoPayment
        
        try:
            order_id = webhook_data.get("order_id") or webhook_data.get("id")
            
            try:
                subscription = CaktoSubscription.objects.get(cakto_order_id=order_id)
            except CaktoSubscription.DoesNotExist:
                logger.warning(f"Assinatura não encontrada para order {order_id}")
                return {"success": False, "error": "Assinatura não encontrada"}
            
            # Registrar pagamento rejeitado
            amount = Decimal(str(webhook_data.get("amount", self.plan_value)))
            error_msg = webhook_data.get("error_message", "Pagamento rejeitado")
            
            CaktoPayment.objects.create(
                subscription=subscription,
                cakto_order_id=f"{order_id}_rejected_{timezone.now().timestamp()}",
                amount=amount,
                status="rejected",
                error_message=error_msg,
            )
            
            # Desativar assinatura
            subscription.deactivate()
            
            logger.warning(f"Pagamento rejeitado para {subscription.padaria.name}: {error_msg}")
            
            return {"success": True, "subscription": subscription}
            
        except Exception as e:
            logger.error(f"Erro ao processar rejeição: {str(e)}")
            return {"success": False, "error": str(e)}


# Instância global do serviço
cakto_service = CaktoService()
