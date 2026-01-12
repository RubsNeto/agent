# API de Monitoramento de Pagamentos

Esta documentação descreve os endpoints disponíveis para monitorar o status dos links de pagamento gerados pelo sistema.

## Visão Geral

Quando um link de pagamento é gerado via `/payments/api/generate-link/`, ele retorna um `payment_id` interno que pode ser usado para monitorar o status do pagamento.

### 🔄 Monitoramento Automático

O sistema agora inclui **monitoramento automático em background**! Quando um link de pagamento é criado:

1. Um **monitor em background** é iniciado automaticamente
2. O monitor verifica o status na API do Mercado Pago **a cada 5 segundos**
3. Quando o pagamento é aprovado, o status é atualizado automaticamente no banco
4. O monitoramento dura até **10 minutos** ou até o pagamento ser finalizado

### Formas de Monitorar

O sistema oferece 4 formas de monitorar os pagamentos:
1. **Monitoramento automático em background** (novo!) - Inicia automaticamente
2. **Webhook automático**: O Mercado Pago notifica quando há mudanças
3. **Polling manual**: Consultar status individual via API
4. **Sincronização em lote**: Sincronizar todos os pagamentos pendentes de uma vez

---

## Endpoints de Monitoramento

### 1. Verificar Status de um Pagamento

**Endpoint:** `GET /payments/api/check/<payment_id>/` ou `POST /payments/api/check/<payment_id>/`

Consulta o status atual de um pagamento específico e **sincroniza com o Mercado Pago** para obter a informação mais recente.

#### Parâmetros

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| payment_id | int (path) | ID interno do pagamento (retornado ao gerar o link) |

#### Exemplo de Requisição

```bash
curl -X GET "http://localhost:8000/payments/api/check/15/"
```

#### Resposta de Sucesso (200)

```json
{
    "success": true,
    "payment_id": 15,
    "mp_payment_id": "123456789",
    "preference_id": "xxx-yyy-zzz",
    "external_reference": "pandia_padaria_abc12345",
    "status": "approved",
    "status_detail": "accredited",
    "status_label": "Aprovado",
    "amount": 35.00,
    "description": "10x Pão Francês, 1x Bolo de Chocolate",
    "checkout_url": "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=...",
    "padaria_name": "Padaria do Marcos",
    "payer_email": "cliente@email.com",
    "paid_at": "2026-01-12T10:30:00.000000-03:00",
    "created_at": "2026-01-12T10:00:00.000000-03:00",
    "updated_at": "2026-01-12T10:30:05.000000-03:00",
    "synced": true,
    "synced_at": "2026-01-12T10:30:10.000000-03:00",
    "status_changed": true
}
```

#### Status Possíveis

| Status | Label | Descrição |
|--------|-------|-----------|
| `pending` | Pendente | Aguardando pagamento |
| `approved` | Aprovado | Pagamento confirmado ✅ |
| `authorized` | Autorizado | Pagamento autorizado (não capturado) |
| `in_process` | Em Processamento | Pagamento sendo analisado |
| `rejected` | Rejeitado | Pagamento recusado ❌ |
| `cancelled` | Cancelado | Pagamento cancelado |
| `refunded` | Estornado | Pagamento devolvido |

---

### 2. Listar Pagamentos Pendentes

**Endpoint:** `GET /payments/api/pending/`

Lista todos os pagamentos de uma padaria, com opção de filtrar por status.

#### Parâmetros (Query String)

| Parâmetro | Tipo | Obrigatório | Default | Descrição |
|-----------|------|-------------|---------|-----------|
| padaria_slug | string | ✅ | - | Slug da padaria |
| status | string | ❌ | `pending` | Status para filtrar (`pending`, `approved`, `all`) |
| limit | int | ❌ | 50 | Número máximo de resultados |

#### Exemplo de Requisição

```bash
# Listar pagamentos pendentes
curl "http://localhost:8000/payments/api/pending/?padaria_slug=padaria-do-marcos"

# Listar pagamentos aprovados
curl "http://localhost:8000/payments/api/pending/?padaria_slug=padaria-do-marcos&status=approved"

# Listar todos os pagamentos (sem filtro de status)
curl "http://localhost:8000/payments/api/pending/?padaria_slug=padaria-do-marcos&status=all&limit=100"
```

#### Resposta de Sucesso (200)

