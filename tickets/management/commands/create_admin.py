from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tickets.models import UserProfile
import os

class Command(BaseCommand):
    help = 'Create initial admin user for the ticket system'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default=os.environ.get('DJANGO_ADMIN_USERNAME'), help='Admin username')
        parser.add_argument('--email', type=str, default=os.environ.get('DJANGO_ADMIN_EMAIL'), help='Admin email')
        parser.add_argument('--password', type=str, default=os.environ.get('DJANGO_ADMIN_PASSWORD'), help='Admin password')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists.')
            )
            return

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name=os.environ.get('DJANGO_ADMIN_FIRST_NAME', 'System'),
            last_name=os.environ.get('DJANGO_ADMIN_LAST_NAME', 'Administrator')
        )
        
        # Ensure the user profile has admin role
        if hasattr(user, 'profile'):
            user.profile.role = 'admin'
            user.profile.save()
        else:
            UserProfile.objects.create(user=user, role='admin')

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created admin user "{username}" with admin role')
        )
        self.stdout.write(f'Username: {username}')
        self.stdout.write(f'Password: {password}')
        self.stdout.write(f'Email: {email}')
        self.stdout.write(f'Role: Admin')
        self.stdout.write(
            self.style.WARNING('Please change the default password after first login!')
        )
