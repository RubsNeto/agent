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


def create_rag_table(slug, agent_slug=None):
    """
    Cria uma tabela RAG dinâmica no Supabase para o agente.
    Nome da tabela: rag_{slug_sanitizado}
    
    Estrutura:
    - id (int8, primary key)
    - content (text)
    - metadata (jsonb)
    - embedding (vector)
    
    Args:
        slug: Slug da padaria (usado para nome da tabela RAG)
        agent_slug: Slug do agente (usado para atualizar na tabela agentes)
    
    Returns:
        str: Nome da tabela criada se sucesso, None se erro
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase não configurado. Pulando criação de tabela RAG.")
        return None
    
    # Sanitizar slug para nome de tabela válido
    table_name = f"rag_{slugify(slug).replace('-', '_')}"
    
    # Usar agent_slug se fornecido, senão usar o slug normal
    update_slug = agent_slug or slug
    
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
            # Atualizar a referência na tabela agentes usando agent_slug
            update_agent_rag_table(update_slug, table_name)
            return table_name
        else:
            # Se RPC não existir, tentar via SQL direto (menos seguro mas funcional)
            logger.warning(f"RPC exec_sql não disponível, tentando método alternativo...")
            result = create_rag_table_alternative(table_name)
            if result:
                # Atualizar a referência na tabela agentes
                update_agent_rag_table(update_slug, table_name)
                return table_name
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao criar tabela RAG: {str(e)}")
        return None


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


def update_agent_rag_table(slug, rag_table_name):
    """
    Atualiza a coluna 'rag_table' na tabela 'agentes' do Supabase.
    Busca o ID (oid) da tabela e salva junto com o nome.
    
    Args:
        slug: Slug do agente
        rag_table_name: Nome da tabela RAG criada (ex: rag_padaria_maria)
    
    Returns:
        bool: True se sucesso, False se erro
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase não configurado. Pulando atualização do rag_table.")
        return False
    
    try:
        # Buscar o ID (oid) da tabela criada
        table_id = get_table_oid(rag_table_name)
        
        url = f"{SUPABASE_URL}/rest/v1/agentes?slug=eq.{slug}"
        
        # Salvar tanto o nome quanto o ID da tabela
        data = {
            "rag_table": rag_table_name,
            "rag_id": table_id  # ID numérico da tabela
        }
        
        headers = get_headers()
        headers["Prefer"] = "return=representation"
        
        response = requests.patch(
            url,
            json=data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            logger.info(f"rag_table '{rag_table_name}' (ID: {table_id}) atualizado para agente '{slug}'!")
            return True
        else:
            logger.error(f"Erro ao atualizar rag_table: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão ao atualizar rag_table: {str(e)}")
        return False


def get_table_oid(table_name):
    """
    Busca o OID (ID numérico) de uma tabela no PostgreSQL.
    
    Args:
        table_name: Nome da tabela
    
    Returns:
        int: OID da tabela ou None se não encontrada
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    
    try:
        # Usar RPC para executar SQL e buscar o oid
        url = f"{SUPABASE_URL}/rest/v1/rpc/get_table_oid"
        
        headers = get_headers()
        headers["Prefer"] = "return=representation"
        
        response = requests.post(
            url,
            json={"p_table_name": table_name},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result:
                logger.info(f"OID da tabela '{table_name}': {result}")
                return result
        
        # Fallback: tentar via consulta direta na tabela pg_class
        # (requer que a tabela pg_class seja acessível via REST)
        logger.warning(f"RPC get_table_oid não disponível. Usando nome da tabela como ID.")
        return table_name  # Fallback para o nome se não conseguir o ID
            
    except Exception as e:
        logger.error(f"Erro ao buscar OID da tabela: {str(e)}")
        return table_name  # Fallback para o nome


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


def update_agent_evolution_hash(slug, evolution_hash):
    """
    Atualiza a coluna 'evo' na tabela 'agentes' do Supabase.
    
    Args:
        slug: Slug do agente (correspondente ao slug no Supabase)
        evolution_hash: Hash/token da instância Evolution API
    
    Returns:
        bool: True se sucesso, False se erro
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase não configurado. Pulando atualização do hash Evolution.")
        return False
    
    try:
        url = f"{SUPABASE_URL}/rest/v1/agentes?slug=eq.{slug}"
        
        data = {"evo": evolution_hash}
        
        headers = get_headers()
        headers["Prefer"] = "return=representation"
        
        response = requests.patch(
            url,
            json=data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            logger.info(f"Hash Evolution atualizado para agente '{slug}'!")
            return True
        else:
            logger.error(f"Erro ao atualizar hash Evolution: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão ao atualizar hash Evolution: {str(e)}")
        return False
