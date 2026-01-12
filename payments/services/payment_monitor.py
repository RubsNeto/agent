"""
Serviço de Polling para monitorar status de pagamentos do Mercado Pago.
Verifica periodicamente se os pagamentos pendentes foram aprovados.
"""
import threading
import time
import logging
from typing import Optional, Dict, Set
from django.utils import timezone
from django.db import connection

logger = logging.getLogger(__name__)

# Armazena os IDs dos pagamentos sendo monitorados
_active_monitors: Dict[int, threading.Thread] = {}
_monitor_lock = threading.Lock()


class PaymentMonitor:
    """
    Monitor individual para um pagamento.
    Verifica o status periodicamente até ser aprovado, rejeitado ou expirar.
    """
    
    def __init__(
        self,
        payment_id: int,
        external_reference: str,
        access_token: str,
        check_interval: int = 5,  # segundos entre cada verificação
        max_duration: int = 600,  # duração máxima do monitoramento (10 minutos)
        on_status_change: Optional[callable] = None
    ):
        self.payment_id = payment_id
        self.external_reference = external_reference
        self.access_token = access_token
        self.check_interval = check_interval
        self.max_duration = max_duration
        self.on_status_change = on_status_change
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Inicia o monitoramento em uma thread separada."""
        if self._thread and self._thread.is_alive():
            logger.warning(f"Monitor para pagamento {self.payment_id} já está rodando")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name=f"PaymentMonitor-{self.payment_id}",
            daemon=True
        )
        self._thread.start()
        logger.info(f"Monitor iniciado para pagamento {self.payment_id}")
    
    def stop(self):
        """Para o monitoramento."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info(f"Monitor parado para pagamento {self.payment_id}")
    
    def _monitor_loop(self):
        """Loop principal de monitoramento."""
        from payments.services.mercadopago_service import MercadoPagoService
        from payments.models import MercadoPagoPayment
        
        start_time = time.time()
        check_count = 0
        
        try:
            mp_service = MercadoPagoService(self.access_token)
            
            while not self._stop_event.is_set():
                # Verificar se excedeu o tempo máximo
                elapsed = time.time() - start_time
                if elapsed > self.max_duration:
                    logger.info(f"Monitor {self.payment_id}: tempo máximo atingido ({self.max_duration}s)")
                    break
                
                check_count += 1
                logger.debug(f"Monitor {self.payment_id}: verificação #{check_count}")
                
                try:
                    # Fechar conexão antiga e abrir nova para evitar problemas de thread
                    connection.close()
                    
                    # Buscar pagamento no banco
                    try:
                        payment = MercadoPagoPayment.objects.get(id=self.payment_id)
                    except MercadoPagoPayment.DoesNotExist:
                        logger.warning(f"Monitor {self.payment_id}: pagamento não existe mais")
                        break
                    
                    # Se já não está pendente, parar
                    if payment.status != 'pending':
                        logger.info(f"Monitor {self.payment_id}: status já é {payment.status}, parando")
                        break
                    
                    # Buscar status no Mercado Pago
                    old_status = payment.status
                    new_status = None
                    mp_payment_id = None
                    
                    # Tentar por mp_payment_id primeiro (mais rápido)
                    if payment.mp_payment_id:
                        try:
                            mp_data = mp_service.get_payment(payment.mp_payment_id)
                            if mp_data:
                                new_status = mp_data.get('status')
                                mp_payment_id = str(mp_data.get('id', ''))
                        except Exception as e:
                            logger.debug(f"Monitor {self.payment_id}: erro ao buscar por mp_id: {e}")
                    
                    # Se não encontrou, buscar por external_reference
                    if not new_status and self.external_reference:
                        try:
                            search_result = mp_service.search_payments(
                                external_reference=self.external_reference,
                                limit=5
                            )
                            for result in search_result.get('results', []):
                                if result.get('external_reference') == self.external_reference:
                                    new_status = result.get('status')
                                    mp_payment_id = str(result.get('id', ''))
                                    break
                        except Exception as e:
                            logger.debug(f"Monitor {self.payment_id}: erro ao buscar por external_ref: {e}")
                    
                    # Se encontrou status diferente, atualizar
                    if new_status and new_status != old_status:
                        logger.info(f"Monitor {self.payment_id}: status mudou {old_status} -> {new_status}")
                        
                        # Atualizar no banco
                        payment.status = new_status
                        if mp_payment_id:
                            payment.mp_payment_id = mp_payment_id
                        if new_status == 'approved':
                            payment.paid_at = timezone.now()
                        payment.save()
                        
                        # Callback se definido
                        if self.on_status_change:
                            try:
                                self.on_status_change(self.payment_id, old_status, new_status)
                            except Exception as e:
                                logger.error(f"Erro no callback: {e}")
                        
                        # Se foi aprovado ou rejeitado, parar monitoramento
                        if new_status in ['approved', 'rejected', 'cancelled', 'refunded']:
                            logger.info(f"Monitor {self.payment_id}: status final {new_status}, parando")
                            break
                    
                except Exception as e:
                    logger.error(f"Monitor {self.payment_id}: erro na verificação: {e}")
                
                # Aguardar intervalo
                self._stop_event.wait(self.check_interval)
                
        except Exception as e:
            logger.exception(f"Monitor {self.payment_id}: erro fatal: {e}")
        finally:
            # Remover da lista de monitores ativos
            with _monitor_lock:
                if self.payment_id in _active_monitors:
                    del _active_monitors[self.payment_id]
            
            # Fechar conexão
            connection.close()
            logger.info(f"Monitor {self.payment_id}: finalizado após {check_count} verificações")


