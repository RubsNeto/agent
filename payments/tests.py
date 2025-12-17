"""
Testes para o app de pagamentos.
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from organizations.models import Padaria, ApiKey
from payments.models import StripeAccount, PaymentSession


class StripeAccountModelTest(TestCase):
    """Testes para o modelo StripeAccount."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.padaria = Padaria.objects.create(name="Test Padaria", owner=self.user)
    
    def test_create_stripe_account(self):
        """Testa criação de conta Stripe."""
        account = StripeAccount.objects.create(
            padaria=self.padaria,
            stripe_account_id="acct_test123"
        )
        self.assertEqual(account.padaria, self.padaria)
        self.assertEqual(account.stripe_account_id, "acct_test123")
        self.assertFalse(account.is_onboarding_complete)
        self.assertFalse(account.charges_enabled)
    
    def test_is_fully_enabled_property(self):
        """Testa propriedade is_fully_enabled."""
        account = StripeAccount.objects.create(
            padaria=self.padaria,
            stripe_account_id="acct_test123",
            charges_enabled=True,
            payouts_enabled=True,
            details_submitted=True
        )
        self.assertTrue(account.is_fully_enabled)
        
        account.charges_enabled = False
        self.assertFalse(account.is_fully_enabled)


class PaymentSessionModelTest(TestCase):
    """Testes para o modelo PaymentSession."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.padaria = Padaria.objects.create(name="Test Padaria", owner=self.user)
    
    def test_create_payment_session(self):
        """Testa criação de sessão de pagamento."""
        session = PaymentSession.objects.create(
            padaria=self.padaria,
            stripe_session_id="cs_test123",
            checkout_url="https://checkout.stripe.com/test",
            amount=Decimal("50.00"),
            description="Test order",
            customer_phone="5511999999999"
        )
        self.assertEqual(session.padaria, self.padaria)
        self.assertEqual(session.status, "pending")
        self.assertEqual(session.amount, Decimal("50.00"))


class PaymentAPITest(TestCase):
    """Testes para API de pagamentos."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.padaria = Padaria.objects.create(name="Test Padaria", owner=self.user)
        self.api_key = ApiKey.objects.create(padaria=self.padaria)
    
    def test_check_payments_enabled_no_account(self):
        """Testa endpoint check-enabled quando não tem conta Stripe."""
        response = self.client.get(
            "/api/payments/check-enabled/",
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["payments_enabled"])
    
    def test_check_payments_enabled_with_account(self):
        """Testa endpoint check-enabled com conta Stripe habilitada."""
        StripeAccount.objects.create(
            padaria=self.padaria,
            stripe_account_id="acct_test123",
            charges_enabled=True,
            payouts_enabled=True,
            details_submitted=True
        )
        
        response = self.client.get(
            "/api/payments/check-enabled/",
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["payments_enabled"])
    
    def test_create_checkout_no_stripe_account(self):
        """Testa criação de checkout sem conta Stripe."""
        response = self.client.post(
            "/api/payments/create-checkout/",
            data='{"amount": 50.00, "description": "Test"}',
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "stripe_not_configured")
    
    def test_create_checkout_missing_amount(self):
        """Testa criação de checkout sem amount."""
        StripeAccount.objects.create(
            padaria=self.padaria,
            stripe_account_id="acct_test123",
            charges_enabled=True
        )
        
        response = self.client.post(
            "/api/payments/create-checkout/",
            data='{"description": "Test"}',
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "missing_amount")
    
    def test_payment_status_not_found(self):
        """Testa verificação de status de sessão inexistente."""
        response = self.client.get(
            "/api/payments/status/cs_notexists/",
            HTTP_X_API_KEY=self.api_key.key
        )
        self.assertEqual(response.status_code, 404)


class StripeWebhookTest(TestCase):
    """Testes para webhooks do Stripe."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.padaria = Padaria.objects.create(name="Test Padaria", owner=self.user)
    
    def test_account_updated_webhook(self):
        """Testa webhook de atualização de conta."""
        stripe_account = StripeAccount.objects.create(
            padaria=self.padaria,
            stripe_account_id="acct_test123",
            charges_enabled=False
        )
        
        # Simula webhook
        payload = {
            "type": "account.updated",
            "data": {
                "object": {
                    "id": "acct_test123",
                    "charges_enabled": True,
                    "payouts_enabled": True,
                    "details_submitted": True
                }
            }
        }
        
        response = self.client.post(
            "/payments/stripe/webhook/",
            data=payload,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        # Verifica se conta foi atualizada
        stripe_account.refresh_from_db()
        self.assertTrue(stripe_account.charges_enabled)
        self.assertTrue(stripe_account.payouts_enabled)
    
    def test_checkout_completed_webhook(self):
        """Testa webhook de checkout completado."""
        session = PaymentSession.objects.create(
            padaria=self.padaria,
            stripe_session_id="cs_test123",
            checkout_url="https://checkout.stripe.com/test",
            amount=Decimal("50.00")
        )
        
        payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test123"
                }
            }
        }
        
        response = self.client.post(
            "/payments/stripe/webhook/",
            data=payload,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        # Verifica se sessão foi atualizada
        session.refresh_from_db()
        self.assertEqual(session.status, "completed")
        self.assertIsNotNone(session.completed_at)
