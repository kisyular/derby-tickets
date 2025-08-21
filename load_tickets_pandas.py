#!/usr/bin/env python
"""
Robust ticket data loader using pandas for CSV parsing.
Handles multi-line descriptions and complex CSV formats.
"""

import os
import sys
import pandas as pd
from datetime import datetime
import pytz

# Setup Django environment first
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticket_project.settings')

import django
django.setup()

# Now import Django models after setup
from django.db import transaction
from django.contrib.auth.models import User
from tickets.models import Ticket, UserProfile, Category

def parse_datetime(date_str):
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
    
    print(f"Warning: Could not parse date: {date_str}")
    return None

def find_or_create_category(category_name):
    """Find an existing category by name or create 'Other' as fallback."""
    if not category_name or pd.isna(category_name):
        # Return 'Other' category as default
        try:
            return Category.objects.get(name='Other')
        except Category.DoesNotExist:
            print("Warning: 'Other' category not found, creating it...")
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
            print(f"Warning: Category '{category_name}' not found, using 'Other'")
            try:
                return Category.objects.get(name='Other')
            except Category.DoesNotExist:
                print("Warning: 'Other' category not found, creating it...")
                other_category = Category(name='Other')
                other_category.save(use_auto_now=False)
                return other_category

def find_or_create_user(name, department=None, location=None):
    """Find or create a user by name, handling various name formats."""
    if pd.isna(name) or not name or str(name).strip() == '':
        return None
    
    name = str(name).strip()
    
    # Handle email addresses first (like the working load_data_fixed.py)
    if '@' in name:
        try:
            # Try to find by email first
            user = User.objects.filter(email__iexact=name).first()
            if user:
                return user
            # If not found, create with email as username
            username = name
        except Exception:
            return None
    else:
        # For non-email names, try to find existing user by full name
        name_parts = name.split()
        if not name_parts:
            return None
        
        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
        
        # Try to find by full name
        try:
            user = User.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name
            ).first()
            if user:
                return user
        except Exception:
            pass
        
        # Generate email-like username for consistency
        username = name.lower().replace(' ', '').replace('.', '').replace('-', '') + '@derbyfab.com'
    
    # Create new user
    try:
        # For non-email names, parse first/last name
        if '@' not in name:
            name_parts = name.split()
            first_name = name_parts[0] if name_parts else name
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
        else:
            # For email addresses, try to extract name from email
            email_prefix = name.split('@')[0]
            # Handle common email patterns like firstname.lastname
            if '.' in email_prefix:
                parts = email_prefix.split('.')
                first_name = parts[0].capitalize()
                last_name = '.'.join(parts[1:]).capitalize()
            else:
                first_name = email_prefix.capitalize()
                last_name = ''
        
        # Ensure username is unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            if '@' in base_username:
                email_parts = base_username.split('@')
                username = f"{email_parts[0]}_{counter}@{email_parts[1]}"
            else:
                username = f"{base_username}_{counter}"
            counter += 1
        
        user = User.objects.create_user(
            username=username,
            email=username if '@' in username else f"{username}@company.com",
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )
        user.set_password('defaultpass123')
        user.save()
        
        # Create or update UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        if department and not pd.isna(department):
            profile.department = str(department).strip()
        if location and not pd.isna(location):
            profile.location = str(location).strip()
        profile.save()
        
        print(f"Created user: {user.get_full_name()} ({user.email})")
        return user
        
    except Exception as e:
        print(f"Error creating user '{name}': {e}")
        return None

