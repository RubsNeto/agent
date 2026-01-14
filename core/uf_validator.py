"""
Serviço de validação de UF para CNPJ e CEP.
Utiliza BrasilAPI para CNPJ e ViaCEP para CEP.
"""
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any


def clean_cnpj(cnpj: str) -> str:
    """Remove caracteres especiais do CNPJ, mantendo apenas números."""
    if not cnpj:
        return ""
    return re.sub(r'\D', '', cnpj)


def clean_cep(cep: str) -> str:
    """Remove caracteres especiais do CEP, mantendo apenas números."""
    if not cep:
        return ""
    return re.sub(r'\D', '', cep)


def validate_cnpj_format(cnpj: str) -> bool:
    """Valida se o CNPJ tem o formato correto (14 dígitos)."""
    clean = clean_cnpj(cnpj)
    return len(clean) == 14 and clean.isdigit()


def validate_cep_format(cep: str) -> bool:
    """Valida se o CEP tem o formato correto (8 dígitos)."""
    clean = clean_cep(cep)
    return len(clean) == 8 and clean.isdigit()


def get_uf_from_cnpj(cnpj: str) -> Dict[str, Any]:
    """
    Consulta a BrasilAPI para obter a UF do CNPJ.
    
    Retorna:
        {"uf": "SP", "error": None} em caso de sucesso
        {"uf": None, "error": "mensagem"} em caso de erro
    """
    clean = clean_cnpj(cnpj)
    
    if not validate_cnpj_format(cnpj):
        return {"uf": None, "error": "CNPJ inválido. Deve conter 14 dígitos."}
    
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{clean}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            uf = data.get("uf")
            if uf:
                return {"uf": uf.upper(), "error": None, "data": data}
            else:
                return {"uf": None, "error": "UF não encontrada no retorno da API."}
        elif response.status_code == 404:
            return {"uf": None, "error": "CNPJ não encontrado na base da Receita Federal."}
        else:
            return {"uf": None, "error": f"Erro na consulta do CNPJ: HTTP {response.status_code}"}
            
    except requests.exceptions.Timeout:
        return {"uf": None, "error": "Timeout ao consultar CNPJ. Tente novamente."}
    except requests.exceptions.ConnectionError:
        return {"uf": None, "error": "Erro de conexão ao consultar CNPJ."}
    except Exception as e:
        return {"uf": None, "error": f"Erro inesperado: {str(e)}"}


def get_uf_from_cep(cep: str) -> Dict[str, Any]:
    """
    Consulta o ViaCEP para obter a UF do CEP.
    
    Retorna:
        {"uf": "SP", "error": None} em caso de sucesso
        {"uf": None, "error": "mensagem"} em caso de erro
    """
    clean = clean_cep(cep)
    
    if not validate_cep_format(cep):
        return {"uf": None, "error": "CEP inválido. Deve conter 8 dígitos."}
    
    try:
        url = f"https://viacep.com.br/ws/{clean}/json/"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # ViaCEP retorna {"erro": true} para CEP não encontrado
            if data.get("erro"):
                return {"uf": None, "error": "CEP não encontrado."}
            
            uf = data.get("uf")
            if uf:
                return {"uf": uf.upper(), "error": None, "data": data}
            else:
                return {"uf": None, "error": "UF não encontrada no retorno da API."}
        else:
            return {"uf": None, "error": f"Erro na consulta do CEP: HTTP {response.status_code}"}
            
    except requests.exceptions.Timeout:
        return {"uf": None, "error": "Timeout ao consultar CEP. Tente novamente."}
    except requests.exceptions.ConnectionError:
        return {"uf": None, "error": "Erro de conexão ao consultar CEP."}
    except Exception as e:
        return {"uf": None, "error": f"Erro inesperado: {str(e)}"}


def validate_same_uf(cnpj: str, cep: str) -> Dict[str, Any]:
    """
    Valida se o CNPJ e o CEP pertencem à mesma Unidade Federativa.
    
    Realiza as consultas em paralelo para maior performance.
    
    Args:
        cnpj: CNPJ da empresa (com ou sem formatação)
        cep: CEP do administrador (com ou sem formatação)
    
    Retorna:
        {
            "valid": True/False,  # Se são da mesma UF
            "cnpj_uf": "SP",      # UF do CNPJ
            "cep_uf": "SP",       # UF do CEP
            "error": None         # Mensagem de erro se houver
        }
    """
    # Validação inicial de formato
    if not validate_cnpj_format(cnpj):
        return {
            "valid": False,
            "cnpj_uf": None,
            "cep_uf": None,
            "error": "CNPJ inválido. Deve conter 14 dígitos."
        }
    
    if not validate_cep_format(cep):
        return {
            "valid": False,
            "cnpj_uf": None,
            "cep_uf": None,
            "error": "CEP inválido. Deve conter 8 dígitos."
        }
    
    # Executar consultas em paralelo
    cnpj_result = None
    cep_result = None
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(get_uf_from_cnpj, cnpj): "cnpj",
            executor.submit(get_uf_from_cep, cep): "cep"
        }
        
        for future in as_completed(futures):
            api_type = futures[future]
            try:
                result = future.result()
                if api_type == "cnpj":
                    cnpj_result = result
                else:
                    cep_result = result
            except Exception as e:
                if api_type == "cnpj":
                    cnpj_result = {"uf": None, "error": str(e)}
                else:
                    cep_result = {"uf": None, "error": str(e)}
    
    # Verificar erros nas consultas
    if cnpj_result.get("error"):
        return {
            "valid": False,
            "cnpj_uf": None,
            "cep_uf": cep_result.get("uf"),
            "error": f"Erro no CNPJ: {cnpj_result['error']}"
        }
    
    if cep_result.get("error"):
        return {
            "valid": False,
            "cnpj_uf": cnpj_result.get("uf"),
            "cep_uf": None,
            "error": f"Erro no CEP: {cep_result['error']}"
        }
    
    # Comparar UFs
    cnpj_uf = cnpj_result.get("uf")
    cep_uf = cep_result.get("uf")
    
    return {
        "valid": cnpj_uf == cep_uf,
        "cnpj_uf": cnpj_uf,
        "cep_uf": cep_uf,
        "error": None
    }
