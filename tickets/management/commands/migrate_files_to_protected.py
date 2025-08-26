import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from tickets.models import TicketAttachment


class Command(BaseCommand):
    help = 'Migrate existing ticket attachments to protected directory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be moved without actually moving files',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be moved'))
        
        # Get all ticket attachments
        attachments = TicketAttachment.objects.all()
        moved_count = 0
        error_count = 0
        
        for attachment in attachments:
            old_path = os.path.join(settings.MEDIA_ROOT, attachment.file.name)
            
            # Check if file is already in protected directory
            if attachment.file.name.startswith('protected/'):
                self.stdout.write(f'Skipping {attachment.file.name} - already in protected directory')
                continue
            
            # Generate new protected path
            filename = os.path.basename(attachment.file.name)
            new_relative_path = f"protected/attachments/tickets/{attachment.ticket.id}/{filename}"
            new_path = os.path.join(settings.MEDIA_ROOT, new_relative_path)
            
            if os.path.exists(old_path):
                try:
                    if not dry_run:
                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        
                        # Move the file
                        shutil.move(old_path, new_path)
                        
                        # Update the database record
                        attachment.file.name = new_relative_path
                        attachment.save(update_fields=['file'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'{"Would move" if dry_run else "Moved"}: {old_path} -> {new_path}')
                    )
                    moved_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error moving {old_path}: {str(e)}')
                    )
                    error_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'File not found: {old_path}')
                )
                error_count += 1
        
        # Summary
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'DRY RUN COMPLETE: Would move {moved_count} files, {error_count} errors/warnings')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'MIGRATION COMPLETE: Moved {moved_count} files, {error_count} errors/warnings')
            )
            
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'Please review the {error_count} errors/warnings above')
            )
