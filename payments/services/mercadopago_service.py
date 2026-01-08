"""
Serviço para integração com API do Mercado Pago.
Gerencia criação de links de pagamento e consultas.
"""
import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class MercadoPagoService:
    """
    Serviço para comunicação com a API do Mercado Pago.
    Cada padaria tem suas próprias credenciais.
    Documentação: https://www.mercadopago.com.br/developers/
    """
    
    def __init__(self, access_token: str):
        """
        Inicializa o serviço com o access_token da padaria.
        
        Args:
            access_token: Token de acesso do Mercado Pago da padaria
        """
        self.access_token = access_token
        self.api_url = "https://api.mercadopago.com"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Faz uma requisição à API do Mercado Pago.
        """
        url = f"{self.api_url}/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=30
            )
            
            logger.info(f"MercadoPago {method} {endpoint}: {response.status_code}")
            
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                logger.error(f"MercadoPago error: {error_data}")
                raise MercadoPagoAPIError(
                    message=error_data.get("message", "Erro desconhecido"),
                    status_code=response.status_code,
                    response=error_data
                )
            
            return response.json() if response.content else {}
            
        except requests.exceptions.Timeout:
            logger.error(f"MercadoPago timeout: {endpoint}")
            raise MercadoPagoAPIError("Timeout na requisição ao Mercado Pago")
        except requests.exceptions.RequestException as e:
            logger.error(f"MercadoPago request error: {e}")
            raise MercadoPagoAPIError(f"Erro de conexão: {str(e)}")
    
    # =========================================================================
    # Verificação de credenciais
    # =========================================================================
    
    def test_credentials(self) -> Dict[str, Any]:
        """
        Testa se as credenciais são válidas.
        
        Returns:
            Dict com informações do usuário se válido
        
        Raises:
            MercadoPagoAPIError se inválido
        """
        return self._request("GET", "users/me")
    
    # =========================================================================
    # Preferências de Pagamento (Checkout Pro)
    # =========================================================================
    
    def create_preference(
        self,
        title: str,
        amount: float,
        description: str = "",
        payer_email: Optional[str] = None,
        external_reference: Optional[str] = None,
        notification_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cria uma preferência de pagamento (link de checkout).
        
        Args:
            title: Título do produto/serviço
            amount: Valor em R$
            description: Descrição opcional
            payer_email: Email do pagador (pré-preenche no checkout)
            external_reference: Referência externa (seu ID)
            notification_url: URL para webhook de notificação
        
        Returns:
            Dict com 'id', 'init_point' (URL do checkout), 'sandbox_init_point'
        """
        data = {
            "items": [
                {
                    "title": title,
                    "quantity": 1,
                    "unit_price": float(amount),
                    "currency_id": "BRL",
                }
            ],
            "back_urls": {
                "success": "https://pandia.com.br/payments/mp/success/",
                "failure": "https://pandia.com.br/payments/mp/failure/",
                "pending": "https://pandia.com.br/payments/mp/pending/",
            },
            "auto_return": "approved",
        }
        
        if description:
            data["items"][0]["description"] = description
        
        if payer_email:
            data["payer"] = {"email": payer_email}
        
        if external_reference:
            data["external_reference"] = external_reference
        
        if notification_url:
            data["notification_url"] = notification_url
        
        return self._request("POST", "checkout/preferences", data)
    
    def get_preference(self, preference_id: str) -> Dict[str, Any]:
        """Busca dados de uma preferência."""
        return self._request("GET", f"checkout/preferences/{preference_id}")
    
    # =========================================================================
    # Pagamentos
    # =========================================================================
    
    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Busca dados de um pagamento pelo ID.
        
        Returns:
            Dict com 'id', 'status', 'status_detail', 'transaction_amount', etc
        """
        return self._request("GET", f"v1/payments/{payment_id}")
    
    def search_payments(
        self, 
        external_reference: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Busca pagamentos com filtros.
        
        Args:
            external_reference: Filtra por referência externa
            status: Filtra por status (approved, pending, rejected, etc)
            limit: Limite de resultados
        
        Returns:
            Dict com 'results' (lista de pagamentos)
        """
        params = [f"limit={limit}"]
        
        if external_reference:
            params.append(f"external_reference={external_reference}")
        if status:
            params.append(f"status={status}")
        
        query_string = "&".join(params)
        return self._request("GET", f"v1/payments/search?{query_string}")


class MercadoPagoAPIError(Exception):
    """Exceção para erros da API do Mercado Pago."""
    
    def __init__(
        self, 
        message: str, 
        status_code: int = None, 
        response: Dict = None
    ):
        self.message = message
        self.status_code = status_code
        self.response = response or {}
        super().__init__(self.message)


def get_mp_service(padaria) -> MercadoPagoService:
    """
    Factory para criar instância do serviço MP para uma padaria.
    
    Args:
        padaria: Instância do model Padaria
    
    Returns:
        MercadoPagoService configurado
    
    Raises:
        ValueError se a padaria não tiver configuração MP
    """
    try:
        mp_config = padaria.mercadopago_config
        if not mp_config.access_token:
            raise ValueError("Mercado Pago não configurado para esta padaria")
        return MercadoPagoService(mp_config.access_token)
    except AttributeError:
        raise ValueError("Mercado Pago não configurado para esta padaria")
