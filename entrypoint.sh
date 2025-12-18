#!/bin/bash
set -e

echo "=== Django Entrypoint ==="

# Aguardar um momento para garantir que volumes estão montados
sleep 2

# Rodar migrações
echo "[1/3] Aplicando migrações..."
python manage.py migrate --noinput

# Coletar arquivos estáticos
echo "[2/3] Coletando arquivos estáticos..."
python manage.py collectstatic --noinput --clear

# Iniciar Gunicorn
echo "[3/3] Iniciando Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 2 \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --log-level info
