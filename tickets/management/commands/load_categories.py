from django.core.management.base import BaseCommand
from datetime import datetime
import pytz
from tickets.models import Category


class Command(BaseCommand):
    help = 'Load predefined categories with legacy timestamps'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean existing categories before loading',
        )

    def handle(self, *args, **options):
        clean_first = options['clean']

        if clean_first:
            self.stdout.write("Cleaning existing categories...")
            category_count = Category.objects.count()
            Category.objects.all().delete()
            self.stdout.write(f"Deleted {category_count} existing categories")

        self.stdout.write("Loading predefined categories...")
        
        try:
            success_count = self.load_categories()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully loaded {success_count} categories')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error loading categories: {str(e)}')
            )

    def load_categories(self):
        """Load categories with legacy timestamps."""
        
        # Category data with legacy timestamps
        category_data = [
            ('Hardware', '2017-09-05T18:53:25+00:00', '2017-09-05T18:53:25+00:00'),
            ('Software', '2017-09-05T18:53:25+00:00', '2017-09-05T18:53:25+00:00'),
            ('Network', '2017-09-05T18:53:25+00:00', '2017-09-05T18:53:25+00:00'),
            ('Email', '2017-09-05T18:53:25+00:00', '2017-09-05T18:53:25+00:00'),
            ('Maintenance', '2017-09-05T18:53:25+00:00', '2017-09-05T18:53:25+00:00'),
            ('Other', '2017-09-05T18:53:25+00:00', '2017-09-05T18:53:25+00:00'),
            ('EDI', '2022-11-03T18:03:49+00:00', '2022-11-03T18:03:49+00:00'),
            ('ON-OFF Boarding', '2022-11-03T18:04:03+00:00', '2022-11-03T18:04:03+00:00'),
            ('PLEX UX', '2022-11-03T18:04:11+00:00', '2022-11-03T18:04:11+00:00'),
            ('Project', '2022-11-03T18:04:42+00:00', '2022-11-03T18:04:42+00:00'),
            ('Services', '2022-11-08T14:58:20+00:00', '2022-11-08T14:58:20+00:00'),
            ('Workflow', '2022-11-10T13:48:25+00:00', '2022-11-10T13:48:25+00:00'),
            ('Labels', '2022-11-10T13:51:14+00:00', '2022-11-10T13:51:14+00:00'),
            ('Mach2', '2022-11-10T13:52:54+00:00', '2022-11-10T13:52:54+00:00'),
            ('End User Support', '2022-11-10T14:07:57+00:00', '2022-11-10T14:07:57+00:00'),
            ('CustApp', '2022-11-10T14:23:57+00:00', '2025-03-13T20:50:44+00:00'),
            ('Website', '2023-05-10T17:57:25+00:00', '2023-05-10T17:57:33+00:00'),
            ('Checksheets', '2023-08-23T10:49:46+00:00', '2023-08-23T10:49:46+00:00'),
            ('PLEX UX Project/Case', '2023-10-19T18:31:28+00:00', '2023-10-19T18:31:28+00:00'),
            ('PLEX Classic', '2023-10-19T18:34:49+00:00', '2023-10-19T18:34:49+00:00'),
            ('PLEX UX Security', '2023-10-19T19:01:15+00:00', '2023-10-19T19:01:15+00:00'),
            ('VPN', '2023-10-20T15:23:29+00:00', '2023-10-20T15:23:29+00:00'),
            ('Reports - Custom/Plex', '2023-10-24T11:08:26+00:00', '2023-10-24T11:08:26+00:00'),
            ('Phone', '2023-10-26T16:57:17+00:00', '2023-10-26T16:57:17+00:00'),
            ('Apptivo', '2023-11-06T18:01:26+00:00', '2023-11-06T18:01:26+00:00'),
            ('MS Teams', '2024-03-05T18:33:14+00:00', '2024-03-05T18:33:14+00:00'),
            ('Smart Scanner', '2024-03-06T14:33:25+00:00', '2024-03-06T14:33:25+00:00'),
            ('MES', '2024-03-06T14:33:55+00:00', '2024-03-06T14:33:55+00:00'),
            ('Remote Desktop', '2024-03-06T19:42:00+00:00', '2024-03-06T19:42:00+00:00'),
            ('Hosting', '2024-03-07T19:49:01+00:00', '2024-03-07T19:49:01+00:00'),
            ('PLEX UX DMS', '2024-03-11T16:34:05+00:00', '2024-03-11T16:34:05+00:00'),
            ('File Share', '2024-03-11T17:20:31+00:00', '2024-03-11T17:20:31+00:00'),
            ('Outlook', '2024-03-12T13:55:27+00:00', '2024-03-12T13:55:27+00:00'),
            ('Power BI', '2024-03-12T19:13:15+00:00', '2024-03-12T19:13:15+00:00'),
            ('Chrome', '2024-03-13T13:05:07+00:00', '2024-03-13T13:05:07+00:00'),
            ('Active Directory', '2024-03-13T14:42:10+00:00', '2024-03-13T14:42:10+00:00'),
            ('Printers', '2024-03-13T15:17:44+00:00', '2024-03-13T15:17:44+00:00'),
            ('Computers', '2024-03-13T20:50:00+00:00', '2024-03-13T20:50:00+00:00'),
        ]
        
        success_count = 0
        
        for name, created_str, updated_str in category_data:
            try:
                # Check if category already exists
                if Category.objects.filter(name=name).exists():
                    self.stdout.write(f"Category '{name}' already exists, skipping...")
                    continue
                
                # Parse timestamps
                created_at = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                updated_at = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                
                # Create category
                category = Category(
                    name=name,
                    created_at=created_at,
                    updated_at=updated_at
                )
                category.save(use_auto_now=False)  # Don't override with current time
                success_count += 1
                
                self.stdout.write(f"Created category: {name}")
                
            except Exception as e:
                self.stdout.write(f"Error creating category '{name}': {str(e)}")
                continue
        
        return success_count
