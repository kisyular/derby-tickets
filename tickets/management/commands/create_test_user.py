from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tickets.models import UserProfile

class Command(BaseCommand):
    help = 'Create a test user with specified role'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Username')
        parser.add_argument('--email', type=str, default='test@example.com', help='Email')
        parser.add_argument('--password', type=str, default='testpass123', help='Password')
        parser.add_argument('--role', type=str, choices=['user', 'admin'], default='user', help='User role')
        parser.add_argument('--first-name', type=str, default='Test', help='First name')
        parser.add_argument('--last-name', type=str, default='User', help='Last name')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        role = options['role']
        first_name = options['first_name']
        last_name = options['last_name']

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists.')
            )
            return

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Create or update profile
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'role': role}
        )

        if not created:
            profile.role = role
            profile.save()

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created user "{username}" with role "{role}"')
        )
        self.stdout.write(f'Username: {username}')
        self.stdout.write(f'Password: {password}')
        self.stdout.write(f'Email: {email}')
        self.stdout.write(f'Role: {role}')
        
        if role == 'admin':
            self.stdout.write(
                self.style.SUCCESS('This user can be assigned to tickets!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('This user can create tickets but cannot be assigned to them.')
            )
