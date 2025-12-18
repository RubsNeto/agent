# ============================================
# Dockerfile para Django MVP - Docker Swarm
# ============================================
FROM python:3.12-slim

# Variáveis de ambiente para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primeiro (melhor cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do projeto
COPY . .

# Criar diretórios necessários e usuário não-root
RUN mkdir -p /app/staticfiles /app/media /app/data \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# Copiar e dar permissão ao entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Mudar para usuário não-root
USER appuser

# Porta do Gunicorn
EXPOSE 8000

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]