def load_tickets_from_csv(csv_path):
    """Load tickets from CSV using pandas for robust parsing."""
    
    print(f"Loading tickets from: {csv_path}")
    
    try:
        # Read CSV with pandas - it handles multi-line fields better
        df = pd.read_csv(
            csv_path,
            dtype=str,  # Read all as strings initially
            na_values=['', 'NULL', 'null', 'None'],
            keep_default_na=False,
            encoding='utf-8',
            quoting=1,  # QUOTE_ALL
            skipinitialspace=True
        )
        
        print(f"Loaded {len(df)} rows from CSV")
        print(f"Columns: {list(df.columns)}")
        
        # Display first few rows for verification
        print("\nFirst 3 rows:")
        print(df.head(3).to_string())
        
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    # Track statistics
    created_count = 0
    skipped_count = 0
    error_count = 0
    
    # Process tickets in chunks for better memory management
    chunk_size = 100
    total_chunks = len(df) // chunk_size + (1 if len(df) % chunk_size > 0 else 0)
    
    for chunk_idx in range(total_chunks):
        start_idx = chunk_idx * chunk_size
        end_idx = min((chunk_idx + 1) * chunk_size, len(df))
        chunk = df.iloc[start_idx:end_idx]
        
        print(f"\nProcessing chunk {chunk_idx + 1}/{total_chunks} (rows {start_idx + 1}-{end_idx})")
        
        with transaction.atomic():
            for idx, row in chunk.iterrows():
                try:
                    # Helper function to safely extract and clean string data
                    def safe_str(value):
                        if pd.isna(value) or value is None:
                            return ''
                        return str(value).strip()
                    
                    # Extract ticket data
                    ticket_number = safe_str(row.get('Ticket Number', ''))
                    summary = safe_str(row.get('Summary', ''))
                    description = safe_str(row.get('Description', ''))
                    assigned_to_name = safe_str(row.get('Assigned To', ''))
                    created_by_name = safe_str(row.get('Created By', ''))
                    category = safe_str(row.get('Category', ''))
                    priority = safe_str(row.get('Priority', ''))
                    status = safe_str(row.get('Status', ''))
                    department = safe_str(row.get('Department', ''))
                    location = safe_str(row.get('Location', ''))
                    
                    # Parse dates
                    created_at = parse_datetime(row.get('Created On', ''))
                    closed_on = parse_datetime(row.get('Closed On', ''))
                    due_on = parse_datetime(row.get('Due On', ''))
                    
                    # Validate required fields
                    if not ticket_number or not summary:
                        print(f"Row {idx + 1}: Missing required fields (ticket_number or summary)")
                        skipped_count += 1
                        continue
                    
                    # Check if ticket already exists
                    if Ticket.objects.filter(ticket_number=ticket_number).exists():
                        print(f"Row {idx + 1}: Ticket {ticket_number} already exists, skipping")
                        skipped_count += 1
                        continue
                    
                    # Find or create users
                    created_by = find_or_create_user(created_by_name, department, location)
                    assigned_to = find_or_create_user(assigned_to_name, department, location)
                    
                    # Find category by name
                    category_obj = find_or_create_category(category)
                    
                    # Map status values
                    status_mapping = {
                        'open': 'Open',
                        'closed': 'Closed', 
                        'in progress': 'In Progress',
                    }
                    mapped_status = status_mapping.get(status.lower(), 'Open')
                    
                    # Map priority values
                    priority_mapping = {
                        'low': 'Low',
                        'medium': 'Medium',
                        'high': 'High',
                    }
                    mapped_priority = priority_mapping.get(priority.lower(), 'Medium')
                    
                    # Create ticket with custom dates from CSV
                    ticket = Ticket(
                        ticket_number=ticket_number,
                        title=summary,
                        description=description or 'No description provided',
                        created_by=created_by,
                        assigned_to=assigned_to,
                        status=mapped_status,
                        priority=mapped_priority,
                        category=category_obj,
                        location=location or '',
                        department=department or '',
                        created_at=created_at or datetime.now(pytz.UTC),
                        closed_on=closed_on,
                        due_on=due_on,
                    )
                    
                    # Save with use_auto_now=False to preserve CSV dates
                    ticket.save(use_auto_now=False)
                    
                    created_count += 1
                    
                    if created_count % 10 == 0:
                        print(f"  Created {created_count} tickets so far...")
                    
                except Exception as e:
                    print(f"Row {idx + 1}: Error creating ticket: {e}")
                    error_count += 1
                    continue
    
    # Final statistics
    print(f"\n" + "="*50)
    print(f"IMPORT COMPLETED")
    print(f"Total rows processed: {len(df)}")
    print(f"Tickets created: {created_count}")
    print(f"Tickets skipped: {skipped_count}")
    print(f"Errors encountered: {error_count}")
    print(f"="*50)

if __name__ == "__main__":
    csv_file = "data/ticket_export.csv"
    
    if not os.path.exists(csv_file):
        print(f"Error: CSV file not found at {csv_file}")
        sys.exit(1)
    
    print("Starting robust ticket import with pandas...")
    load_tickets_from_csv(csv_file)
    print("Import process completed!")
