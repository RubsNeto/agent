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
        back_urls: Optional[Dict[str, str]] = None,
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
            back_urls: URLs de retorno (success, failure, pending)
        
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
            "auto_return": "approved",
        }
        
        # Usar back_urls personalizadas ou padrão
        if back_urls:
            data["back_urls"] = back_urls
        else:
            data["back_urls"] = {
                "success": "https://pandia.com.br/payments/mp/success/",
                "failure": "https://pandia.com.br/payments/mp/failure/",
                "pending": "https://pandia.com.br/payments/mp/pending/",
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
    
    # =========================================================================
    # Pagamento PIX Direto (para carrinho WhatsApp)
    # =========================================================================
    
    def create_pix_payment(
        self,
        amount: float,
        description: str,
        payer_email: str,
        payer_first_name: str = "Cliente",
        payer_last_name: str = "",
        payer_cpf: str = None,
        external_reference: str = None,
        expiration_minutes: int = 30,
        notification_url: str = None,
    ) -> Dict[str, Any]:
        """
        Cria pagamento PIX direto (sem redirect para checkout).
        Retorna QR Code e código copia/cola para enviar via WhatsApp.
        
        Args:
            amount: Valor em R$
            description: Descrição do pedido
            payer_email: Email do pagador (obrigatório)
            payer_first_name: Nome do pagador
            payer_last_name: Sobrenome do pagador
            payer_cpf: CPF do pagador (opcional, mas recomendado)
            external_reference: Referência externa (seu ID do pedido)
            expiration_minutes: Tempo de expiração em minutos (padrão 30)
            notification_url: URL para webhook de notificação
        
        Returns:
            Dict com:
            - 'id': ID do pagamento
            - 'status': Status (pending, approved, etc)
            - 'qr_code': Código PIX copia e cola
            - 'qr_code_base64': QR Code em base64
            - 'ticket_url': URL da página de pagamento
            - 'expires_at': Data/hora de expiração
        """
        import uuid
        from datetime import datetime, timedelta
        
        # Calcular data de expiração
        expiration = datetime.now() + timedelta(minutes=expiration_minutes)
        expiration_iso = expiration.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")
        
        data = {
            "transaction_amount": float(amount),
            "description": description,
            "payment_method_id": "pix",
            "payer": {
                "email": payer_email,
                "first_name": payer_first_name,
                "last_name": payer_last_name,
            },
            "date_of_expiration": expiration_iso,
        }
        
        # Adicionar CPF se fornecido
        if payer_cpf:
            # Limpar CPF (só números)
            cpf_clean = ''.join(filter(str.isdigit, payer_cpf))
            if len(cpf_clean) == 11:
                data["payer"]["identification"] = {
                    "type": "CPF",
                    "number": cpf_clean
                }
        
        if external_reference:
            data["external_reference"] = external_reference
        
        if notification_url:
            data["notification_url"] = notification_url
        
        # Headers especiais para pagamentos (precisa de idempotency key)
        idempotency_key = str(uuid.uuid4())
        
        # Fazer request diretamente com header extra
        url = f"{self.api_url}/v1/payments"
        headers = {
            **self.headers,
            "X-Idempotency-Key": idempotency_key,
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            logger.info(f"MercadoPago PIX payment: {response.status_code}")
            
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                logger.error(f"MercadoPago PIX error: {error_data}")
                raise MercadoPagoAPIError(
                    message=error_data.get("message", str(error_data)),
                    status_code=response.status_code,
                    response=error_data
                )
            
            result = response.json()
            
            # Extrair dados do PIX da resposta
            transaction_data = result.get("point_of_interaction", {}).get("transaction_data", {})
            
            return {
                "id": result.get("id"),
                "status": result.get("status"),
                "qr_code": transaction_data.get("qr_code", ""),
                "qr_code_base64": transaction_data.get("qr_code_base64", ""),
                "ticket_url": result.get("ticket_url", ""),
                "expires_at": result.get("date_of_expiration"),
                "raw_response": result,
            }
            
        except requests.exceptions.Timeout:
            logger.error("MercadoPago PIX timeout")
            raise MercadoPagoAPIError("Timeout na requisição ao Mercado Pago")
        except requests.exceptions.RequestException as e:
            logger.error(f"MercadoPago PIX request error: {e}")
            raise MercadoPagoAPIError(f"Erro de conexão: {str(e)}")


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