def start_payment_monitor(
    payment_id: int,
    external_reference: str,
    access_token: str,
    check_interval: int = 5,
    max_duration: int = 600
) -> bool:
    """
    Inicia o monitoramento de um pagamento.
    
    Args:
        payment_id: ID interno do pagamento
        external_reference: Referência externa (pandia_xxx_yyy)
        access_token: Token do Mercado Pago
        check_interval: Intervalo entre verificações em segundos (default: 5)
        max_duration: Duração máxima do monitoramento em segundos (default: 600 = 10 min)
    
    Returns:
        True se iniciou o monitoramento, False se já estava ativo
    """
    with _monitor_lock:
        if payment_id in _active_monitors:
            thread = _active_monitors[payment_id]
            if thread.is_alive():
                logger.info(f"Monitor para pagamento {payment_id} já está ativo")
                return False
    
    monitor = PaymentMonitor(
        payment_id=payment_id,
        external_reference=external_reference,
        access_token=access_token,
        check_interval=check_interval,
        max_duration=max_duration
    )
    
    with _monitor_lock:
        _active_monitors[payment_id] = monitor._thread
    
    monitor.start()
    return True


def stop_payment_monitor(payment_id: int) -> bool:
    """
    Para o monitoramento de um pagamento.
    
    Returns:
        True se parou, False se não estava ativo
    """
    with _monitor_lock:
        if payment_id not in _active_monitors:
            return False
        
        # O monitor se remove sozinho quando para
        return True


def get_active_monitors() -> Set[int]:
    """Retorna IDs dos pagamentos sendo monitorados."""
    with _monitor_lock:
        return set(_active_monitors.keys())


def start_bulk_payment_monitor(padaria_slug: str, max_duration: int = 300) -> int:
    """
    Inicia monitoramento para todos os pagamentos pendentes de uma padaria.
    
    Args:
        padaria_slug: Slug da padaria
        max_duration: Duração máxima por pagamento (default: 5 min)
    
    Returns:
        Número de monitores iniciados
    """
    from payments.models import MercadoPagoPayment, MercadoPagoConfig
    from organizations.models import Padaria
    
    try:
        padaria = Padaria.objects.get(slug=padaria_slug)
        mp_config = padaria.mercadopago_config
        
        if not mp_config or not mp_config.access_token:
            logger.warning(f"Padaria {padaria_slug} não tem MP configurado")
            return 0
        
        # Buscar pagamentos pendentes
        pending_payments = MercadoPagoPayment.objects.filter(
            config=mp_config,
            status='pending'
        ).order_by('-created_at')[:20]  # Limita a 20 para não sobrecarregar
        
        count = 0
        for payment in pending_payments:
            external_ref = payment.pix_qr_code if payment.pix_qr_code and payment.pix_qr_code.startswith('pandia_') else None
            if external_ref:
                if start_payment_monitor(
                    payment_id=payment.id,
                    external_reference=external_ref,
                    access_token=mp_config.access_token,
                    max_duration=max_duration
                ):
                    count += 1
        
        logger.info(f"Iniciados {count} monitores para padaria {padaria_slug}")
        return count
        
    except Exception as e:
        logger.exception(f"Erro ao iniciar monitores para {padaria_slug}: {e}")
        return 0
