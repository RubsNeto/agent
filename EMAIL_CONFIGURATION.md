# Configuração de Email para Recuperação de Senha

## Status Atual

✅ **Funcionalidade implementada e pronta**
- URLs de reset de senha configuradas
- 4 templates criados (formulário, confirmação, redefinição, sucesso)
- Templates de email configurados
- Link "Esqueceu a senha?" adicionado na tela de login
- Email backend configurado (console em dev, SMTP em produção)

## Modo Desenvolvimento (Atual)

Em desenvolvimento (DEBUG=True), os emails são impressos no console/terminal.

**Para testar:**
1. Acesse a tela de login
2. Clique em "Esqueceu a senha?"
3. Digite um email cadastrado
4. O email será impresso no console do Django
5. Copie o link do email e acesse no navegador
6. Defina a nova senha

## Configuração para Produção

Para enviar emails reais em produção, adicione no arquivo `.env`:

```bash
# Email SMTP Settings
EMAIL_HOST=smtp.gmail.com              # Servidor SMTP
EMAIL_PORT=587                         # Porta SMTP (587 para TLS, 465 para SSL)
EMAIL_USE_TLS=True                     # Usar TLS
EMAIL_HOST_USER=seu-email@gmail.com    # Email remetente
EMAIL_HOST_PASSWORD=sua-senha-app       # Senha de aplicativo
DEFAULT_FROM_EMAIL=noreply@pandia.com.br  # Email de exibição
```

### Opções de Serviços SMTP

#### 1. **Gmail** (Recomendado para testes)
```bash
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=senha-de-aplicativo
```

**Como gerar senha de aplicativo:**
1. Acesse https://myaccount.google.com/security
2. Ative "Verificação em 2 etapas"
3. Vá em "Senhas de app"
4. Gere uma senha para "Email"
5. Use essa senha no EMAIL_HOST_PASSWORD

**Limitações:** 500 emails/dia

#### 2. **SendGrid** (Recomendado para produção)
```bash
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=sua-api-key-sendgrid
```

**Vantagens:**
- 100 emails grátis/dia
- Confiável e profissional
- Dashboard de analytics

**Como configurar:**
1. Crie conta em https://sendgrid.com
2. Vá em Settings > API Keys
3. Crie uma API Key com permissão "Mail Send"
4. Use "apikey" como EMAIL_HOST_USER
5. Use a API Key como EMAIL_HOST_PASSWORD

#### 3. **AWS SES** (Mais escalável)
```bash
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-access-key
EMAIL_HOST_PASSWORD=seu-secret-key
```

**Vantagens:**
- $0.10 por 1000 emails
- Altamente escalável
- Integração com AWS

#### 4. **Mailgun**
```bash
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=postmaster@seu-dominio.mailgun.org
EMAIL_HOST_PASSWORD=sua-senha-mailgun
```

## Testando a Funcionalidade

### Em Desenvolvimento (Local)
```bash
# Inicie o servidor
python manage.py runserver

# Os emails aparecerão no console do terminal
```

### Em Produção (pandia.com.br)
Após configurar as variáveis de ambiente no servidor:

```bash
# SSH no servidor
ssh seu-usuario@pandia.com.br

# Edite o .env
nano .env

# Adicione as configurações de email
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SUA_SENDGRID_API_KEY
DEFAULT_FROM_EMAIL=noreply@pandia.com.br

# Salve (Ctrl+O, Enter, Ctrl+X)

# Reinicie o serviço Docker
docker-compose restart web
```

## Fluxo Completo

1. **Usuário esqueceu a senha:**
   - Acessa /login
   - Clica em "Esqueceu a senha?"
   - Digite o email

2. **Sistema envia email:**
   - Gera token único de recuperação
   - Envia email com link válido por 24h
   - Redireciona para tela de confirmação

3. **Usuário recebe email:**
   - Clica no link do email
   - É redirecionado para página de redefinição

4. **Usuário define nova senha:**
   - Digite senha nova (2x)
   - Sistema valida requisitos
   - Senha é redefinida

5. **Confirmação:**
   - Tela de sucesso
   - Botão para fazer login
   - Usuário pode entrar com nova senha

## Arquivos Criados

```
templates/accounts/
├── password_reset.html             # Formulário solicitar reset
├── password_reset_done.html        # Confirmação email enviado
├── password_reset_confirm.html     # Formulário nova senha
├── password_reset_complete.html    # Sucesso
├── password_reset_email.html       # Template do email
└── password_reset_subject.txt      # Assunto do email
```

## Próximos Passos

1. ✅ Funcionalidade implementada
2. ⏳ Testar fluxo completo em desenvolvimento
3. ⏳ Configurar SMTP em produção (SendGrid recomendado)
4. ⏳ Testar em produção com email real
5. ⏳ Desativar DEBUG após confirmar tudo funcionando

## Notas de Segurança

- Links de reset expiram em 24 horas
- Token único por solicitação
- Senha deve ter mínimo 8 caracteres
- Não pode ser muito comum
- Não pode ser apenas numérica
- Link só funciona uma vez
