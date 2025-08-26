"""
Management command to demonstrate the logging system.
Usage: python manage.py demo_logging
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tickets.logging_utils import (
    log_system_event, log_ticket_created, log_ticket_updated, 
    log_auth_event, log_security_event, log_email_sent,
    log_performance_event, performance_monitor
)
import time
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Demonstrate the logging system with sample events'

    def add_arguments(self, parser):
        parser.add_argument(
            '--events', 
            type=int, 
            default=10,
            help='Number of test events to generate'
        )
        parser.add_argument(
            '--performance',
            action='store_true',
            help='Test performance monitoring'
        )

    def handle(self, *args, **options):
        events_count = options['events']
        test_performance = options['performance']

        self.stdout.write(
            self.style.SUCCESS(f'Starting logging system demonstration with {events_count} events...')
        )

        # Demo system startup
        log_system_event('STARTUP', 'Logging system demonstration initiated', 'INFO')

        # Test various event types
        for i in range(events_count):
            self.generate_test_events(i)

        if test_performance:
            self.test_performance_monitoring()

        # Test system shutdown
        log_system_event('SHUTDOWN', 'Logging system test completed', 'INFO')

        self.stdout.write(
            self.style.SUCCESS(
                f'Logging test completed! Check the following log files:'
                f'\n- logs/application.log'
                f'\n- logs/tickets.log'
                f'\n- logs/security.log'
                f'\n- logs/authentication.log'
                f'\n- logs/performance.log'
            )
        )

    def generate_test_events(self, index):
        """Generate various types of test log events."""
        
        # Test ticket events
        ticket_id = 1000 + index
        log_ticket_created(ticket_id, None)
        
        # Test authentication events
        usernames = ['test@derbyfab.com', 'admin@derbyfab.com', 'user@example.com']
        username = random.choice(usernames)
        success = random.choice([True, False, False])  # 1/3 chance of failure
        reason = '' if success else random.choice([
            'Invalid password', 'Account locked', 'Invalid domain'
        ])
        log_auth_event('LOGIN_ATTEMPT', username, None, success, reason)

        # Test security events
        if not success and '@example.com' in username:
            log_security_event(
                'UNAUTHORIZED_DOMAIN', 
                f'Login attempt from unauthorized domain: {username}',
                severity='WARNING'
            )

        # Test email events
        log_email_sent(
            'test@derbyfab.com', 
            f'Test Email #{index}', 
            success=random.choice([True, True, False])  # 2/3 success rate
        )

        # Test error scenarios occasionally
        if index % 5 == 0:
            log_system_event(
                'ERROR_TEST', 
                f'Simulated error event #{index}', 
                'ERROR'
            )

    @performance_monitor('test_slow_operation')
    def slow_operation(self):
        """Simulate a slow operation for performance testing."""
        time.sleep(random.uniform(0.1, 0.5))
        return "Operation completed"

    def test_performance_monitoring(self):
        """Test performance monitoring functionality."""
        self.stdout.write('Testing performance monitoring...')
        
        for i in range(5):
            result = self.slow_operation()
            log_performance_event(
                f'manual_test_{i}',
                random.uniform(0.05, 0.2),
                {'test_index': i, 'result': result}
            )

        self.stdout.write(self.style.SUCCESS('Performance monitoring test completed!'))
