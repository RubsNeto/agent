import os
import sys
import django
import requests
import json
import random
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from organizations.models import Padaria
from payments.models import CaktoSubscription, CaktoPayment

def run_verification():
    import argparse
    
    parser = argparse.ArgumentParser(description='Verificação de Assinatura via Webhook')
    parser.add_argument('--url', default="http://127.0.0.1:8000/payments/cakto/webhook/", help='URL do Webhook')
    parser.add_argument('--token', default=settings.CAKTO_WEBHOOK_TOKEN, help='Token do Webhook (X-Webhook-Token)')
    parser.add_argument('--padaria-slug', type=str, help='Slug da padaria para teste (busca no banco local)')
    parser.add_argument('--padaria-id', type=int, help='ID da padaria para teste (ignora banco local e usa este ID no payload)')
    args = parser.parse_args()

    print(f"=== Iniciando Verificação de Fluxo de Assinatura via Webhook ===\n")
    print(f"   Alvo: {args.url}")

    # 1. Definir Padaria Alvo
    padaria_local = None
    target_padaria_id = None
    target_padaria_slug = "padaria-teste"
    
    if args.padaria_id:
        # Modo Manual (Ideal para produção)
        target_padaria_id = args.padaria_id
        print(f"1. Padaria Alvo (ID Manual): {target_padaria_id}")
        
        # Tenta achar local só para mostrar o nome
        padaria_local = Padaria.objects.filter(id=target_padaria_id).first()
        if padaria_local:
            print(f"   (Encontrada localmente: {padaria_local.name})")
            target_padaria_slug = padaria_local.slug
        else:
            print(f"   (Não encontrada localmente - usando dados mock para payload)")
            
    else:
        # Modo Automático (Baseado no banco local)
        if args.padaria_slug:
            padaria_local = Padaria.objects.filter(slug=args.padaria_slug).first()
        else:
            padaria_local = Padaria.objects.first()
        
        if not padaria_local:
            print("ERRO: Nenhuma padaria encontrada no banco de dados local.")
            return

        target_padaria_id = padaria_local.id
        target_padaria_slug = padaria_local.slug
        print(f"1. Padaria Alvo (Local): {padaria_local.name} (ID: {target_padaria_id})")

    # 2. Configuração Local (Só funciona se tiver padaria local)
    subscription = None
    if padaria_local:
        subscription, created = CaktoSubscription.objects.get_or_create(padaria=padaria_local)
        
        # Resetar status para teste (se já estiver ativa e for localhost)
        if "127.0.0.1" in args.url or "localhost" in args.url:
            original_status = subscription.status
            if subscription.status == 'active':
                print("   (Teste Local: Resetando para 'trial' para teste de ativação)")
                subscription.status = 'trial'
                subscription.save()
            print(f"2. Status da assinatura local antes do teste: {subscription.status}")
        else:
            print(f"2. (Teste Remoto - ignorando estado local)")
            
            # Atualizar ID do pedido localmente para o teste fazer sentido
            order_id = f"test_order_{random.randint(1000, 9999)}"
            subscription.cakto_order_id = order_id 
            subscription.save()
    else:
         order_id = f"test_order_{random.randint(1000, 9999)}"

    # 3. Preparar Payload do Webhook

    payload = {
        "event": "purchase_approved",
        "order_id": order_id,
        "amount": "140.00",
        "status": "approved",
    payload = {
        "event": "purchase_approved",
        "order_id": order_id,
        "amount": "140.00",
        "status": "approved",
        "metadata": {
            "padaria_id": target_padaria_id,
            "padaria_slug": target_padaria_slug
        },
        "payment_method": {
            "type": "credit_card",
            "last4": "4242",
            "brand": "Visa"
        },
        "created_at": datetime.now().isoformat()
    }

    print(f"3. Enviando Webhook simulado via HTTP...")
    print(f"   Order ID: {order_id}")
    
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Token": args.token
    }

    try:
        response = requests.post(
            args.url,
            data=json.dumps(payload),
            headers=headers,
            timeout=10
        )
        
        print(f"   Status Code do Webhook: {response.status_code}")
        print(f"   Resposta Body: {response.text}")
        
        if response.status_code != 200:
            print(f"❌ ERRO: O webhook retornou erro {response.status_code}.")
            return

    except Exception as e:
        print(f"❌ ERRO ao conectar com o servidor: {e}")
        return

    # 4. Verificar atualização no Banco de Dados
    print("\n4. Verificando resultados no banco de dados...")
    
    # Se for teste remoto, não podemos validar o banco diretamente aqui, a menos que seja o mesmo banco
    # Mas como estamos rodando localmente, assumimos banco local.
    # Se o objetivo é testar produção DE VERDADE, o usuário deveria rodar isso no servidor de produção.
    # OU o script apenas envia o webhook e pede para verificar no painel admin.
    
    if "127.0.0.1" in args.url or "localhost" in args.url:
        if padaria_local:
            # Recarregar assinatura
            subscription.refresh_from_db()
            
            # Verificar status
            if subscription.status == 'active':
                print(f"   ✅ SUCESSO: Status da assinatura atualizado para 'active'")
            else:
                print(f"   ❌ FALHA: Status da assinatura é '{subscription.status}' (esperado: 'active')")

            # Verificar pagamento criado
            payment = CaktoPayment.objects.filter(cakto_order_id=order_id).first()
            if payment:
                print(f"   ✅ SUCESSO: Pagamento registrado (ID: {payment.id}, Status: {payment.status})")
            else:
                print(f"   ❌ FALHA: Nenhum pagamento encontrado com order_id '{order_id}'")
        else:
            print("   (Teste sem padaria local: impossível verificar banco de dados localmente)")
    else:
        print("   ⚠️ Teste remoto: Verifique no painel admin da produção se a assinatura foi ativada.")
        if padaria_local:
            print(f"   Verifique a padaria: {padaria_local.name} (Slug: {padaria_local.slug})")
        else:
             print(f"   Verifique a padaria com ID: {target_padaria_id}")

if __name__ == "__main__":
    run_verification()
