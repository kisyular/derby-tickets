"""
Management command to create or reset admin user for the ticket system.
Combines functionality of create_admin and reset_admin commands.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tickets.models import UserProfile
import os


class Command(BaseCommand):
    help = "Create or reset admin user for the ticket system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            default=os.environ.get("DJANGO_ADMIN_USERNAME", "admin"),
            help="Admin username",
        )
        parser.add_argument(
            "--email",
            type=str,
            default=os.environ.get("DJANGO_ADMIN_EMAIL", "admin@derbyfab.com"),
            help="Admin email",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=os.environ.get("DJANGO_ADMIN_PASSWORD", "admin123"),
            help="Admin password",
        )
        parser.add_argument(
            "--reset", action="store_true", help="Reset existing admin user password"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force create/update even if user exists",
        )

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]
        reset_mode = options["reset"]
        force = options["force"]

        self.stdout.write(self.style.SUCCESS("Admin User Management Tool"))
        self.stdout.write("=" * 40)

        try:
            # Check if user exists
            user_exists = User.objects.filter(username=username).exists()

            if user_exists and not (reset_mode or force):
                self.stdout.write(
                    self.style.WARNING(f'User "{username}" already exists.')
                )
                self.stdout.write(
                    self.style.WARNING(
                        "Use --reset to reset password or --force to update user."
                    )
                )
                return

            if user_exists:
                # Update existing user
                user = User.objects.get(username=username)
                user.email = email
                user.set_password(password)
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True
                user.first_name = os.environ.get("DJANGO_ADMIN_FIRST_NAME", "System")
                user.last_name = os.environ.get(
                    "DJANGO_ADMIN_LAST_NAME", "Administrator"
                )
                user.save()

                action = "updated"
            else:
                # Create new user
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    first_name=os.environ.get("DJANGO_ADMIN_FIRST_NAME", "System"),
                    last_name=os.environ.get("DJANGO_ADMIN_LAST_NAME", "Administrator"),
                )
                action = "created"

            # Ensure the user profile has admin role
            profile, created = UserProfile.objects.get_or_create(
                user=user, defaults={"role": "admin"}
            )
            if not created and profile.role != "admin":
                profile.role = "admin"
                profile.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully {action} admin user "{username}" with admin role'
                )
            )
            self.stdout.write(f"Username: {username}")
            self.stdout.write(f"Email: {email}")
            self.stdout.write(f"Role: Admin")
            self.stdout.write(f"Superuser: Yes")

            if action == "created" or reset_mode:
                self.stdout.write(
                    self.style.WARNING(
                        "Please change the default password after first login!"
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error {action if "action" in locals() else "managing"} admin user: {str(e)}'
                )
            )
