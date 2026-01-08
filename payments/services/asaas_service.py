"""
Serviço para integração com API do Asaas.
Gerencia clientes, assinaturas e cobranças.
"""
import requests
import logging
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class AsaasService:
    """
    Serviço para comunicação com a API do Asaas.
    Documentação: https://docs.asaas.com/
    """
    
    def __init__(self):
        self.api_key = settings.ASAAS_API_KEY
        self.api_url = settings.ASAAS_API_URL
        self.headers = {
            "Content-Type": "application/json",
            "access_token": self.api_key,
        }
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Faz uma requisição à API do Asaas.
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
            
            # Log da requisição
            logger.info(f"Asaas {method} {endpoint}: {response.status_code}")
            
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                logger.error(f"Asaas error: {error_data}")
                raise AsaasAPIError(
                    message=error_data.get("errors", [{}])[0].get("description", "Erro desconhecido"),
                    status_code=response.status_code,
                    response=error_data
                )
            
            return response.json() if response.content else {}
            
        except requests.exceptions.Timeout:
            logger.error(f"Asaas timeout: {endpoint}")
            raise AsaasAPIError("Timeout na requisição ao Asaas")
        except requests.exceptions.RequestException as e:
            logger.error(f"Asaas request error: {e}")
            raise AsaasAPIError(f"Erro de conexão: {str(e)}")
    
    # =========================================================================
    # Clientes
    # =========================================================================
    
    def create_customer(
        self,
        name: str,
        email: str,
        cpf_cnpj: Optional[str] = None,
        phone: Optional[str] = None,
        external_reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cria um novo cliente no Asaas.
        
        Returns:
            Dict com dados do cliente, incluindo 'id' (asaas_customer_id)
        """
        data = {
            "name": name,
            "email": email,
        }
        
        if cpf_cnpj:
            data["cpfCnpj"] = cpf_cnpj
        if phone:
            data["phone"] = phone
        if external_reference:
            data["externalReference"] = external_reference
        
        return self._request("POST", "customers", data)
    
    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Busca dados de um cliente pelo ID."""
        return self._request("GET", f"customers/{customer_id}")
    
    def find_customer_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Busca cliente pelo email."""
        result = self._request("GET", f"customers?email={email}")
        customers = result.get("data", [])
        return customers[0] if customers else None
    
    # =========================================================================
    # Assinaturas
    # =========================================================================
    
    def create_subscription(
        self,
        customer_id: str,
        billing_type: str = "PIX",
        value: float = None,
        cycle: str = None,
        description: str = "Assinatura Pandia",
        next_due_date: str = None,
    ) -> Dict[str, Any]:
        """
        Cria uma assinatura recorrente para o cliente.
        
        Args:
            customer_id: ID do cliente no Asaas
            billing_type: PIX, CREDIT_CARD ou BOLETO
            value: Valor da assinatura (usa settings se não informado)
            cycle: Ciclo de cobrança (MONTHLY, WEEKLY, etc)
            description: Descrição da assinatura
            next_due_date: Data do primeiro vencimento (YYYY-MM-DD)
        
        Returns:
            Dict com dados da assinatura, incluindo 'id' (asaas_subscription_id)
        """
        if value is None:
            value = settings.ASAAS_SUBSCRIPTION_VALUE
        if cycle is None:
            cycle = settings.ASAAS_SUBSCRIPTION_CYCLE
        if next_due_date is None:
            # Próximo mês
            next_due_date = (timezone.now() + timezone.timedelta(days=30)).strftime("%Y-%m-%d")
        
        data = {
            "customer": customer_id,
            "billingType": billing_type,
            "value": value,
            "cycle": cycle,
            "description": description,
            "nextDueDate": next_due_date,
        }
        
        return self._request("POST", "subscriptions", data)
    
    def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Busca dados de uma assinatura."""
        return self._request("GET", f"subscriptions/{subscription_id}")
    
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancela uma assinatura."""
        return self._request("DELETE", f"subscriptions/{subscription_id}")
    
    def get_subscription_payments(self, subscription_id: str) -> Dict[str, Any]:
        """Lista pagamentos de uma assinatura."""
        return self._request("GET", f"subscriptions/{subscription_id}/payments")
    
    # =========================================================================
    # Cobranças/Pagamentos
    # =========================================================================
    
    def create_payment(
        self,
        customer_id: str,
        billing_type: str,
        value: float,
        due_date: str,
        description: str = "Cobrança Pandia",
    ) -> Dict[str, Any]:
        """
        Cria uma cobrança avulsa.
        
        Returns:
            Dict com dados da cobrança, incluindo 'invoiceUrl' e 'id'
        """
        data = {
            "customer": customer_id,
            "billingType": billing_type,
            "value": value,
            "dueDate": due_date,
            "description": description,
        }
        
        return self._request("POST", "payments", data)
    
    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """Busca dados de um pagamento."""
        return self._request("GET", f"payments/{payment_id}")
    
    def get_payment_pix_qrcode(self, payment_id: str) -> Dict[str, Any]:
        """
        Obtém o QR Code PIX para pagamento.
        
        Returns:
            Dict com 'encodedImage' (base64), 'payload' (copia e cola), 'expirationDate'
        """
        return self._request("GET", f"payments/{payment_id}/pixQrCode")
    
    def get_payment_invoice_url(self, payment_id: str) -> str:
        """Retorna a URL da fatura para pagamento."""
        payment = self.get_payment(payment_id)
        return payment.get("invoiceUrl", "")


class AsaasAPIError(Exception):
    """Exceção para erros da API do Asaas."""
    
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


# Instância singleton para uso em views/signals
asaas_service = AsaasService()
