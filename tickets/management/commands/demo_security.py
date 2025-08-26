"""
Management command to demonstrate security features.
Usage: python manage.py demo_security
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.core.cache import cache
from tickets.security import SecurityManager, check_password_strength
from tickets.logging_utils import log_security_event, log_auth_event
import time

User = get_user_model()


class Command(BaseCommand):
    help = 'Demonstrate security features and monitoring'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain-tests',
            action='store_true',
            help='Test domain validation'
        )
        parser.add_argument(
            '--lockout-tests',
            action='store_true',
            help='Test account lockout functionality'
        )
        parser.add_argument(
            '--password-tests',
            action='store_true',
            help='Test password strength validation'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all security tests'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting security system tests...')
        )

        if options['all'] or options['domain_tests']:
            self.test_domain_validation()

        if options['all'] or options['lockout_tests']:
            self.test_lockout_functionality()

        if options['all'] or options['password_tests']:
            self.test_password_strength()

        # Always test suspicious activity detection
        self.test_suspicious_activity()

        self.stdout.write(
            self.style.SUCCESS(
                'Security tests completed! Check the following log files:'
                '\n- logs/security.log'
                '\n- logs/authentication.log'
            )
        )

    def test_domain_validation(self):
        """Test domain validation functionality."""
        self.stdout.write('Testing domain validation...')
        
        test_emails = [
            ('user@derbyfab.com', True),
            ('admin@derbyfab.com', True),
            ('test@external.com', False),
            ('user@gmail.com', False),
            ('valid.user@derbyfab.com', True),
        ]
        
        for email, expected in test_emails:
            result = SecurityManager.is_domain_allowed(email)
            status = "PASS" if result == expected else "FAIL"
            self.stdout.write(f'  {status} - {email}: {"Allowed" if result else "Blocked"}')
            
            # Log domain check for testing
            log_security_event(
                'DOMAIN_TEST',
                f'Domain validation test for {email}: {"allowed" if result else "blocked"}',
                severity='INFO'
            )

    def test_lockout_functionality(self):
        """Test account lockout functionality."""
        self.stdout.write('Testing lockout functionality...')
        
        # Clear any existing lockout data
        test_user = 'test@derbyfab.com'
        SecurityManager.clear_attempts(test_user)
        
        factory = RequestFactory()
        request = factory.post('/login', {'username': test_user, 'password': 'wrong'})
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        
        # Simulate failed attempts
        for i in range(6):  # One more than the limit
            result = SecurityManager.record_failed_attempt(test_user, request)
            self.stdout.write(
                f'  Attempt {i+1}: {result["attempts"]} attempts, '
                f'Locked: {"Yes" if result["locked_out"] else "No"}'
            )
            
            if result['locked_out']:
                self.stdout.write('  Account locked!')
                break
        
        # Test lockout check
        is_locked = SecurityManager.is_locked_out(test_user)
        self.stdout.write(f'  Final lockout status: {"LOCKED" if is_locked else "UNLOCKED"}')

        # Clear for next test
        SecurityManager.clear_attempts(test_user)

    def test_password_strength(self):
        """Test password strength validation."""
        self.stdout.write('Testing password strength validation...')
        
        test_passwords = [
            '123',
            'password',
            'Password1',
            'StrongP@ss1',
            'VeryStrongP@ssw0rd!',
        ]
        
        for password in test_passwords:
            result = check_password_strength(password)
            self.stdout.write(
                f'  Password: "{password}" -> '
                f'Score: {result["score"]}/5, '
                f'Strength: {result["strength"]}'
            )
            
            if result['recommendations']:
                self.stdout.write(f'    Recommendations: {", ".join(result["recommendations"])}')

    def test_suspicious_activity(self):
        """Test suspicious activity detection."""
        self.stdout.write('Testing suspicious activity detection...')
        
        factory = RequestFactory()
        
        # Test bot detection
        bot_user_agents = [
            'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'python-requests/2.28.1',
            'curl/7.68.0',
            'Wget/1.20.3',
        ]
        
        for user_agent in bot_user_agents:
            request = factory.get('/')
            request.META['HTTP_USER_AGENT'] = user_agent
            request.META['REMOTE_ADDR'] = '192.168.1.100'
            
            suspicious = SecurityManager.detect_suspicious_patterns(request)
            if suspicious:
                self.stdout.write(f'  Suspicious: {user_agent[:50]}... -> {suspicious[0]}')
                log_security_event(
                    'SUSPICIOUS_TEST',
                    f'Test detected suspicious pattern: {suspicious[0]}',
                    request,
                    'WARNING'
                )
        
        # Test rate limiting simulation
        self.stdout.write('  Testing rate limiting...')
        normal_request = factory.get('/')
        normal_request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        normal_request.META['REMOTE_ADDR'] = '192.168.1.101'
        
        # Simulate rapid requests
        for i in range(35):  # Exceed the 30 requests/minute threshold
            suspicious = SecurityManager.detect_suspicious_patterns(normal_request)
            if suspicious and 'High request rate' in str(suspicious):
                self.stdout.write(f'  Rate limit triggered at request {i+1}')
                break

    def create_test_user(self):
        """Create a test user for security testing."""
        test_username = 'security_test@derbyfab.com'
        
        # Remove existing test user if exists
        User.objects.filter(username=test_username).delete()
        
        user = User.objects.create_user(
            username=test_username,
            email=test_username,
            password='TestPassword123!',
            first_name='Security',
            last_name='Test'
        )
        
        self.stdout.write(f'Created test user: {test_username}')
        return user
