"""
Supabase Integration Client

Funções para sincronizar agentes e criar tabelas RAG no Supabase.
"""
import os
import requests
import logging
from django.utils.text import slugify

logger = logging.getLogger(__name__)

# Configurações do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def get_headers():
    """Retorna headers para autenticação no Supabase."""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }


def sync_agent_to_supabase(slug, api_key, padaria_name, agent_name, phone=""):
    """
    Insere ou atualiza dados do agente na tabela 'agentes' do Supabase.
    
    Args:
        slug: Slug único do agente
        api_key: Chave de API gerada
        padaria_name: Nome da padaria
        agent_name: Nome do agente
        phone: Telefone (opcional)
    
    Returns:
        bool: True se sucesso, False se erro
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase não configurado. Pulando sincronização.")
        return False
    
    try:
        url = f"{SUPABASE_URL}/rest/v1/agentes"
        
        data = {
            "slug": slug,
            "api_key": api_key,
            "padaria_name": padaria_name,
            "agent_name": agent_name,
            "phone": phone or ""
        }
        
        response = requests.post(
            url,
            json=data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"Agente '{slug}' sincronizado com Supabase com sucesso!")
            return True
        else:
            logger.error(f"Erro ao sincronizar agente: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão com Supabase: {str(e)}")
        return False


def create_rag_table(slug):
    """
    Cria uma tabela RAG dinâmica no Supabase para o agente.
    Nome da tabela: rag_{slug_sanitizado}
    
    Estrutura:
    - id (int8, primary key)
    - content (text)
    - metadata (jsonb)
    - embedding (vector)
    
    Args:
        slug: Slug do agente (será sanitizado para nome de tabela)
    
    Returns:
        bool: True se sucesso, False se erro
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase não configurado. Pulando criação de tabela RAG.")
        return False
    
    # Sanitizar slug para nome de tabela válido
    table_name = f"rag_{slugify(slug).replace('-', '_')}"
    
    try:
        # Usar a API de SQL do Supabase para criar a tabela
        url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
        
        # SQL para criar tabela com extensão vector
        sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id BIGSERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            metadata JSONB DEFAULT '{{}}',
            embedding vector(1536)
        );
        
        CREATE INDEX IF NOT EXISTS idx_{table_name}_embedding 
        ON {table_name} USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
        """
        
        response = requests.post(
            url,
            json={"query": sql},
            headers=get_headers(),
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"Tabela RAG '{table_name}' criada com sucesso!")
            return True
        else:
            # Se RPC não existir, tentar via SQL direto (menos seguro mas funcional)
            logger.warning(f"RPC exec_sql não disponível, tentando método alternativo...")
            return create_rag_table_alternative(table_name)
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao criar tabela RAG: {str(e)}")
        return False


def create_rag_table_alternative(table_name):
    """
    Método alternativo para criar tabela RAG via RPC function.
    """
    try:
        url = f"{SUPABASE_URL}/rest/v1/rpc/create_rag_table"
        
        headers = get_headers()
        headers["Prefer"] = "return=representation"  # Retornar resultado
        
        print(f"[DEBUG] Chamando RPC create_rag_table com table_name={table_name}")
        print(f"[DEBUG] URL: {url}")
        
        response = requests.post(
            url,
            json={"table_name": table_name},
            headers=headers,
            timeout=30
        )
        
        print(f"[DEBUG] RPC response status: {response.status_code}")
        print(f"[DEBUG] RPC response text: {response.text}")
        
        if response.status_code in [200, 201, 204]:
            logger.info(f"Tabela RAG '{table_name}' criada (método alternativo)!")
            return True
        else:
            logger.error(f"Erro ao criar tabela RAG: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao criar tabela RAG (alternativo): {str(e)}")
        return False


def delete_agent_from_supabase(slug):
    """
    Remove agente da tabela 'agentes' do Supabase.
    
    Args:
        slug: Slug do agente a remover
    
    Returns:
        bool: True se sucesso, False se erro
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    
    try:
        url = f"{SUPABASE_URL}/rest/v1/agentes?slug=eq.{slug}"
        
        response = requests.delete(
            url,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            logger.info(f"Agente '{slug}' removido do Supabase!")
            return True
        else:
            logger.error(f"Erro ao remover agente: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao remover agente: {str(e)}")
        return False
