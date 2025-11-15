"""
Utilitários para o app agents.
"""
import PyPDF2
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
