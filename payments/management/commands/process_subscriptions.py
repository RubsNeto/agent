"""
Management command para processar assinaturas Cakto diariamente.

Funções:
- Verifica trials expirando (3 dias antes do fim)
- Desativa padarias com trial expirado sem pagamento
- Processa renovações de assinaturas ativas

Uso: python manage.py process_subscriptions
Recomendado: Executar via cron/scheduler 1x ao dia
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from payments.models import CaktoSubscription
from organizations.models import Padaria


class Command(BaseCommand):
    help = 'Processa assinaturas Cakto - verifica trials, ativa/desativa padarias'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem fazer alterações no banco de dados',
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        today = timezone.now().date()
        
        self.stdout.write(f"[{timezone.now()}] Iniciando processamento de assinaturas...")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY-RUN: Nenhuma alteração será feita"))
        
        # 1. Verificar trials expirando em 3 dias (para notificação)
        warning_date = today + timedelta(days=3)
        expiring_trials = CaktoSubscription.objects.filter(
            status='trial',
            trial_end_date=warning_date,
            card_registered=False
        )
        
        for sub in expiring_trials:
            self.stdout.write(
                f"  ⚠️  Trial expirando em 3 dias: {sub.padaria.name} (fim: {sub.trial_end_date})"
            )
            # TODO: Enviar email/notificação para o responsável
        
        # 2. Desativar padarias com trial expirado sem cartão cadastrado
        expired_trials = CaktoSubscription.objects.filter(
            status='trial',
            trial_end_date__lt=today,
        )
        
        expired_count = 0
        for sub in expired_trials:
            self.stdout.write(
                f"  ❌ Trial expirado: {sub.padaria.name} (fim: {sub.trial_end_date})"
            )
            
            if not dry_run:
                # Mudar status para inativo
                sub.status = 'inactive'
                sub.save(update_fields=['status', 'updated_at'])
                
                # Desativar padaria
                sub.padaria.is_active = False
                sub.padaria.save(update_fields=['is_active'])
                
            expired_count += 1
        
        # 3. Verificar assinaturas ativas com pagamento vencido
        overdue_subscriptions = CaktoSubscription.objects.filter(
            status='active',
            next_billing_date__lt=today
        )
        
        overdue_count = 0
        for sub in overdue_subscriptions:
            days_overdue = (today - sub.next_billing_date).days
            self.stdout.write(
                f"  ⚠️  Pagamento atrasado há {days_overdue} dias: {sub.padaria.name}"
            )
            
            # Após 15 dias de atraso, desativar
            if days_overdue > 15:
                self.stdout.write(
                    f"  ❌ Desativando por inadimplência: {sub.padaria.name}"
                )
                
                if not dry_run:
                    sub.status = 'inactive'
                    sub.save(update_fields=['status', 'updated_at'])
                    
                    sub.padaria.is_active = False
                    sub.padaria.save(update_fields=['is_active'])
                    
                overdue_count += 1
        
        # 4. Resumo
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"Trials expirando em 3 dias: {expiring_trials.count()}")
        self.stdout.write(f"Trials expirados processados: {expired_count}")
        self.stdout.write(f"Assinaturas inadimplentes desativadas: {overdue_count}")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nMODO DRY-RUN: Nenhuma alteração foi feita"))
        else:
            self.stdout.write(self.style.SUCCESS("\nProcessamento concluído!"))
