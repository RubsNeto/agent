#  Fluxo de Uso do Sistema - Pandia

> Documento que descreve o fluxo completo desde a criação de uma padaria pelo Admin até a recepção de mensagens no WhatsApp, gerenciamento de promoções e campanhas.

---

##  Índice

1. [Visão Geral do Sistema](#visão-geral-do-sistema)
2. [Papéis e Permissões](#papéis-e-permissões)
3. [Fluxo Completo](#fluxo-completo)
   - [Etapa 1: Admin Master Cria a Padaria](#etapa-1-admin-master-cria-a-padaria)
   - [Etapa 2: Dono da Padaria Acessa o Sistema](#etapa-2-dono-da-padaria-acessa-o-sistema)
   - [Etapa 3: Criação do Agente de IA](#etapa-3-criação-do-agente-de-ia)
   - [Etapa 4: Gestão de Promoções](#etapa-4-gestão-de-promoções)
   - [Etapa 5: Gestão de Clientes](#etapa-5-gestão-de-clientes)
   - [Etapa 6: Campanhas de WhatsApp](#etapa-6-campanhas-de-whatsapp)
   - [Etapa 7: Integração com n8n e Evolution API](#etapa-7-integração-com-n8n-e-evolution-api)
   - [Etapa 8: Cliente Envia Mensagem no WhatsApp](#etapa-8-cliente-envia-mensagem-no-whatsapp)
4. [Diagrama de Arquitetura](#diagrama-de-arquitetura)
5. [Endpoints da API](#endpoints-da-api)
6. [Checklist de Configuração](#checklist-de-configuração)

---

##  Visão Geral do Sistema

O sistema é uma plataforma SaaS para gerenciamento de **agentes de IA** que atendem clientes via **WhatsApp**. Cada padaria cadastrada pode ter seu próprio agente de IA personalizado, gerenciar promoções e enviar campanhas para clientes.

### Componentes Principais

| Componente | Descrição |
|------------|-----------|
| **Django SaaS** | Backend que gerencia padarias, agentes, promoções, clientes e campanhas |
| **n8n** | Orquestrador de automações (recebe mensagens, processa com IA, responde) |
| **Evolution API** | Conecta com WhatsApp Business |
| **Supabase** | Banco de dados para RAG (memória vetorial do agente) |
| **OpenAI/LLM** | Modelo de linguagem para gerar respostas |

### Funcionalidades do Sistema

-  Gerenciamento de Padarias (multi-tenant)
-  Criação e configuração de Agentes de IA
-  API Keys vinculadas a agentes específicos
-  Base de conhecimento (texto + PDF)
-  Gestão de Promoções com validade
-  Cadastro de Clientes
-  Campanhas de WhatsApp com delay inteligente
-  Logs de auditoria
-  Integração com n8n e Evolution API

---

##  Papéis e Permissões

| Papel | Permissões |
|-------|------------|
| **Admin Master** | Acesso total: criar/editar/deletar padarias, usuários, ver logs globais |
| **Dono da Padaria** | Gerenciar seu agente, promoções, clientes, campanhas, ver API Keys |
| **Funcionário** | Visualizar e editar configurações (acesso limitado) |

---

##  Fluxo Completo

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
| Nome da Padaria | Padaria Pão Quente |  Sim |
| CNPJ | 12.345.678/0001-90 | Não |
| Telefone | (11) 99999-9999 | Não |
| E-mail | contato@paoquente.com.br | Não |
| Endereço | Rua das Flores, 123 | Não |

**Dados do Usuário Dono:**
| Campo | Exemplo | Obrigatório |
|-------|---------|-------------|
| Nome Completo | João Silva |  Sim |
| E-mail | joao@paoquente.com.br |  Sim |
| Senha | (mínimo 6 caracteres) |  Sim |

#### 1.3 O que acontece ao salvar

O sistema automaticamente:

1.  Cria o **usuário dono** com as credenciais informadas
2.  Cria a **padaria** com os dados de empresa
3.  Gera o **slug** único (ex: `padaria-pao-quente`)
4.  Vincula o usuário como **membro** (role: `dono`)
5.  Gera uma **API Key** inicial para a padaria
6.  Registra a ação no **log de auditoria**

#### 1.4 Resultado

O admin vê mensagem de sucesso:
```
 Padaria 'Padaria Pão Quente' criada com sucesso! 
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

**Função e Personalidade:**
| Campo | Opções | Descrição |
|-------|--------|-----------|
| Função | Atendente, Recepcionista, Consultor, Vendedor, Suporte, Assistente, Gerente, Especialista | Define comportamento base |
| Tom de Voz | Formal, Casual, Amigável, Profissional, Objetivo e Direto, Simpático e Acolhedor, etc. | Tom nas respostas |
| Status | Ativo, Inativo, Manutenção | Se recebe mensagens |

**Mensagens Customizáveis:**
| Campo | Padrão |
|-------|--------|
| Saudação | "Olá! Eu sou {{agente_nome}}, assistente virtual da {{padaria_nome}}..." |
| Fora do Horário | "No momento estamos fora do horário de atendimento..." |
| Fallback | "Desculpe, não entendi. Pode reformular?" |
| Regra de Escalonamento | "Transferir para atendente humano quando..." |

**Base de Conhecimento:**
- **Texto Markdown:** Informações sobre produtos, preços, políticas
- **Upload PDF:** Documento com cardápio, FAQ, etc.

**Horário de Funcionamento:**
```json
{
  "mon": "06:00-20:00",
  "tue": "06:00-20:00",
  "wed": "06:00-20:00",
  "thu": "06:00-20:00",
  "fri": "06:00-20:00",
  "sat": "06:00-14:00",
  "sun": "closed"
}
```

#### 3.3 O que acontece ao salvar

1.  Salva o agente no banco de dados
2.  Gera slug único (ex: `maria-padaria-pao-quente`)
3.  Processa PDF (se enviado) e extrai texto
4.  Gera **API Key vinculada ao agente**
5.  Sincroniza com Supabase (se configurado)
6.  Notifica n8n via webhook (se configurado)

#### 3.4 Resultado

Mensagem exibida ao dono:
```
 Agente 'Maria' criado com sucesso! 

 API Key gerada: sk_abcdef123456...

 Copie a chave agora! Ela não será exibida novamente.
```

---

### Etapa 4: Gestão de Promoções

#### 4.1 Criar Promoção

```
URL: /organizations/promocoes/create/
```

**Campos:**
| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| Título | Nome da promoção | Pão Francês em Dobro |
| Descrição | Detalhes da oferta | Leve 12, pague 10 |
| Preço Promocional | Valor com desconto | R$ 5,00 |
| Preço Original | Valor original | R$ 6,00 |
| Imagem | Foto do produto | (upload) |
| Data de Início | Quando inicia | 2025-01-01 |
| Data de Validade | Quando expira | 2025-01-15 |

#### 4.2 Lista de Promoções

```
URL: /organizations/promocoes/
```

- Ver todas as promoções da padaria
- Editar/Excluir promoções
- Criar campanha a partir de uma promoção

---

### Etapa 5: Gestão de Clientes

#### 5.1 Cadastrar Cliente

```
URL: /organizations/clientes/create/
```

**Campos:**
| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| Nome | Nome do cliente | Maria Silva |
| Telefone/WhatsApp | Número com DDD | (11) 99999-9999 |
| E-mail | E-mail (opcional) | maria@email.com |
| Aceita Promoções | Autoriza mensagens |  Sim |
| Observações | Notas adicionais | Cliente VIP |

#### 5.2 Importar Clientes

```
URL: /organizations/clientes/import/
```

Importação em massa via arquivo CSV/Excel.

#### 5.3 Lista de Clientes

```
URL: /organizations/clientes/
```

- Ver todos os clientes cadastrados
- Editar/Excluir clientes
- Filtrar por status (ativo/inativo)

---

### Etapa 6: Campanhas de WhatsApp

#### 6.1 Criar Campanha

```
URL: /organizations/campanhas/create/
```

**Campos:**
| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| Nome | Nome da campanha | Promoção de Natal |
| Promoção Vinculada | Promoção associada (opcional) | Pão Francês em Dobro |
| Mensagem | Texto da mensagem | Olá {{nome_cliente}}! Aproveite nossa promoção... |
| Imagem | Imagem para enviar (opcional) | (upload) |

**Configurações de Envio (Anti-ban):**
| Campo | Descrição | Padrão |
|-------|-----------|--------|
| Delay Mínimo | Segundos entre mensagens | 10 |
| Delay Máximo | Segundos entre mensagens | 30 |
| Tamanho do Lote | Mensagens por lote | 10 |
| Pausa entre Lotes | Segundos de pausa | 60 |

#### 6.2 Enviar Campanha

```
URL: /organizations/campanhas/{id}/
```

1. Ver detalhes da campanha
2. Selecionar destinatários (clientes que aceitam promoções)
3. Clicar em **"Iniciar Campanha"**
4. Acompanhar progresso em tempo real

#### 6.3 Status da Campanha

| Status | Descrição |
|--------|-----------|
| Rascunho | Campanha criada, não iniciada |
| Agendada | Aguardando data de agendamento |
| Enviando | Em processo de envio |
| Pausada | Pausada pelo usuário |
| Concluída | Todas as mensagens enviadas |
| Cancelada | Campanha cancelada |
| Erro | Falha no envio |

#### 6.4 Estatísticas

- Total de destinatários
- Mensagens enviadas
- Falhas de envio
- Porcentagem de progresso

---

### Etapa 7: Integração com n8n e Evolution API

#### 7.1 Estrutura do Workflow n8n

```
          
  Evolution API       n8n Flow        Evolution API   
  (Recebe msg)            (Processa)            (Envia resposta)
          
                                  
                    
                                              
                
               Django     Supabase   OpenAI   
               API        RAG        LLM      
                
```

#### 7.2 Buscar Configuração do Agente

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
  "sector": "padaria",
  "language": "pt-BR",
  "greeting": "Olá! Eu sou Maria, assistente virtual da Padaria Pão Quente!",
  "tone": "amigavel",
  "personality": "amigavel",
  "style_guidelines": "Use linguagem simples e amigável...",
  "business_hours": {
    "mon": "06:00-20:00",
    "tue": "06:00-20:00",
    "sat": "06:00-14:00",
    "sun": "closed"
  },
  "fallback_message": "Desculpe, não entendi...",
  "escalation_rule": "Transferir quando cliente pedir humano...",
  "padaria": {
    "name": "Padaria Pão Quente",
    "slug": "padaria-pao-quente"
  },
  "updated_at": "2025-12-18T12:00:00Z"
}
```

#### 7.3 Buscar Base de Conhecimento

**Endpoint separado (para não sobrecarregar):**
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

### Etapa 8: Cliente Envia Mensagem no WhatsApp

#### 8.1 Fluxo da Mensagem

```

                         FLUXO DE MENSAGEM                               


1. CLIENTE envia mensagem no WhatsApp
   
   
2. EVOLUTION API captura a mensagem
   
   
3. Webhook dispara para N8N com dados da mensagem
   
   
4. N8N identifica a instância (padaria) pelo campo "instance"
   
   
5. N8N busca no SUPABASE qual agente/API Key corresponde
   
   
6. N8N chama DJANGO API para buscar config do agente
     GET /api/n8n/agents/{slug}/config
   
   
7. N8N busca BASE DE CONHECIMENTO
     GET /api/n8n/agents/{slug}/knowledge
   
   
8. N8N monta PROMPT para OPENAI/LLM:
     - System: Personalidade + Conhecimento
     - User: Mensagem do cliente
   
   
9. LLM gera RESPOSTA
   
   
10. N8N envia resposta via EVOLUTION API
    
    
11. CLIENTE recebe resposta no WhatsApp 
```

#### 8.2 Exemplo de Conversa

```

 WhatsApp - Padaria Pão Quente                                         

                                                                       
   Cliente (11) 99999-8888                                           
                                            
  Olá, vocês abrem que horas amanhã?                            10:30  
                                                                       
   Maria (Agente IA)                                                 
                                                  
  Olá! Bom dia!                                               10:30  
                                                                       
  Amanhã é sábado, então estaremos abertos das                         
  06:00 às 14:00! Vou adorar te atender.                             
                                                                       
  Precisa encomendar algo especial?                                    
                                                                       
   Cliente                                                           
                                            
  Quanto custa o pão de queijo?                                 10:31  
                                                                       
   Maria                                                             
                                                  
  O pão de queijo custa R$ 3,00 a unidade!                    10:31  
                                                                       
  Ele é feito fresquinho toda manhã. Posso separar                     
  quantas unidades para você?                                          
                                                                       

```

---

##  Diagrama de Arquitetura

```
                                    
                                                   INFRAESTRUTURA                     
                                    
                                    
                                              
        CLIENTE                            N8N                              ADMIN     
      (WhatsApp)                        (Automação)                        MASTER     
                                              
                                                                                  
              Mensagem                                                            Gerencia
                                                                                  
                      
                                                                                           
   EVOLUTION API             DJANGO SAAS          PAINEL ADMIN       
   (WhatsApp Gateway)                 (Backend Core)                   /admin-panel/       
                                                                                           
   - Recebe mensagens                - Padarias                        - Criar padarias    
   - Envia respostas                 - Agentes                         - Gerenciar users   
   - Campanhas                       - Promoções                       - Ver logs          
                                     - Clientes                                            
              - Campanhas                    
                                      - API Keys          
             Webhook                  - Logs              
                                   
                       
                                               API REST
        N8N                                   
    (Workflow Engine)             
                             SUPABASE         
   - Processa msgs                   (Database + RAG)    
   - Chama APIs                                          
   - Integra LLM                     - Tabela agentes    
                                     - Tabelas RAG       
              - Vetores/Embeddings
                                                          
             API Request           
            

                       
      OPENAI / LLM     
   (Geração de texto)  
                       
   - GPT-4 / GPT-3.5   
   - Gemini            
   - Claude            
                       

```

---

##  Endpoints da API

### Autenticação

Todas as requisições devem incluir a API Key:

**Via Header (recomendado):**
```
Authorization: Bearer sk_sua_api_key_aqui
```

**Via Query Parameter:**
```
?api_key=sk_sua_api_key_aqui
```

### Endpoints Disponíveis

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/n8n/agents/{slug}/config` | Configuração do agente |
| GET | `/api/n8n/agents/{slug}/knowledge` | Base de conhecimento |
| GET | `/api/docs/` | Documentação da API |

### Rate Limiting

- **Limite:** 60 requisições por minuto por IP
- **Resposta 429:** Rate limit exceeded

### Códigos de Resposta

| Código | Descrição |
|--------|-----------|
| 200 | Sucesso |
| 401 | API Key inválida ou ausente |
| 403 | API Key sem permissão para este agente |
| 404 | Agente não encontrado |
| 429 | Rate limit excedido |

---

##  Checklist de Configuração

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

- [ ] **4. Cadastrar Promoções**
  - [ ] Criar promoções ativas
  - [ ] Definir preços e validade
  - [ ] Adicionar imagens

- [ ] **5. Cadastrar Clientes**
  - [ ] Importar base de clientes
  - [ ] Verificar aceite de promoções

- [ ] **6. Criar Campanhas**
  - [ ] Selecionar promoção
  - [ ] Configurar delays anti-ban
  - [ ] Testar com poucos destinatários

### Para Integração (Técnico)

- [ ] **7. Configurar Evolution API**
  - [ ] Criar instância WhatsApp
  - [ ] Conectar número (QR Code)
  - [ ] Configurar webhook para n8n

- [ ] **8. Configurar N8N**
  - [ ] Importar workflow base
  - [ ] Configurar credenciais Evolution
  - [ ] Configurar endpoint Django API
  - [ ] Configurar credenciais Supabase
  - [ ] Configurar API Key OpenAI
  - [ ] Testar fluxo completo

- [ ] **9. Verificar Supabase**
  - [ ] Agente registrado na tabela `agentes`
  - [ ] Tabela RAG criada
  - [ ] Embeddings funcionando

### Teste Final

- [ ] **10. Validação End-to-End**
  - [ ] Enviar mensagem de teste no WhatsApp
  - [ ] Verificar resposta do agente
  - [ ] Checar logs no Django
  - [ ] Verificar execução no n8n
  - [ ] Testar envio de campanha

---

##  URLs Principais do Sistema

| URL | Descrição |
|-----|-----------|
| `/` | Dashboard |
| `/accounts/login/` | Login |
| `/accounts/logout/` | Logout |
| `/agents/` | Lista de agentes |
| `/agents/create/` | Criar agente |
| `/agents/{slug}/` | Detalhes/Editar agente |
| `/organizations/` | Lista de padarias |
| `/organizations/{slug}/` | Detalhes da padaria |
| `/organizations/apikeys/` | Gerenciar API Keys |
| `/organizations/promocoes/` | Lista de promoções |
| `/organizations/clientes/` | Lista de clientes |
| `/organizations/campanhas/` | Lista de campanhas |
| `/admin-panel/` | Painel Admin Master |
| `/api/docs/` | Documentação da API |

---

##  Suporte

Para problemas ou dúvidas:

1. **Logs Django:** Console do servidor ou `/admin-panel/logs/`
2. **Logs N8N:** Execuções do workflow
3. **Evolution API:** Dashboard de instâncias
4. **Supabase:** SQL Editor para debug

---

**Versão:** 2.0.0  
**Última atualização:** Dezembro 2025  
**Sistema:** Pandia
