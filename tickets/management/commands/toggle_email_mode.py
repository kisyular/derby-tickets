"""
Management command to toggle email mode between test and production.
Usage: python manage.py toggle_email_mode [test|production]
"""

from django.core.management.base import BaseCommand
import os
import re


class Command(BaseCommand):
    help = 'Toggle email notification mode between test and production'

    def add_arguments(self, parser):
        parser.add_argument(
            'mode',
            nargs='?',
            choices=['test', 'production'],
            help='Set email mode to test or production'
        )

    def handle(self, *args, **options):
        email_utils_path = os.path.join('tickets', 'email_utils.py')
        
        if not os.path.exists(email_utils_path):
            self.stdout.write(
                self.style.ERROR('email_utils.py not found!')
            )
            return

        # Read the current file
        with open(email_utils_path, 'r') as f:
            content = f.read()

        # Check current mode
        current_mode = 'test' if 'in_test=True' in content else 'production'
        
        if not options['mode']:
            # Just show current mode
            self.stdout.write(f"Current email mode: {current_mode}")
            return

        target_mode = options['mode']
        
        if current_mode == target_mode:
            self.stdout.write(f"Email mode is already set to {target_mode}")
            return

        # Toggle the mode
        if target_mode == 'test':
            # Change to test mode
            new_content = re.sub(
                r'in_test=False',
                'in_test=True',
                content
            )
        else:
            # Change to production mode
            new_content = re.sub(
                r'in_test=True',
                'in_test=False',
                content
            )

        # Write the updated content
        with open(email_utils_path, 'w') as f:
            f.write(new_content)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully changed email mode from {current_mode} to {target_mode}')
        )
        
        if target_mode == 'production':
            self.stdout.write(
                self.style.WARNING('PRODUCTION MODE: Emails will be sent to actual recipients!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'TEST MODE: All emails will be sent to {os.environ.get("DJANGO_TEST_EMAIL", "test email")}')
            )