```json
{
    "success": true,
    "padaria": "Padaria do Marcos",
    "count": 3,
    "status_filter": "pending",
    "payments": [
        {
            "payment_id": 18,
            "mp_payment_id": null,
            "preference_id": "xxx-yyy-zzz",
            "status": "pending",
            "status_label": "Pendente",
            "amount": 25.50,
            "description": "5x Pão de Queijo",
            "checkout_url": "https://...",
            "payer_email": "cliente@email.com",
            "paid_at": null,
            "created_at": "2026-01-12T09:00:00Z"
        },
        ...
    ]
}
```

---

### 3. Sincronizar Todos os Pagamentos Pendentes

**Endpoint:** `POST /payments/api/sync-pending/`

Sincroniza todos os pagamentos com status `pending` de uma padaria com o Mercado Pago. Útil para atualização em lote.

#### Body (JSON)

```json
{
    "padaria_slug": "padaria-do-marcos"
}
```

#### Exemplo de Requisição

```bash
curl -X POST "http://localhost:8000/payments/api/sync-pending/" \
     -H "Content-Type: application/json" \
     -d '{"padaria_slug": "padaria-do-marcos"}'
```

#### Resposta de Sucesso (200)

```json
{
    "success": true,
    "padaria": "Padaria do Marcos",
    "synced_count": 5,
    "approved_count": 2,
    "total_pending": 5,
    "updated_payments": [
        {
            "payment_id": 15,
            "old_status": "pending",
            "new_status": "approved",
            "amount": 35.00,
            "description": "10x Pão Francês"
        },
        {
            "payment_id": 16,
            "old_status": "pending",
            "new_status": "approved",
            "amount": 50.00,
            "description": "2x Bolo de Chocolate"
        }
    ]
}
```

---

## Webhook de Notificação Automática

O Mercado Pago também envia notificações automáticas (webhooks) quando o status de um pagamento muda.

**Endpoint de Webhook:** `POST /webhooks/mercadopago/`

Este endpoint é configurado automaticamente quando um link de pagamento é gerado (se o sistema estiver em produção, não localhost).

---

## Fluxo Recomendado para Frontend

Para atualizar a tela do usuário em tempo real:

### Opção 1: Polling (Mais Simples)

```javascript
// Após gerar o link, salve o payment_id
const paymentId = response.payment_id;

// Faça polling a cada 5 segundos
const interval = setInterval(async () => {
    const status = await fetch(`/payments/api/check/${paymentId}/`);
    const data = await status.json();
    
    if (data.status === 'approved') {
        clearInterval(interval);
        showSuccessMessage("Pagamento aprovado! ✅");
    } else if (['rejected', 'cancelled'].includes(data.status)) {
        clearInterval(interval);
        showErrorMessage("Pagamento não foi aprovado ❌");
    }
}, 5000);

// Timeout após 10 minutos
setTimeout(() => clearInterval(interval), 600000);
```

### Opção 2: Sincronização em Lote

```javascript
// A cada 30 segundos, sincronize todos os pendentes
setInterval(async () => {
    const response = await fetch('/payments/api/sync-pending/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ padaria_slug: 'sua-padaria' })
    });
    
    const data = await response.json();
    
    if (data.approved_count > 0) {
        // Atualizar lista de pagamentos na tela
        data.updated_payments.forEach(p => {
            if (p.new_status === 'approved') {
                notifyPaymentApproved(p);
            }
        });
    }
}, 30000);
```

---

## Response do Endpoint de Geração de Link

O endpoint `/payments/api/generate-link/` retorna informações completas para monitoramento:

```json
{
    "success": true,
    "payment_id": 15,
    "preference_id": "xxx-yyy-zzz",
    "checkout_url": "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=...",
    "secure_checkout_url": "http://seusite.com/payments/mp/pay/15/",
    "status_check_url": "http://seusite.com/payments/api/check/15/",
    "sandbox_url": "https://sandbox...",
    "title": "Pedido Padaria do Marcos",
    "total": 35.00,
    "items": [...],
    "description": "10x Pão Francês, 1x Bolo de Chocolate",
    "status": "pending",
    "external_reference": "pandia_padaria_abc12345",
    "created_at": "2026-01-12T10:00:00Z"
}
```

### Campos Importantes:

| Campo | Descrição |
|-------|-----------|
| `checkout_url` | Link direto do Mercado Pago (original) |
| `secure_checkout_url` | **Recomendado!** Link que passa pelo nosso sistema primeiro, verificando se já foi pago |
| `status_check_url` | URL para verificar status via polling |
| `preference_id` | ID da preferência no Mercado Pago |
| `external_reference` | Referência única para rastreamento |

---

## 🔒 Proteção contra Links Já Pagos

O sistema agora bloqueia automaticamente o acesso a links de pagamento que já foram aprovados:

### URL Segura (Recomendada)

Use `secure_checkout_url` em vez de `checkout_url` para enviar ao cliente:

