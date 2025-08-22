"""
Management command to reset admin password for development.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = 'Reset admin password for development purposes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Admin username (default: admin)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='admin123',
            help='New password (default: admin123)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@derbyfab.com',
            help='Admin email (default: admin@derbyfab.com)'
        )
        parser.add_argument(
            '--create',
            action='store_true',
            help='Create admin user if not exists'
        )
    
    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        create_if_missing = options['create']
        
        self.stdout.write(
            self.style.SUCCESS("🔐 Admin Password Reset Tool")
        )
        self.stdout.write("=" * 40)
        
        try:
            # Try to find existing admin user
            try:
                admin = User.objects.get(username=username)
                self.stdout.write(f"✓ Found existing user: {admin.username}")
                
                # Reset password
                admin.set_password(password)
                admin.email = email
                admin.is_superuser = True
                admin.is_staff = True
                admin.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f"\n✅ Password reset successful!")
                )
                
            except User.DoesNotExist:
                if create_if_missing:
                    # Create new admin user
                    admin = User.objects.create_superuser(
                        username=username,
                        email=email,
                        password=password
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f"\n✅ New admin user created!")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"❌ User '{username}' not found!")
                    )
                    self.stdout.write("Use --create to create a new admin user")
                    return
            
            # Display login info
            self.stdout.write(f"   Username: {username}")
            self.stdout.write(f"   Password: {password}")
            self.stdout.write(f"   Email: {email}")
            self.stdout.write("")
            self.stdout.write("🚀 Login URLs:")
            self.stdout.write("   Admin: http://127.0.0.1:8000/admin/")
            self.stdout.write("   App: http://127.0.0.1:8000/login/")
            self.stdout.write("=" * 40)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error: {str(e)}")
            )
