"""
Management command to create and manage API tokens.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tickets.models import APIToken
from tickets.api_auth import generate_api_token
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Create and manage API tokens for external integrations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create',
            action='store_true',
            help='Create a new API token'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Name/description for the token'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Username of the user who owns this token'
        )
        parser.add_argument(
            '--expires-days',
            type=int,
            help='Number of days until token expires (optional)'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all API tokens'
        )
        parser.add_argument(
            '--deactivate',
            type=str,
            help='Deactivate a token by ID or token value'
        )
        parser.add_argument(
            '--activate',
            type=str,
            help='Activate a token by ID or token value'
        )

    def handle(self, *args, **options):
        if options['create']:
            self.create_token(options)
        elif options['list']:
            self.list_tokens()
        elif options['deactivate']:
            self.deactivate_token(options['deactivate'])
        elif options['activate']:
            self.activate_token(options['activate'])
        else:
            self.stdout.write(
                self.style.WARNING('Use --create, --list, --deactivate, or --activate')
            )

    def create_token(self, options):
        """Create a new API token."""
        name = options.get('name')
        username = options.get('user')
        expires_days = options.get('expires_days')

        if not name:
            name = input("Enter a name/description for this token: ")

        if not username:
            username = input("Enter the username who will own this token: ")

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User "{username}" does not exist')
            )
            return

        # Generate token
        token_value = generate_api_token()
        
        # Set expiration if specified
        expires_at = None
        if expires_days:
            expires_at = timezone.now() + timedelta(days=expires_days)

        # Create token
        api_token = APIToken.objects.create(
            token=token_value,
            name=name,
            created_by=user,
            expires_at=expires_at
        )

        self.stdout.write(
            self.style.SUCCESS(f'API token created successfully!')
        )
        self.stdout.write(f'Token ID: {api_token.id}')
        self.stdout.write(f'Name: {api_token.name}')
        self.stdout.write(f'Created by: {user.username}')
        self.stdout.write(f'Token: {token_value}')
        if expires_at:
            self.stdout.write(f'Expires: {expires_at}')
        
        self.stdout.write(
            self.style.WARNING('\nIMPORTANT: Save this token securely. It will not be shown again!')
        )

    def list_tokens(self):
        """List all API tokens."""
        tokens = APIToken.objects.all().order_by('-created_at')
        
        if not tokens.exists():
            self.stdout.write(self.style.WARNING('No API tokens found'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {tokens.count()} API tokens:'))
        self.stdout.write('=' * 80)
        
        for token in tokens:
            status = "Active" if token.is_active else "Inactive"
            if token.expires_at and token.expires_at < timezone.now():
                status = "Expired"

            self.stdout.write(f'ID: {token.id}')
            self.stdout.write(f'Name: {token.name}')
            self.stdout.write(f'Created by: {token.created_by.username}')
            self.stdout.write(f'Created: {token.created_at}')
            self.stdout.write(f'Last used: {token.last_used or "Never"}')
            self.stdout.write(f'Status: {status}')
            self.stdout.write(f'Token: {token.token[:16]}...')
            if token.expires_at:
                self.stdout.write(f'Expires: {token.expires_at}')
            self.stdout.write('-' * 40)

    def deactivate_token(self, identifier):
        """Deactivate a token."""
        token = self.get_token_by_identifier(identifier)
        if token:
            token.is_active = False
            token.save()
            self.stdout.write(
                self.style.SUCCESS(f'Token "{token.name}" has been deactivated')
            )

    def activate_token(self, identifier):
        """Activate a token."""
        token = self.get_token_by_identifier(identifier)
        if token:
            token.is_active = True
            token.save()
            self.stdout.write(
                self.style.SUCCESS(f'Token "{token.name}" has been activated')
            )

    def get_token_by_identifier(self, identifier):
        """Get token by ID or token value."""
        try:
            # Try to get by ID first
            if identifier.isdigit():
                return APIToken.objects.get(id=int(identifier))
            else:
                # Try to get by token value
                return APIToken.objects.get(token=identifier)
        except APIToken.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Token with identifier "{identifier}" not found')
            )
            return None
