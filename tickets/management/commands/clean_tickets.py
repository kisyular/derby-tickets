from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from tickets.models import Ticket, UserProfile


class Command(BaseCommand):
    help = 'Clean existing tickets and user profiles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tickets-only',
            action='store_true',
            help='Only clean tickets, keep users and profiles',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without prompting',
        )

    def handle(self, *args, **options):
        tickets_only = options['tickets_only']
        confirm = options['confirm']

        if not confirm:
            # Ask for confirmation
            self.stdout.write(
                self.style.WARNING('This will delete data from the database!')
            )
            if tickets_only:
                self.stdout.write('- All tickets will be deleted')
            else:
                self.stdout.write('- All tickets will be deleted')
                self.stdout.write('- Orphaned user profiles will be cleaned')
            
            confirm_input = input('Are you sure you want to continue? (yes/no): ')
            if confirm_input.lower() != 'yes':
                self.stdout.write('Operation cancelled.')
                return

        self.stdout.write("Starting cleanup...")
        
        try:
            with transaction.atomic():
                # Delete all tickets
                ticket_count = Ticket.objects.count()
                Ticket.objects.all().delete()
                self.stdout.write(f"✓ Deleted {ticket_count} tickets")
                
                if not tickets_only:
                    # Clean up orphaned profiles
                    orphaned_profiles = UserProfile.objects.filter(user__isnull=True).count()
                    if orphaned_profiles > 0:
                        UserProfile.objects.filter(user__isnull=True).delete()
                        self.stdout.write(f"✓ Cleaned up {orphaned_profiles} orphaned user profiles")
                    else:
                        self.stdout.write("✓ No orphaned user profiles found")

            self.stdout.write(
                self.style.SUCCESS('Database cleanup completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during cleanup: {str(e)}')
            )