```
http://seusite.com/payments/mp/pay/{payment_id}/
```

Esta URL:
1. Verifica se o pagamento já foi realizado
2. Se **já foi pago**: mostra página informando que o pagamento já foi feito
3. Se **expirado/cancelado**: mostra página de link expirado
4. Se **pendente**: redireciona para o checkout do Mercado Pago

### Páginas de Retorno

Após o cliente completar (ou abandonar) o pagamento no MP, ele é redirecionado para:

| URL | Quando |
|-----|--------|
| `/payments/mp/return/?status=approved&payment_id=X` | Pagamento aprovado |
| `/payments/mp/return/?status=pending&payment_id=X` | Pagamento pendente |
| `/payments/mp/return/?status=rejected&payment_id=X` | Pagamento rejeitado |

A página de retorno:
1. Recebe os parâmetros do Mercado Pago
2. Atualiza o status no banco de dados
3. Mostra página apropriada (sucesso, pendente ou falha)
4. Para pagamentos pendentes, faz polling automático a cada 5 segundos

---

## Erros Comuns

### 404 - Pagamento não encontrado
```json
{
    "success": false,
    "error": "Pagamento 999 não encontrado"
}
```

### 400 - Padaria não encontrada
```json
{
    "success": false,
    "error": "Padaria 'slug-invalido' não encontrada"
}
```

### 400 - Mercado Pago não configurado
```json
{
    "success": false,
    "error": "Mercado Pago não configurado para esta padaria"
}
```

---

## 🤖 Endpoints de Monitoramento Automático

O sistema inclui um serviço de polling em background que monitora automaticamente os pagamentos.

### 4. Iniciar Monitor para um Pagamento

**Endpoint:** `POST /payments/api/monitor/<payment_id>/start/`

Inicia manualmente o monitoramento de um pagamento específico. Útil se o monitor automático expirou e você quer reiniciar.

#### Exemplo de Requisição

```bash
curl -X POST "http://localhost:8000/payments/api/monitor/15/start/"
```

#### Resposta de Sucesso (200)

```json
{
    "success": true,
    "payment_id": 15,
    "status": "pending",
    "message": "Monitoramento iniciado",
    "monitoring": true
}
```

---

### 5. Listar Monitores Ativos

**Endpoint:** `GET /payments/api/monitors/`

Retorna a lista de pagamentos que estão sendo monitorados ativamente em background.

#### Exemplo de Requisição

```bash
curl "http://localhost:8000/payments/api/monitors/"
```

#### Resposta de Sucesso (200)

```json
{
    "success": true,
    "active_count": 3,
    "payment_ids": [15, 16, 17]
}
```

---

### 6. Iniciar Monitores em Lote

**Endpoint:** `POST /payments/api/monitors/start-all/`

Inicia monitoramento para todos os pagamentos pendentes de uma padaria.

#### Body (JSON)

```json
{
    "padaria_slug": "padaria-do-marcos"
}
```

#### Exemplo de Requisição

```bash
curl -X POST "http://localhost:8000/payments/api/monitors/start-all/" \
     -H "Content-Type: application/json" \
     -d '{"padaria_slug": "padaria-do-marcos"}'
```

#### Resposta de Sucesso (200)

```json
{
    "success": true,
    "padaria_slug": "padaria-do-marcos",
    "monitors_started": 5
}
```

---

## Como Funciona o Monitoramento Automático

```
┌──────────────────────────────────────────────────────────────────┐
│                    FLUXO DE MONITORAMENTO                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Link Criado                                                  │
│     └── POST /payments/api/generate-link/                        │
│         └── Monitor iniciado automaticamente (thread)            │
│                                                                  │
│  2. Loop de Verificação (a cada 5 segundos)                      │
│     ├── Buscar pagamento no banco                                │
│     ├── Consultar API do Mercado Pago (search_payments)          │
│     │   └── GET /v1/payments/search?external_reference=xxx       │
│     └── Se status mudou → Atualizar banco                        │
│                                                                  │
│  3. Condições de Parada                                          │
│     ├── Status final (approved, rejected, cancelled)             │
│     ├── Tempo máximo atingido (10 minutos)                       │
│     └── Pagamento não existe mais                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Logs de Debug

O sistema gera logs para cada operação do monitor:

```
INFO: Monitor iniciado para pagamento 15
DEBUG: Monitor 15: verificação #1
DEBUG: Monitor 15: verificação #2
INFO: Monitor 15: status mudou pending -> approved
INFO: Monitor 15: status final approved, parando
INFO: Monitor 15: finalizado após 3 verificações
```
