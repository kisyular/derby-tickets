"""
Management command to test and maintain user sessions.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tickets.audit_security import audit_security_manager
from tickets.audit_models import UserSession


class Command(BaseCommand):
    help = 'Test and maintain user sessions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup', 
            action='store_true',
            help='Clean up inactive sessions'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Hours of inactivity after which to clean up sessions (default: 24)'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all active sessions'
        )

    def handle(self, *args, **options):
        if options['cleanup']:
            cleaned_count = audit_security_manager.cleanup_inactive_sessions(
                hours=options['hours']
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Cleaned up {cleaned_count} inactive sessions older than {options["hours"]} hours'
                )
            )
        
        if options['list']:
            active_sessions = UserSession.objects.filter(is_active=True).order_by('-last_activity')
            
            self.stdout.write(self.style.SUCCESS(f'\nActive Sessions: {active_sessions.count()}'))
            self.stdout.write('=' * 80)
            
            for session in active_sessions:
                self.stdout.write(f'User: {session.user.username}')
                self.stdout.write(f'  IP: {session.ip_address}')
                self.stdout.write(f'  Created: {session.created_at}')
                self.stdout.write(f'  Last Activity: {session.last_activity}')
                self.stdout.write(f'  Session Key: {session.session_key[:10]}...')
                self.stdout.write('-' * 40)
        
        if not options['cleanup'] and not options['list']:
            self.stdout.write(
                self.style.WARNING('Use --cleanup to clean inactive sessions or --list to show active sessions')
            )
