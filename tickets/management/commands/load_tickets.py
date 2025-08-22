from django.core.management.base import BaseCommand
import pandas as pd
from datetime import datetime
import pytz
from django.db import transaction
from django.contrib.auth.models import User
from tickets.models import Ticket, UserProfile, Category


class Command(BaseCommand):
    help = 'Load ticket data from CSV file using pandas'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean existing tickets before loading',
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        clean_first = options['clean']

        if clean_first:
            self.stdout.write("Cleaning existing tickets...")
            with transaction.atomic():
                ticket_count = Ticket.objects.count()
                Ticket.objects.all().delete()
                self.stdout.write(f"Deleted {ticket_count} existing tickets")

        self.stdout.write(f"Loading tickets from {csv_file}...")
        
        try:
            success_count = self.load_tickets_from_csv(csv_file)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully loaded {success_count} tickets')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error loading tickets: {str(e)}')
            )

    def parse_datetime(self, date_str):
        """Parse datetime strings from the CSV with various formats."""
        if pd.isna(date_str) or not date_str or date_str.strip() == '':
            return None
        
        # Clean the date string
        date_str = str(date_str).strip()
        
        # Common formats in the CSV
        formats = [
            '%m/%d/%Y %I:%M %p UTC',  # 11/3/2022 1:37 pm UTC
            '%m/%d/%Y %I:%M:%S %p UTC',  # 11/3/2022 1:37:45 pm UTC
            '%m/%d/%Y %H:%M UTC',  # 11/3/2022 13:37 UTC
            '%m/%d/%Y %H:%M:%S UTC',  # 11/3/2022 13:37:45 UTC
            '%m/%d/%Y',  # 11/3/2022
            '%Y-%m-%d %H:%M:%S',  # Standard format
            '%Y-%m-%d',  # Date only
        ]
        
        for fmt in formats:
            try:
                # Handle timezone
                if 'UTC' in date_str:
                    dt = datetime.strptime(date_str, fmt)
                    dt = pytz.UTC.localize(dt) if dt.tzinfo is None else dt
                else:
                    dt = datetime.strptime(date_str, fmt)
                    # Assume UTC if no timezone specified
                    dt = pytz.UTC.localize(dt) if dt.tzinfo is None else dt
                return dt
            except ValueError:
                continue
        
        self.stdout.write(f"Warning: Could not parse date: {date_str}")
        return None

    def find_or_create_category(self, category_name):
        """Find an existing category by name or create 'Other' as fallback."""
        if not category_name or pd.isna(category_name):
            # Return 'Other' category as default
            try:
                return Category.objects.get(name='Other')
            except Category.DoesNotExist:
                self.stdout.write("Warning: 'Other' category not found, creating it...")
                other_category = Category(name='Other')
                other_category.save(use_auto_now=False)  # Use current timestamp
                return other_category
        
        category_name = str(category_name).strip()
        
        # Try to find exact match first
        try:
            return Category.objects.get(name=category_name)
        except Category.DoesNotExist:
            # Try case-insensitive match
            try:
                return Category.objects.get(name__iexact=category_name)
            except Category.DoesNotExist:
                # If not found, return 'Other' category
                self.stdout.write(f"Warning: Category '{category_name}' not found, using 'Other'")
                try:
                    return Category.objects.get(name='Other')
                except Category.DoesNotExist:
                    self.stdout.write("Warning: 'Other' category not found, creating it...")
                    other_category = Category(name='Other')
                    other_category.save(use_auto_now=False)
                    return other_category

    def find_or_create_user(self, name, department=None, location=None):
        """Find or create a user by name, handling various name formats."""
        if pd.isna(name) or not name or str(name).strip() == '':
            return None
        
        name = str(name).strip()
        
        # Handle email addresses first
        if '@' in name:
            email = name.lower()
            username = email.split('@')[0]
            
            # Try to find user by email
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist:
                # Try to find by username
                try:
                    return User.objects.get(username=username)
                except User.DoesNotExist:
                    # Create new user
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        first_name=username.title(),
                        last_name=''
                    )
                    
                    # Create UserProfile
                    UserProfile.objects.create(
                        user=user,
                        department=department or '',
                        location=location or ''
                    )
                    
                    return user
        
        # Handle regular names
        # Try to find existing user by first/last name combination
        name_parts = name.split()
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:])
            
            try:
                return User.objects.get(first_name__iexact=first_name, last_name__iexact=last_name)
            except User.DoesNotExist:
                pass
        
        # Try to find by username (name as username)
        username = name.lower().replace(' ', '_')
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                username=username,
                email=f"{username}@company.com",  # Placeholder email
                first_name=name_parts[0] if name_parts else name,
                last_name=' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            )
            
            # Create UserProfile
            UserProfile.objects.create(
                user=user,
                department=department or '',
                location=location or ''
            )
            
            return user

    def load_tickets_from_csv(self, csv_file):
        """Load tickets from CSV file."""
        # Read CSV with pandas
        df = pd.read_csv(csv_file)
        
        success_count = 0
        
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Extract data from row
                    ticket_id = row.get('Ticket ID') or row.get('ID')
                    title = row.get('Subject') or row.get('Title', '')
                    description = row.get('Description', '')
                    priority = row.get('Priority', 'Medium')
                    status = row.get('Status', 'Open')
                    category_name = row.get('Category')
                    created_by_name = row.get('Created By') or row.get('Reporter')
                    assigned_to_name = row.get('Assigned To')
                    created_at_str = row.get('Created At') or row.get('Created')
                    closed_at_str = row.get('Closed At') or row.get('Closed')
                    department = row.get('Department', '')
                    location = row.get('Location', '')
                    
                    # Parse dates
                    created_at = self.parse_datetime(created_at_str)
                    closed_at = self.parse_datetime(closed_at_str) if closed_at_str else None
                    
                    # Find or create users
                    created_by = self.find_or_create_user(created_by_name, department, location)
                    assigned_to = self.find_or_create_user(assigned_to_name, department, location)
                    
                    # Find or create category
                    category = self.find_or_create_category(category_name)
                    
                    # Validate priority and status
                    valid_priorities = [choice[0] for choice in Ticket.PRIORITY_CHOICES]
                    if priority not in valid_priorities:
                        priority = 'Medium'
                    
                    valid_statuses = [choice[0] for choice in Ticket.STATUS_CHOICES]
                    if status not in valid_statuses:
                        status = 'Open'
                    
                    # Create ticket
                    ticket = Ticket(
                        title=title[:200],  # Limit title length
                        description=description,
                        priority=priority,
                        status=status,
                        category=category,
                        created_by=created_by,
                        assigned_to=assigned_to,
                        department=department,
                        location=location,
                        closed_on=closed_at
                    )
                    
                    # Set created_at if available
                    if created_at:
                        ticket.created_at = created_at
                    
                    ticket.save(use_auto_now=False)
                    success_count += 1
                    
                    if success_count % 100 == 0:
                        self.stdout.write(f"Loaded {success_count} tickets...")
                        
                except Exception as e:
                    self.stdout.write(f"Error processing row {index}: {str(e)}")
                    continue
        
        return success_count
