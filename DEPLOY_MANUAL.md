# 🚀 Deploy Manual - pandia.com.br

> Guia passo a passo para atualizar a aplicação no servidor.

---

## 📋 Pré-requisitos

- Acesso SSH ao servidor
- Docker instalado no servidor
- Git configurado

---

## 🔄 Passos para Atualizar

### Opção A: Build no Servidor (Recomendado)

```bash
# 1. Conectar no servidor via SSH
ssh usuario@seu-servidor

# 2. Ir para o diretório do projeto
cd /caminho/para/agent

# 3. Puxar as últimas alterações do Git
git pull origin main

# 4. Fazer build da nova imagem Docker
docker build -t agentesai:latest .

# 5. Atualizar o stack (deploy)
docker stack deploy -c stack.yml agentesai

# 6. Verificar se o serviço está rodando
docker service ls
docker service ps agentesai_web

# 7. Ver logs (opcional)
docker service logs agentesai_web -f --tail 50
```

### Opção B: Build Local + Enviar para Servidor

```powershell
# === NO SEU PC (Windows) ===

# 1. Fazer commit das alterações
git add .
git commit -m "Descrição da alteração"
git push origin main
```

```bash
# === NO SERVIDOR ===

# 2. Conectar via SSH
ssh usuario@seu-servidor

# 3. Navegar para o projeto e atualizar
cd /caminho/para/agent
git pull origin main

# 4. Rebuild e redeploy
docker build -t agentesai:latest .
docker stack deploy -c stack.yml agentesai
```

---

## ⚡ Comando Rápido (Tudo em Uma Linha)

Se já estiver no diretório do projeto no servidor:

```bash
git pull && docker build -t agentesai:latest . && docker stack deploy -c stack.yml agentesai
```

---

## 🔍 Verificar Status

```bash
# Ver serviços do stack
docker stack services agentesai

# Ver containers rodando
docker ps

# Ver logs em tempo real
docker service logs agentesai_web -f

# Ver status detalhado do serviço
docker service ps agentesai_web --no-trunc
```

---

## 🔧 Comandos Úteis

### Reiniciar o serviço (sem rebuild)
```bash
docker service update --force agentesai_web
```

### Escalar réplicas (se precisar)
```bash
docker service scale agentesai_web=2
```

### Remover o stack completamente
```bash
docker stack rm agentesai
```

### Ver uso de recursos
```bash
docker stats
```

---

## ⚠️ Troubleshooting

### Serviço não inicia
```bash
# Ver logs de erro
docker service logs agentesai_web --tail 100

# Ver eventos do container
docker service ps agentesai_web --no-trunc
```

### Erro de permissão no SQLite
```bash
# Verificar volumes
docker volume ls | grep agentesai

# Se necessário, recriar volumes (CUIDADO: perde dados!)
# docker volume rm agentesai_sqlite_data
```

### Erro de rede
```bash
# Verificar se a rede existe
docker network ls | grep mysellerynet

# Se não existir, criar
docker network create --driver overlay --attachable mysellerynet
```

### Limpar imagens antigas
```bash
docker image prune -a
```

---

## 📝 Checklist Pré-Deploy

- [ ] Testou localmente (`python manage.py runserver`)?
- [ ] Migrations estão atualizadas?
- [ ] Arquivos estáticos coletados (`collectstatic`)?
- [ ] Commit feito com mensagem descritiva?
- [ ] Push para o repositório?

---

## 🔐 Variáveis de Ambiente

Certifique-se que estas variáveis estão configuradas no servidor:

```bash
export SECRET_KEY="sua-chave-secreta-aqui"
export ALLOWED_HOSTS="pandia.com.br,www.pandia.com.br"
export CSRF_TRUSTED_ORIGINS="https://pandia.com.br,https://www.pandia.com.br"
```

Ou crie um arquivo `.env` no servidor e use com docker stack:

```bash
# Carregar variáveis antes do deploy
source .env && docker stack deploy -c stack.yml agentesai
```

---

**Última atualização:** Dezembro 2025
