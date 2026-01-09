"""
API Views para integração de pagamentos.
Endpoints para agentes de IA (WhatsApp) criar pagamentos PIX.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from organizations.models import Padaria
from payments.models import MercadoPagoConfig, MercadoPagoPayment
from payments.services.mercadopago_service import MercadoPagoService, MercadoPagoAPIError

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def create_cart_payment(request):
    """
    Cria pagamento PIX para carrinho de compras via WhatsApp.
    
    POST /api/payments/cart/
    
    Headers:
        Content-Type: application/json
        X-API-Key: (opcional, para autenticação futura)
    
    Body:
    {
        "padaria_slug": "bela-milao",
        "items": [
            {"name": "Pão Francês", "quantity": 10, "unit_price": 0.50},
            {"name": "Bolo de Chocolate", "quantity": 1, "unit_price": 25.00}
        ],
        "customer": {
            "name": "João Silva",
            "email": "joao@email.com",
            "phone": "11999999999",
            "cpf": "12345678900"  // opcional
        },
        "expiration_minutes": 30  // opcional, padrão 30
    }
    
    Response (success):
    {
        "success": true,
        "payment_id": "12345",
        "order_id": "order_123",
        "total": 30.00,
        "items_count": 2,
        "pix": {
            "qr_code": "00020126...",
            "qr_code_base64": "iVBORw0...",
            "ticket_url": "https://..."
        },
        "expires_at": "2026-01-09T11:00:00Z",
        "message": "Pagamento criado com sucesso"
    }
    
    Response (error):
    {
        "success": false,
        "error": "Descrição do erro"
    }
    """
    try:
        # Parse do body JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "JSON inválido no body da requisição"
            }, status=400)
        
        # Validar campos obrigatórios
        padaria_slug = data.get("padaria_slug")
        items = data.get("items", [])
        customer = data.get("customer", {})
        expiration_minutes = data.get("expiration_minutes", 30)
        
        if not padaria_slug:
            return JsonResponse({
                "success": False,
                "error": "Campo 'padaria_slug' é obrigatório"
            }, status=400)
        
        if not items:
            return JsonResponse({
                "success": False,
                "error": "Campo 'items' é obrigatório e deve ter pelo menos 1 item"
            }, status=400)
        
        customer_email = customer.get("email")
        if not customer_email:
            return JsonResponse({
                "success": False,
                "error": "Campo 'customer.email' é obrigatório"
            }, status=400)
        
        # Buscar padaria
        try:
            padaria = Padaria.objects.get(slug=padaria_slug)
        except Padaria.DoesNotExist:
            return JsonResponse({
                "success": False,
                "error": f"Padaria '{padaria_slug}' não encontrada"
            }, status=404)
        
        # Verificar se padaria tem Mercado Pago configurado
        try:
            mp_config = padaria.mercadopago_config
            if not mp_config.access_token:
                return JsonResponse({
                    "success": False,
                    "error": "Mercado Pago não configurado para esta padaria"
                }, status=400)
        except MercadoPagoConfig.DoesNotExist:
            return JsonResponse({
                "success": False,
                "error": "Mercado Pago não configurado para esta padaria"
            }, status=400)
        
        # Calcular total e validar items
        total = 0.0
        items_description = []
        
        for i, item in enumerate(items):
            name = item.get("name", f"Item {i+1}")
            quantity = item.get("quantity", 1)
            unit_price = item.get("unit_price", 0)
            
            if quantity <= 0 or unit_price <= 0:
                return JsonResponse({
                    "success": False,
                    "error": f"Item '{name}' tem quantidade ou preço inválido"
                }, status=400)
            
            item_total = float(quantity) * float(unit_price)
            total += item_total
            items_description.append(f"{quantity}x {name}")
        
        if total <= 0:
            return JsonResponse({
                "success": False,
                "error": "Total do pedido deve ser maior que zero"
            }, status=400)
        
        # Gerar referência externa (order_id)
        import uuid
        order_id = f"order_{uuid.uuid4().hex[:12]}"
        
        # Montar descrição do pedido
        description = f"Pedido {padaria.name}: {', '.join(items_description)}"
        if len(description) > 200:
            description = description[:197] + "..."
        
        # Extrair dados do cliente
        customer_name = customer.get("name", "Cliente")
        name_parts = customer_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        customer_cpf = customer.get("cpf")
        customer_phone = customer.get("phone", "")
        
        # Criar serviço MP
        mp_service = MercadoPagoService(mp_config.access_token)
        
        # URL de notificação (webhook)
        notification_url = None
        host = request.get_host()
        if 'localhost' not in host and '127.0.0.1' not in host:
            notification_url = f"https://{host}/webhooks/mercadopago/"
        
        # Criar pagamento PIX
        logger.info(f"Criando pagamento PIX: {order_id} - R${total:.2f}")
        
        pix_result = mp_service.create_pix_payment(
            amount=total,
            description=description,
            payer_email=customer_email,
            payer_first_name=first_name,
            payer_last_name=last_name,
            payer_cpf=customer_cpf,
            external_reference=order_id,
            expiration_minutes=expiration_minutes,
            notification_url=notification_url,
        )
        
        # Registrar pagamento no banco
        mp_payment = MercadoPagoPayment.objects.create(
            config=mp_config,
            mp_payment_id=str(pix_result.get("id", "")),
            description=description,
            amount=total,
            payer_email=customer_email,
            payer_phone=customer_phone,
            pix_qr_code=pix_result.get("qr_code", ""),
            pix_qr_code_base64=pix_result.get("qr_code_base64", ""),
            ticket_url=pix_result.get("ticket_url", ""),
            status="pending",
        )
        
        # Parsear data de expiração
        expires_at = pix_result.get("expires_at")
        if expires_at:
            try:
                from datetime import datetime
                # Parse ISO format
                if isinstance(expires_at, str):
                    expires_at = expires_at.replace("-03:00", "").replace("-04:00", "")
                    mp_payment.expires_at = datetime.fromisoformat(expires_at)
                    mp_payment.save()
            except Exception:
                pass
        
        logger.info(f"Pagamento PIX criado: {order_id} - MP ID: {pix_result.get('id')}")
        
        # Retornar resposta de sucesso
        return JsonResponse({
            "success": True,
            "payment_id": str(pix_result.get("id")),
            "order_id": order_id,
            "total": round(total, 2),
            "items_count": len(items),
            "pix": {
                "qr_code": pix_result.get("qr_code", ""),
                "qr_code_base64": pix_result.get("qr_code_base64", ""),
                "ticket_url": pix_result.get("ticket_url", ""),
            },
            "expires_at": expires_at,
            "message": "Pagamento PIX criado com sucesso!"
        })
        
    except MercadoPagoAPIError as e:
        logger.error(f"Erro Mercado Pago: {e.message}")
        return JsonResponse({
            "success": False,
            "error": f"Erro Mercado Pago: {e.message}"
        }, status=500)
    except Exception as e:
        logger.exception(f"Erro inesperado ao criar pagamento: {e}")
        return JsonResponse({
            "success": False,
            "error": f"Erro inesperado: {str(e)}"
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_payment_status(request, payment_id):
    """
    Consulta status de um pagamento.
    
    GET /api/payments/<payment_id>/status/
    
    Response:
    {
        "success": true,
        "payment_id": "12345",
        "status": "pending|approved|rejected|cancelled",
        "amount": 30.00,
        "paid_at": null
    }
    """
    try:
        # Buscar no banco local primeiro
        try:
            mp_payment = MercadoPagoPayment.objects.get(mp_payment_id=payment_id)
            return JsonResponse({
                "success": True,
                "payment_id": payment_id,
                "status": mp_payment.status,
                "amount": float(mp_payment.amount),
                "description": mp_payment.description,
                "paid_at": mp_payment.paid_at.isoformat() if mp_payment.paid_at else None,
                "created_at": mp_payment.created_at.isoformat(),
            })
        except MercadoPagoPayment.DoesNotExist:
            return JsonResponse({
                "success": False,
                "error": f"Pagamento {payment_id} não encontrado"
            }, status=404)
            
    except Exception as e:
        logger.exception(f"Erro ao consultar pagamento: {e}")
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_payment_link(request):
    """
    Cria link de pagamento (checkout) via Mercado Pago.
    Endpoint para integração com n8n/WhatsApp.
    
    O n8n envia os produtos e quantidades, o sistema busca os preços
    no banco e gera o link com o total calculado.
    
    POST /payments/api/generate-link/
    
    Headers:
        Content-Type: application/json
    
    Body:
    {
        "padaria_slug": "padaria-do-marcos",
        "items": [
            {"nome": "Pão Francês", "quantidade": 10},
            {"nome": "Bolo de Chocolate", "quantidade": 1}
        ],
        "payer_email": "cliente@email.com"  // opcional
    }
    
    Response (success):
    {
        "success": true,
        "payment_id": 15,
        "checkout_url": "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=...",
        "title": "Pedido Padaria",
        "total": 35.00,
        "items": [
            {"nome": "Pão Francês", "quantidade": 10, "preco_unitario": 0.50, "subtotal": 5.00},
            {"nome": "Bolo de Chocolate", "quantidade": 1, "preco_unitario": 30.00, "subtotal": 30.00}
        ],
        "description": "10x Pão Francês, 1x Bolo de Chocolate",
        "status": "pending",
        "created_at": "2026-01-09T16:30:00Z"
    }
    
    Response (error):
    {
        "success": false,
        "error": "Descrição do erro"
    }
    """
    from organizations.models import Produto
    
    try:
        # Parse do body JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "JSON inválido no body da requisição"
            }, status=400)
        
        # Validar campos obrigatórios
        padaria_slug = data.get("padaria_slug")
        items = data.get("items", [])
        payer_email = data.get("payer_email", "")
        
        if not padaria_slug:
            return JsonResponse({
                "success": False,
                "error": "Campo 'padaria_slug' é obrigatório"
            }, status=400)
        
        if not items or not isinstance(items, list):
            return JsonResponse({
                "success": False,
                "error": "Campo 'items' é obrigatório e deve ser uma lista de produtos"
            }, status=400)
        
        # Buscar padaria
        try:
            padaria = Padaria.objects.get(slug=padaria_slug)
        except Padaria.DoesNotExist:
            return JsonResponse({
                "success": False,
                "error": f"Padaria '{padaria_slug}' não encontrada"
            }, status=404)
        
        # Verificar se padaria tem Mercado Pago configurado
        try:
            mp_config = padaria.mercadopago_config
            if not mp_config.access_token:
                return JsonResponse({
                    "success": False,
                    "error": "Mercado Pago não configurado para esta padaria"
                }, status=400)
        except MercadoPagoConfig.DoesNotExist:
            return JsonResponse({
                "success": False,
                "error": "Mercado Pago não configurado para esta padaria"
            }, status=400)
        
        # Processar itens e buscar preços no banco
        items_processados = []
        items_nao_encontrados = []
        total = 0.0
        descricao_itens = []
        
        for item in items:
            nome = item.get("nome", "").strip()
            produto_id = item.get("id")  # Também aceita ID do produto
            quantidade = item.get("quantidade", 1)
            
            if not nome and not produto_id:
                continue
            
            try:
                quantidade = int(quantidade)
                if quantidade <= 0:
                    quantidade = 1
            except (TypeError, ValueError):
                quantidade = 1
            
            # Buscar produto no banco (por ID ou por nome)
            produto = None
            try:
                if produto_id:
                    produto = Produto.objects.get(id=produto_id, padaria=padaria, ativo=True)
                else:
                    # Busca por nome (case-insensitive, parcial)
                    produto = Produto.objects.filter(
                        padaria=padaria,
                        nome__icontains=nome,
                        ativo=True
                    ).first()
                    
                    # Se não encontrou parcial, tenta exato
                    if not produto:
                        produto = Produto.objects.filter(
                            padaria=padaria,
                            nome__iexact=nome,
                            ativo=True
                        ).first()
            except Produto.DoesNotExist:
                pass
            
            if produto and produto.preco:
                preco_original = float(produto.preco)
                preco_unitario = preco_original
                em_promocao = False
                
                # Verificar se o produto tem promoção ativa
                from organizations.models import Promocao
                promocao_ativa = Promocao.objects.filter(
                    produto=produto,
                    is_active=True
                ).first()
                
                if promocao_ativa and promocao_ativa.is_valid() and promocao_ativa.preco:
                    preco_unitario = float(promocao_ativa.preco)
                    em_promocao = True
                
                subtotal = preco_unitario * quantidade
                total += subtotal
                
                item_data = {
                    "id": produto.id,
                    "nome": produto.nome,
                    "quantidade": quantidade,
                    "preco_unitario": round(preco_unitario, 2),
                    "subtotal": round(subtotal, 2)
                }
                
                # Adicionar info de promoção se aplicável
                if em_promocao:
                    item_data["em_promocao"] = True
                    item_data["preco_original"] = round(preco_original, 2)
                    descricao_itens.append(f"{quantidade}x {produto.nome} (PROMO)")
                else:
                    descricao_itens.append(f"{quantidade}x {produto.nome}")
                
                items_processados.append(item_data)
            else:
                items_nao_encontrados.append(nome if nome else f"ID:{produto_id}")
        
        # Verificar se encontrou algum item
        if not items_processados:
            return JsonResponse({
                "success": False,
                "error": f"Nenhum produto encontrado. Itens não encontrados: {', '.join(items_nao_encontrados)}"
            }, status=404)
        
        if total <= 0:
            return JsonResponse({
                "success": False,
                "error": "Total do pedido deve ser maior que zero"
            }, status=400)
        
        # Gerar external_reference único para tracking
        import uuid
        external_reference = f"pandia_{padaria.slug}_{uuid.uuid4().hex[:8]}"
        
        # URL de notificação (webhook)
        notification_url = None
        host = request.get_host()
        if 'localhost' not in host and '127.0.0.1' not in host:
            notification_url = f"https://{host}/webhooks/mercadopago/"
        
        # Montar título e descrição
        title = f"Pedido {padaria.name}"
        description = ", ".join(descricao_itens)
        if len(description) > 200:
            description = description[:197] + "..."
        
        # Criar preferência no Mercado Pago
        mp_service = MercadoPagoService(mp_config.access_token)
        
        logger.info(f"Criando link de pagamento: {title} - R${total:.2f} - {len(items_processados)} itens")
        
        preference = mp_service.create_preference(
            title=title,
            amount=total,
            description=description,
            payer_email=payer_email if payer_email else None,
            external_reference=external_reference,
            notification_url=notification_url,
        )
        
        # Salvar no banco
        mp_payment = MercadoPagoPayment.objects.create(
            config=mp_config,
            mp_preference_id=preference.get('id', ''),
            description=description,
            amount=total,
            payer_email=payer_email,
            checkout_url=preference.get('init_point', ''),
            pix_qr_code=external_reference,  # Armazena external_ref para tracking
            status='pending',
        )
        
        logger.info(f"Link de pagamento criado: {mp_payment.id} - {preference.get('init_point', '')[:50]}...")
        
        # Preparar resposta
        response_data = {
            "success": True,
            "payment_id": mp_payment.id,
            "checkout_url": preference.get('init_point', ''),
            "sandbox_url": preference.get('sandbox_init_point', ''),
            "title": title,
            "total": round(total, 2),
            "items": items_processados,
            "description": description,
            "status": "pending",
            "created_at": mp_payment.created_at.isoformat(),
        }
        
        # Adicionar aviso se algum item não foi encontrado
        if items_nao_encontrados:
            response_data["warning"] = f"Alguns itens não foram encontrados: {', '.join(items_nao_encontrados)}"
        
        return JsonResponse(response_data)
        
    except MercadoPagoAPIError as e:
        logger.error(f"Erro Mercado Pago: {e.message}")
        return JsonResponse({
            "success": False,
            "error": f"Erro Mercado Pago: {e.message}"
        }, status=500)
    except Exception as e:
        logger.exception(f"Erro inesperado ao criar link de pagamento: {e}")
        return JsonResponse({
            "success": False,
            "error": f"Erro inesperado: {str(e)}"
        }, status=500)
