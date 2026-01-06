"""
Utilitários para o app agents.
"""
import PyPDF2
import os
import json
import requests
from io import BytesIO


def extract_text_from_pdf(pdf_file):
    """
    Extrai texto de um arquivo PDF.
    
    Args:
        pdf_file: Arquivo PDF (FileField ou UploadedFile)
    
    Returns:
        str: Texto extraído do PDF
    """
    try:
        # Se for um FileField, pegar o arquivo
        if hasattr(pdf_file, 'file'):
            file_obj = pdf_file.file
        else:
            file_obj = pdf_file
            
        # Reset file pointer
        file_obj.seek(0)
        
        # Criar reader do PDF
        pdf_reader = PyPDF2.PdfReader(file_obj)
        
        # Extrair texto de todas as páginas
        text_parts = []
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text.strip():
                text_parts.append(text.strip())
        
        # Juntar todo o texto
        full_text = "\n\n".join(text_parts)
        
        return full_text
        
    except Exception as e:
        raise ValueError(f"Erro ao extrair texto do PDF: {str(e)}")


def extract_products_from_text(text, padaria):
    """
    Extrai produtos do texto do PDF usando a API do Gemini.
    
    Args:
        text: Texto extraído do PDF
        padaria: Instância do modelo Padaria
    
    Returns:
        list: Lista de Produtos criados/atualizados
    """
    from organizations.models import Produto
    
    # Obter API key
    api_key = os.environ.get('GEMINI_API_KEY', '')
    
    if not api_key:
        print("[ERROR] GEMINI_API_KEY não configurada no .env")
        return []
    
    print(f"[DEBUG] Usando Gemini API...")
    print(f"[DEBUG] Texto do PDF: {len(text)} caracteres")
    
    try:
        # Usar a API REST do Gemini diretamente (mais simples)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        prompt = f"""Analise o texto abaixo que foi extraído de um catálogo/cardápio de padaria.
Extraia TODOS os produtos mencionados.

Para cada produto, retorne:
- nome: nome do produto
- preco: preço em reais como número (ex: 5.50), ou null se não tiver
- descricao: descrição breve, ou string vazia
- categoria: Pães, Doces, Salgados, Bebidas, Bolos, Confeitaria, Lanches, ou vazio

RETORNE APENAS JSON no formato:
{{"produtos": [{{"nome": "X", "preco": 1.00, "descricao": "", "categoria": "Pães"}}]}}

Texto:
{text[:6000]}"""

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 4096
            }
        }
        
        print(f"[DEBUG] Enviando request para Gemini...")
        
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        print(f"[DEBUG] Gemini status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[ERROR] Gemini error: {response.text[:500]}")
            return []
        
        # Parse response
        result = response.json()
        
        # Extrair texto da resposta
        try:
            response_text = result['candidates'][0]['content']['parts'][0]['text']
            print(f"[DEBUG] Gemini response: {response_text[:300]}...")
        except (KeyError, IndexError) as e:
            print(f"[ERROR] Estrutura de resposta inválida: {e}")
            print(f"[DEBUG] Result: {json.dumps(result)[:500]}")
            return []
        
        # Limpar JSON (remover markdown se presente)
        response_text = response_text.strip()
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
        response_text = response_text.strip()
        
        # Parse JSON
        try:
            data = json.loads(response_text)
            products_data = data.get('produtos', [])
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parse error: {e}")
            print(f"[DEBUG] Text: {response_text[:300]}")
            return []
        
        print(f"[DEBUG] Gemini encontrou {len(products_data)} produtos")
        
        # Criar produtos no banco
        created_products = []
        for p in products_data:
            try:
                nome = str(p.get('nome', '')).strip()
                if not nome or len(nome) < 2:
                    continue
                
                # Parse preço
                preco = p.get('preco')
                if preco is not None:
                    try:
                        preco = float(preco)
                        if preco <= 0 or preco > 10000:
                            preco = None
                    except:
                        preco = None
                
                descricao = str(p.get('descricao', '') or '')
                categoria = str(p.get('categoria', '') or '')
                
                # Verificar se já existe
                existing = Produto.objects.filter(
                    padaria=padaria,
                    nome__iexact=nome
                ).first()
                
                if existing:
                    if preco is not None:
                        existing.preco = preco
                    if descricao:
                        existing.descricao = descricao
                    if categoria:
                        existing.categoria = categoria
                    existing.save()
                    created_products.append(existing)
                    print(f"[DEBUG] Atualizado: {nome}")
                else:
                    produto = Produto.objects.create(
                        padaria=padaria,
                        nome=nome,
                        preco=preco,
                        descricao=descricao,
                        categoria=categoria,
                        ativo=True
                    )
                    created_products.append(produto)
                    print(f"[DEBUG] Criado: {nome}")
                    
            except Exception as e:
                print(f"[WARNING] Erro ao criar '{p.get('nome', '?')}': {e}")
                continue
        
        return created_products
        
    except requests.exceptions.Timeout:
        print("[ERROR] Timeout ao chamar Gemini")
        return []
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request error: {e}")
        return []
    except Exception as e:
        import traceback
        print(f"[ERROR] Erro inesperado: {e}")
        print(traceback.format_exc())
        return []
