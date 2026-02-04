# Sistema de Assinaturas - Pandia

## 📋 Visão Geral

O sistema de assinaturas do Pandia usa o **Asaas** como gateway de pagamento com **renovação automática mensal**.

## ✅ Correções Implementadas (Fev 2026)

### 1. **Cálculo Correto de Vencimento**
- ❌ **Antes**: `next_due_date = hoje + 30 dias`
- ✅ **Agora**: `next_due_date = last_payment_date + 30 dias`

**Motivo**: O vencimento deve ser baseado na data do último pagamento, não na data atual. Isso garante que o ciclo de 30 dias seja respeitado mesmo se houver atrasos.

### 2. **Período Gratuito (Trial)**
- ✅ **15 dias grátis** para novas padarias
- Status inicial: `active` com `next_due_date = hoje + 15 dias`
- Após 15 dias, a primeira cobrança é gerada automaticamente

### 3. **Débito Automático (Assinatura Recorrente)**
- ✅ O Asaas gerencia cobranças mensais automaticamente
- Tipo: **SUBSCRIPTION** no Asaas (não cobrança avulsa)
- Ciclo: **MONTHLY** (configurável em `.env`)

## 🔄 Fluxo de Assinatura

### Criação de Nova Padaria
```python
1. Padaria criada → Signal dispara
2. AsaasSubscription criada com:
   - status = 'active'
   - next_due_date = hoje + 15 dias (trial)
   - plan_value = R$ X/mês
3. Padaria usa o sistema gratuitamente por 15 dias
```

### Primeiro Vencimento (Após Trial)
```python
1. Dia 15 → Sistema cria cobrança automática no Asaas
2. Cliente recebe link de pagamento por email/webhook
3. Cliente paga → Webhook PAYMENT_RECEIVED dispara
4. Sistema atualiza:
   - status = 'active'
   - last_payment_date = data do pagamento
   - next_due_date = last_payment_date + 30 dias
```

### Renovações Mensais
```python
1. A cada 30 dias do last_payment_date:
   - Asaas gera nova cobrança automaticamente
   - Cliente recebe link de pagamento
2. Se pago:
   - status = 'active'
   - last_payment_date = data do novo pagamento
   - next_due_date = last_payment_date + 30 dias
3. Se não pago após vencimento:
   - status = 'overdue'
   - Sistema continua funcionando (opcional bloquear)
```

## 📊 Modelo de Dados

### AsaasSubscription
```python
class AsaasSubscription:
    padaria: OneToOne → Padaria
    
    # IDs Asaas
    asaas_customer_id: str     # ID do cliente no Asaas
    asaas_subscription_id: str # ID da assinatura recorrente
    
    # Plano
    plan_name: str = "Plano Único"
    plan_value: Decimal        # Configurado em ASAAS_SUBSCRIPTION_VALUE
    billing_type: str          # PIX, CREDIT_CARD, BOLETO
    
    # Status e Datas
    status: str  # active, pending, overdue, cancelled, expired
    next_due_date: Date        # Calculado como last_payment_date + 30
    last_payment_date: Date    # Data do último pagamento confirmado
    
    # Link de Pagamento Atual
    current_payment_link: URL
    current_payment_id: str
```

### AsaasPayment (Histórico)
```python
class AsaasPayment:
    subscription: FK → AsaasSubscription
    asaas_payment_id: str
    value: Decimal
    due_date: Date
    payment_date: Date
    status: str  # pending, received, overdue, refunded
    invoice_url: URL
```

## 🔔 Webhooks Asaas

### PAYMENT_CREATED
Cobrança mensal gerada automaticamente:
```python
- Salva AsaasPayment com status='pending'
- Atualiza current_payment_link na subscription
- Cliente recebe email do Asaas com link
```

### PAYMENT_RECEIVED / PAYMENT_CONFIRMED
Pagamento confirmado:
```python
- AsaasPayment.status = 'received'
- AsaasSubscription.status = 'active'
- AsaasSubscription.last_payment_date = hoje
- AsaasSubscription.next_due_date = last_payment_date + 30 dias ✅
- Limpa current_payment_link
```

### PAYMENT_OVERDUE
Pagamento vencido:
```python
- AsaasPayment.status = 'overdue'
- AsaasSubscription.status = 'overdue'
- Sistema pode bloquear acesso (opcional)
```

## ⚙️ Configuração (.env)

```bash
# Credenciais Asaas
ASAAS_API_KEY=seu_api_key_aqui
ASAAS_ENVIRONMENT=sandbox  # ou production
ASAAS_WEBHOOK_TOKEN=seu_token_webhook

# Assinatura
ASAAS_SUBSCRIPTION_VALUE=99.90    # Valor mensal em R$
ASAAS_SUBSCRIPTION_CYCLE=MONTHLY  # Ciclo de cobrança
```

## 📌 Pontos Importantes

### ✅ Vantagens do Sistema Atual
1. **Renovação Automática**: Asaas gerencia cobranças mensais
2. **Trial de 15 dias**: Novas padarias têm período gratuito
3. **Cálculo correto**: Vencimento baseado em `last_payment_date`
4. **Webhooks em tempo real**: Status atualizado automaticamente
5. **Histórico completo**: Todos os pagamentos salvos

### ⚠️ Comportamento Atual
- **Inadimplência**: Status vira `overdue` mas sistema continua funcionando
- **Sem bloqueio automático**: Padaria inadimplente ainda pode usar o sistema
- **Sem retry automático**: Cliente precisa pagar manualmente o link

### 🔧 Melhorias Sugeridas (Futuro)
1. **Bloquear agente** após X dias de inadimplência
2. **Retry de cobrança** automático (3, 5, 7 dias)
3. **Notificações por email** antes do vencimento
4. **Dashboard de métricas** de assinaturas para admin
5. **Múltiplos planos** (básico, premium, enterprise)

## 🧪 Testando Assinaturas

### Sandbox Asaas
```bash
1. Usar ASAAS_ENVIRONMENT=sandbox
2. Criar padaria de teste
3. Verificar que recebeu 15 dias grátis
4. Simular pagamento no Asaas Sandbox
5. Verificar webhook de confirmação
```

### Produção
```bash
1. ASAAS_ENVIRONMENT=production
2. Configurar webhook URL no Asaas
3. Validar SSL do domínio
4. Testar com valor real
```

## 📞 Suporte

- **Documentação Asaas**: https://docs.asaas.com
- **API Reference**: https://docs.asaas.com/reference
- **Webhooks**: https://docs.asaas.com/docs/webhooks

---

**Última atualização**: Fevereiro 2026  
**Versão do sistema**: 2.0 (com trial e débito automático)
