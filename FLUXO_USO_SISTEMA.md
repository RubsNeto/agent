# 🍞 Fluxo de Uso do Sistema - Padaria Agent

> Documento que descreve o fluxo completo desde a criação de uma padaria pelo Admin até a recepção de mensagens no WhatsApp pelo dono da padaria.

---

## 📋 Índice

1. [Visão Geral do Sistema](#visão-geral-do-sistema)
2. [Papéis e Permissões](#papéis-e-permissões)
3. [Fluxo Completo](#fluxo-completo)
   - [Etapa 1: Admin Master Cria a Padaria](#etapa-1-admin-master-cria-a-padaria)
   - [Etapa 2: Dono da Padaria Acessa o Sistema](#etapa-2-dono-da-padaria-acessa-o-sistema)
   - [Etapa 3: Criação do Agente de IA](#etapa-3-criação-do-agente-de-ia)
   - [Etapa 4: Configuração do n8n (Automação)](#etapa-4-configuração-do-n8n-automação)
   - [Etapa 5: Integração com WhatsApp (Evolution API)](#etapa-5-integração-com-whatsapp-evolution-api)
   - [Etapa 6: Cliente Envia Mensagem no WhatsApp](#etapa-6-cliente-envia-mensagem-no-whatsapp)
   - [Etapa 7: Dono Recebe e Acompanha as Conversas](#etapa-7-dono-recebe-e-acompanha-as-conversas)
4. [Diagrama de Arquitetura](#diagrama-de-arquitetura)
5. [Checklist de Configuração](#checklist-de-configuração)

---

## 🎯 Visão Geral do Sistema

O sistema é uma plataforma SaaS para gerenciamento de **agentes de IA** que atendem clientes via **WhatsApp**. Cada padaria cadastrada pode ter seu próprio agente de IA personalizado.

### Componentes Principais

| Componente | Descrição |
|------------|-----------|
| **Django SaaS** | Backend que gerencia padarias, agentes e API Keys |
| **n8n** | Orquestrador de automações (recebe mensagens, processa com IA, responde) |
| **Evolution API** | Conecta com WhatsApp Business |
| **Supabase** | Banco de dados para RAG (memória vetorial do agente) |
| **OpenAI/LLM** | Modelo de linguagem para gerar respostas |

---

## 👥 Papéis e Permissões

| Papel | Permissões |
|-------|------------|
| **Admin Master** | Acesso total: criar/editar/deletar padarias, usuários, agentes, ver logs globais |
| **Dono da Padaria** | Gerenciar seu agente, ver API Keys, configurar base de conhecimento |
| **Funcionário** | Visualizar e editar configurações do agente (limitado) |

---

## 🔄 Fluxo Completo

### Etapa 1: Admin Master Cria a Padaria

#### 1.1 Acesso ao Painel Admin

```
URL: /admin-panel/
```

1. O **Admin Master** faz login no sistema
2. Acessa o **Dashboard Administrativo**
3. Clica em **"Nova Padaria"**

#### 1.2 Preenchimento do Formulário

**Dados da Empresa:**
| Campo | Exemplo | Obrigatório |
|-------|---------|-------------|
| Nome da Padaria | Padaria Pão Quente | ✅ Sim |
| CNPJ | 12.345.678/0001-90 | Não |
| Telefone | (11) 99999-9999 | Não |
| E-mail | contato@paoquente.com.br | Não |
| Endereço | Rua das Flores, 123 | Não |

**Dados do Usuário Dono:**
| Campo | Exemplo | Obrigatório |
|-------|---------|-------------|
| Nome Completo | João Silva | ✅ Sim |
| E-mail | joao@paoquente.com.br | ✅ Sim |
| Senha | (mínimo 6 caracteres) | ✅ Sim |

#### 1.3 O que acontece ao salvar

O sistema automaticamente:

1. ✅ Cria o **usuário dono** com as credenciais informadas
2. ✅ Cria a **padaria** com os dados de empresa
3. ✅ Vincula o usuário como **membro** (role: `dono`)
4. ✅ Gera uma **API Key** inicial para a padaria
5. ✅ Registra a ação no **log de auditoria**

```python
# Código executado (admin_panel/views.py)
owner = User.objects.create_user(username, email, password)
padaria = Padaria.objects.create(name=name, owner=owner, ...)
PadariaUser.objects.create(user=owner, padaria=padaria, role='dono')
ApiKey.objects.create(padaria=padaria, name='Chave Principal')
```

#### 1.4 Resultado

O admin vê mensagem de sucesso:
```
✅ Padaria 'Padaria Pão Quente' criada com sucesso! 
Usuário 'joao' criado.
```

---

### Etapa 2: Dono da Padaria Acessa o Sistema

#### 2.1 Login

```
URL: /accounts/login/
```

O dono usa as credenciais criadas pelo admin:
- **Usuário:** joao (gerado a partir do email)
- **Senha:** a definida no cadastro

#### 2.2 Dashboard do Dono

Após login, o dono é redirecionado para:
```
URL: /agents/
```

**O que o dono pode ver:**
- Sua padaria (nome, dados)
- Agente (se já existir)
- Opção para **criar agente** (se ainda não existir)

---

### Etapa 3: Criação do Agente de IA

#### 3.1 Acessar Criação

```
URL: /agents/create/
```

O dono clica em **"Criar Agente"** ou é direcionado automaticamente se a padaria não tiver agente.

#### 3.2 Formulário do Agente

**Informações Básicas:**
| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| Nome do Agente | Nome que aparece nas conversas | Maria |
| Padaria | Selecionada automaticamente | Padaria Pão Quente |
| Perfil/Preset | Template de personalidade | Atendente de Padaria |

**Personalidade:**
| Campo | Opções | Descrição |
|-------|--------|-----------|
| Função | Atendente, Vendedor, etc. | Define comportamento base |
| Personalidade | Amigável, Profissional, etc. | Tom de voz nas respostas |
| Status | Ativo, Inativo, Manutenção | Se recebe mensagens |

**Mensagens Customizáveis:**
| Campo | Padrão |
|-------|--------|
| Saudação | "Olá! Eu sou {{agente_nome}}, assistente virtual da {{padaria_nome}}..." |
| Fora do Horário | "No momento estamos fora do horário de atendimento..." |
| Fallback | "Desculpe, não entendi. Pode reformular?" |

**Base de Conhecimento:**
- **Texto Markdown:** Informações sobre produtos, preços, políticas
- **Upload PDF:** Documento com cardápio, FAQ, etc.

#### 3.3 O que acontece ao salvar

```python
# Código executado (agents/views.py)

# 1. Salvar agente no banco
agent = form.save()

# 2. Processar PDF (se enviado)
if pdf_file:
    extracted_text = extract_text_from_pdf(pdf_file)
    agent.knowledge_pdf_text = extracted_text

# 3. Gerar API Key VINCULADA ao agente
api_key = ApiKey.objects.create(
    padaria=agent.padaria,
    agent=agent,  # Vinculada a este agente específico
    name=f"Auto - {agent.name}"
)

# 4. Sincronizar com Supabase
sync_agent_to_supabase(slug, api_key, padaria_name, agent_name, phone)
create_rag_table(slug)  # Cria tabela RAG para esta padaria

# 5. Notificar n8n via webhook
requests.post(webhook_url, json={
    "action": "agent_created",
    "agent_slug": agent.slug,
    "api_key": api_key.key,
    ...
})
```

#### 3.4 Resultado

Mensagem exibida ao dono:
```
✅ Agente 'Maria' criado com sucesso! ✨

🔑 API Key gerada: sk_abcdef123456...

⚠️ Copie a chave agora! Ela não será exibida novamente.
```

**O que foi criado automaticamente:**
- Agente com configurações
- API Key vinculada ao agente
- Registro no Supabase (tabela `agentes`)
- Tabela RAG para memória (`rag_padaria_pao_quente`)

---

### Etapa 4: Configuração do n8n (Automação)

#### 4.1 Estrutura do Workflow n8n

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Evolution API   │────▶│    n8n Flow      │────▶│  Evolution API   │
│  (Recebe msg)    │     │   (Processa)     │     │  (Envia resposta)│
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ Django   │ │ Supabase │ │ OpenAI   │
              │ API      │ │ RAG      │ │ LLM      │
              └──────────┘ └──────────┘ └──────────┘
```

#### 4.2 Buscar Configuração do Agente

**Endpoint:**
```http
GET /api/n8n/agents/{slug}/config
Authorization: Bearer {api_key}
```

**Exemplo de Requisição:**
```bash
curl -X GET "https://seu-saas.com/api/n8n/agents/maria-padaria-pao-quente/config" \
  -H "Authorization: Bearer sk_abcdef123456..."
```

**Resposta JSON:**
```json
{
  "name": "Maria",
  "slug": "maria-padaria-pao-quente",
  "role": "atendente",
  "personality": "amigavel",
  "greeting": "Olá! Eu sou Maria, assistente virtual da Padaria Pão Quente!",
  "knowledge_base": "## Produtos\n- Pão Francês R$0,50\n- Pão de Queijo R$3,00...",
  "business_hours": {
    "mon": "06:00-20:00",
    "tue": "06:00-20:00",
    ...
  },
  "fallback_message": "Desculpe, não entendi...",
  "escalation_rule": "Transferir quando cliente pedir humano...",
  "padaria": {
    "name": "Padaria Pão Quente",
    "slug": "padaria-pao-quente"
  }
}
```

#### 4.3 Buscar Base de Conhecimento (Endpoint Separado)

**Para não sobrecarregar requisições frequentes:**
```http
GET /api/n8n/agents/{slug}/knowledge
Authorization: Bearer {api_key}
```

**Resposta:**
```json
{
  "slug": "maria-padaria-pao-quente",
  "knowledge_base": "## Produtos da Padaria\n...",
  "has_pdf": true,
  "pdf_text": "Conteúdo extraído do PDF...",
  "updated_at": "2025-12-18T12:00:00Z"
}
```

---

### Etapa 5: Integração com WhatsApp (Evolution API)

#### 5.1 Configurar Instância Evolution

1. Acessar Evolution API
2. Criar nova instância para a padaria
3. Escanear QR Code com WhatsApp Business do dono
4. Configurar webhook para apontar para n8n

**Webhook Evolution → n8n:**
```
URL: https://n8n.seudominio.com/webhook/whatsapp-incoming
```

#### 5.2 Dados que chegam da Evolution

```json
{
  "event": "messages.upsert",
  "instance": "padaria-pao-quente",
  "data": {
    "key": {
      "remoteJid": "5511999999999@s.whatsapp.net",
      "fromMe": false,
      "id": "msg123"
    },
    "message": {
      "conversation": "Olá, vocês abrem que horas amanhã?"
    },
    "pushName": "Cliente João"
  }
}
```

---

### Etapa 6: Cliente Envia Mensagem no WhatsApp

#### 6.1 Fluxo da Mensagem

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FLUXO DE MENSAGEM                               │
└─────────────────────────────────────────────────────────────────────────┘

1. CLIENTE envia mensagem no WhatsApp
   │
   ▼
2. EVOLUTION API captura a mensagem
   │
   ▼
3. Webhook dispara para N8N com dados da mensagem
   │
   ▼
4. N8N identifica a instância (padaria) pelo campo "instance"
   │
   ▼
5. N8N busca no SUPABASE qual agente/API Key corresponde
   │
   ▼
6. N8N chama DJANGO API para buscar config do agente
   │  GET /api/n8n/agents/{slug}/config
   │
   ▼
7. N8N busca CONTEXTO RAG no SUPABASE
   │  (busca vetorial com a mensagem do cliente)
   │
   ▼
8. N8N monta PROMPT para OPENAI/LLM:
   │  - System: Personalidade + Conhecimento + Contexto RAG
   │  - User: Mensagem do cliente
   │
   ▼
9. LLM gera RESPOSTA
   │
   ▼
10. N8N envia resposta via EVOLUTION API
    │
    ▼
11. CLIENTE recebe resposta no WhatsApp ✅
```

#### 6.2 Exemplo de Conversa

```
╔═══════════════════════════════════════════════════════════════════════╗
║ WhatsApp - Padaria Pão Quente                                         ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  👤 Cliente (11) 99999-8888                                           ║
║  ───────────────────────────                                          ║
║  Olá, vocês abrem que horas amanhã?                            10:30  ║
║                                                                       ║
║  🤖 Maria (Agente IA)                                                 ║
║  ─────────────────────                                                ║
║  Olá! Bom dia! 🥐                                              10:30  ║
║                                                                       ║
║  Amanhã é sábado, então estaremos abertos das                         ║
║  06:00 às 14:00! Vou adorar te atender. 😊                            ║
║                                                                       ║
║  Precisa encomendar algo especial?                                    ║
║                                                                       ║
║  👤 Cliente                                                           ║
║  ───────────────────────────                                          ║
║  Quanto custa o pão de queijo?                                 10:31  ║
║                                                                       ║
║  🤖 Maria                                                             ║
║  ─────────────────────                                                ║
║  O pão de queijo custa R$ 3,00 a unidade! 🧀                   10:31  ║
║                                                                       ║
║  Ele é feito fresquinho toda manhã. Posso separar               ║
║  quantas unidades para você?                                          ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
```

---

### Etapa 7: Dono Recebe e Acompanha as Conversas

#### 7.1 Onde o Dono Monitora

O dono da padaria tem acesso aos atendimentos de várias formas:

**1. No próprio WhatsApp:**
- O número da padaria recebe todas as mensagens
- O dono vê o histórico completo no celular

**2. No Painel Django:**
```
URL: /agents/{slug}/
```
- Ver logs de auditoria das chamadas de API
- Estatísticas de uso (futuro)

**3. Dashboard N8N (se tiver acesso):**
- Ver execuções do workflow
- Debug de erros

#### 7.2 Logs de Auditoria

Toda chamada à API é registrada:

```python
AuditLog.log(
    action="api_call",
    entity="Agent",
    padaria=padaria,
    entity_id=agent.id,
    diff={
        "endpoint": "get_agent_config",
        "slug": slug
    },
    ip="192.168.1.1",
    user_agent="n8n/1.0"
)
```

**Visualizar logs:**
```
URL: /admin-panel/logs/  (apenas admin)
URL: /agents/{slug}/     (dono vê logs do seu agente)
```

---

## 🏗️ Diagrama de Arquitetura

```
                                    ┌─────────────────────────────────────────────────┐
                                    │               INFRAESTRUTURA                     │
                                    └─────────────────────────────────────────────────┘
                                    
     ┌─────────────┐                     ┌─────────────┐                    ┌──────────────┐
     │   CLIENTE   │                     │    N8N      │                    │    ADMIN     │
     │ (WhatsApp)  │                     │ (Automação) │                    │   MASTER     │
     └──────┬──────┘                     └──────┬──────┘                    └──────┬───────┘
            │                                   │                                   │
            │ 📱 Mensagem                       │                                   │ 🔧 Gerencia
            ▼                                   ▼                                   ▼
┌───────────────────────┐           ┌───────────────────────┐           ┌───────────────────────┐
│                       │           │                       │           │                       │
│   EVOLUTION API       │◀─────────▶│      DJANGO SAAS      │◀─────────▶│    PAINEL ADMIN       │
│   (WhatsApp Gateway)  │           │    (Backend Core)     │           │   /admin-panel/       │
│                       │           │                       │           │                       │
│   - Recebe mensagens  │           │   - Padarias          │           │   - Criar padarias    │
│   - Envia respostas   │           │   - Agentes           │           │   - Gerenciar users   │
│   - WebSocket         │           │   - API Keys          │           │   - Ver logs          │
│                       │           │   - Logs              │           │                       │
└───────────┬───────────┘           └───────────┬───────────┘           └───────────────────────┘
            │                                   │
            │ Webhook                           │ API REST
            ▼                                   ▼
┌───────────────────────┐           ┌───────────────────────┐
│                       │           │                       │
│        N8N            │──────────▶│      SUPABASE         │
│    (Workflow Engine)  │           │   (Database + RAG)    │
│                       │           │                       │
│   - Processa msgs     │           │   - Tabela agentes    │
│   - Chama APIs        │           │   - Tabelas RAG       │
│   - Integra LLM       │           │   - Vetores/Embeddings│
│                       │           │                       │
└───────────┬───────────┘           └───────────────────────┘
            │
            │ API Request
            ▼
┌───────────────────────┐
│                       │
│      OPENAI / LLM     │
│   (Geração de texto)  │
│                       │
│   - GPT-4 / GPT-3.5   │
│   - Gemini            │
│   - Claude            │
│                       │
└───────────────────────┘
```

---

## ✅ Checklist de Configuração

### Para o Admin Master

- [ ] **1. Criar Padaria**
  - [ ] Preencher dados da empresa
  - [ ] Criar usuário dono
  - [ ] Verificar API Key gerada

### Para o Dono da Padaria

- [ ] **2. Primeiro Acesso**
  - [ ] Login com credenciais recebidas
  - [ ] Trocar senha (recomendado)

- [ ] **3. Criar Agente**
  - [ ] Definir nome e personalidade
  - [ ] Configurar saudação
  - [ ] Preencher base de conhecimento
  - [ ] Upload de PDF (opcional)
  - [ ] Copiar e guardar API Key

### Para Integração (Técnico)

- [ ] **4. Configurar Evolution API**
  - [ ] Criar instância WhatsApp
  - [ ] Conectar número (QR Code)
  - [ ] Configurar webhook para n8n

- [ ] **5. Configurar N8N**
  - [ ] Importar workflow base
  - [ ] Configurar credenciais Evolution
  - [ ] Configurar endpoint Django API
  - [ ] Configurar credenciais Supabase
  - [ ] Configurar API Key OpenAI
  - [ ] Testar fluxo completo

- [ ] **6. Verificar Supabase**
  - [ ] Agente registrado na tabela `agentes`
  - [ ] Tabela RAG criada (`rag_{padaria_slug}`)
  - [ ] Embeddings funcionando

### Teste Final

- [ ] **7. Validação End-to-End**
  - [ ] Enviar mensagem de teste no WhatsApp
  - [ ] Verificar resposta do agente
  - [ ] Checar logs no Django
  - [ ] Verificar execução no n8n

---

## 📞 Suporte

Para problemas ou dúvidas:

1. **Logs Django:** Console do servidor ou `/admin-panel/logs/`
2. **Logs N8N:** Execuções do workflow
3. **Evolution API:** Dashboard de instâncias
4. **Supabase:** SQL Editor para debug

---

**Versão:** 1.0.0  
**Última atualização:** Dezembro 2025  
**Autor:** Sistema InnoTalk Agent
