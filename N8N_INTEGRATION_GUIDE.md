# Guia de Integração N8N

## 📋 Passo a Passo para Configurar HTTP Request no N8N

### 1️⃣ Criar API Key
1. Acesse seu SaaS em: `http://seu-dominio.ngrok-free.dev/organizations/`
2. Clique em "API Keys" da sua organização
3. Clique em "Criar Nova API Key"
4. Copie a chave gerada (exemplo: `sk_abc123xyz...`)

### 2️⃣ Descobrir o Slug do Agente
1. Vá em "Agentes"
2. Clique no agente que deseja usar
3. O slug está na URL: `/agents/seu-agente-slug/`
   - Exemplo: `maria-atendente-unhas-fast`

### 3️⃣ Configurar HTTP Request no N8N

**Adicione um nó "HTTP Request" no seu workflow:**

```
┌─────────────────────────────────────────┐
│ HTTP Request - Buscar Config do Agente │
└─────────────────────────────────────────┘
```

**Configurações:**

| Campo | Valor |
|-------|-------|
| **Method** | `GET` |
| **URL** | `https://seu-dominio.ngrok-free.dev/api/n8n/agents/SEU-SLUG/config` |
| **Authentication** | `Header Auth` |
| **Header Name** | `Authorization` |
| **Header Value** | `Bearer SUA_API_KEY` |

**Exemplo real:**
```
Method: GET
URL: https://petra-nonlogistical-freeman.ngrok-free.dev/api/n8n/agents/maria-atendente-unhas-fast/config
Header: Authorization: Bearer sk_1234567890abcdef
```

### 4️⃣ Testar a Requisição
1. Clique em "Execute Node" no N8N
2. Você deve receber um JSON com:
   - `name`: Nome do agente
   - `greeting`: Saudação inicial
   - `knowledge_base`: Todo o conhecimento (incluindo PDF extraído!)
   - `tone`: Tom de voz
   - `escalation_rule`: Quando escalar para humano
   - Etc.

### 5️⃣ Usar os Dados no Workflow

**Exemplo de uso:**

```javascript
// Acessar o conhecimento do agente
{{ $json.knowledge_base }}

// Usar a saudação personalizada
{{ $json.greeting }}

// Verificar o tom de voz
{{ $json.tone }}
```

## 🔄 Fluxo Completo Sugerido

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Webhook    │────▶│ HTTP Request │────▶│   OpenAI     │
│  (Chatwoot)  │     │ (Buscar Agent│     │  (Chat GPT)  │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     Agent Config:
                     - knowledge_base
                     - tone
                     - rules
```

**No nó OpenAI, você usa:**

```javascript
System Prompt:
Você é {{ $node["HTTP Request"].json.name }}.
Papel: {{ $node["HTTP Request"].json.role }}
Tom de voz: {{ $node["HTTP Request"].json.tone }}

Conhecimento:
{{ $node["HTTP Request"].json.knowledge_base }}

Regras de escalonamento:
{{ $node["HTTP Request"].json.escalation_rule }}
```

## 🚨 Troubleshooting

### Erro 401 (Unauthorized)
- ✅ Verifique se a API Key está correta
- ✅ Confirme que o header é `Authorization: Bearer SUA_CHAVE`

### Erro 404 (Not Found)
- ✅ Verifique se o slug do agente está correto
- ✅ Confirme que o agente está marcado como "Ativo"
- ✅ Verifique se a API Key pertence à mesma organização do agente

### Erro 429 (Rate Limit)
- ✅ Você excedeu 60 requisições por minuto
- ✅ Aguarde 1 minuto e tente novamente
- ✅ Considere cachear a configuração do agente

## 💡 Dicas

1. **Cache**: Não busque a config a cada mensagem. Busque uma vez no início da conversa.
2. **Variáveis**: Use variáveis do N8N para armazenar o slug e API key.
3. **Webhook**: Quando atualizar o agente no SaaS, ele pode notificar o N8N (futuro).

## 📚 Mais Informações

Acesse a documentação completa em: `/api/docs/`
