#!/bin/bash
set -e

# Configurações
APP_DIR="/opt/apps/agentesai/agent"
SERVICE_NAME="agentesai_web"

echo "🚀 Iniciando deploy automático..."

# 1. Navegar para o diretório
cd $APP_DIR

# 2. Resetar mudanças locais (evita conflito no git pull)
echo "🧹 Limpando mudanças locais..."
git checkout .
git clean -fd

# 3. Baixar código novo
echo "📥 Baixando atualizações..."
git pull origin main

# 4. Reconstruir imagem (Sempre sem cache para garantir atualizações de libs/static)
echo "🔨 Reconstruindo imagem Docker (no-cache)..."
docker build --no-cache -t agentesai:latest .

# 5. Atualizar ou criar stack
echo "🔄 Atualizando stack..."
docker stack deploy -c stack.yml agentesai

# 6. Forçar atualização do serviço para pegar a nova imagem
echo "⚡ Reiniciando serviço..."
docker service update --force $SERVICE_NAME

# 7. Limpar imagens antigas (prune) para economizar espaço
echo "🗑️ Limpando imagens não utilizadas..."
docker image prune -a -f --filter "until=24h"

echo "✅ Deploy concluído com sucesso!"
docker service ls | grep $SERVICE_NAME
