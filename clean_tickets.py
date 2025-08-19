#!/usr/bin/env python
"""
Clean tickets and reimport with the fixed script.
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticket_project.settings')
django.setup()

from django.db import transaction
from django.contrib.auth.models import User
from tickets.models import Ticket, UserProfile

def clean_and_reimport():
    """Clean existing tickets and run the reimport."""
    
    print("Cleaning existing tickets...")
    with transaction.atomic():
        # Delete all tickets
        ticket_count = Ticket.objects.count()
        Ticket.objects.all().delete()
        print(f"Deleted {ticket_count} existing tickets")
        
        # Keep users but clean up any orphaned profiles
        orphaned_profiles = UserProfile.objects.filter(user__isnull=True).count()
        if orphaned_profiles > 0:
            UserProfile.objects.filter(user__isnull=True).delete()
            print(f"Cleaned up {orphaned_profiles} orphaned user profiles")
    
    print("Database cleaned successfully!")
    print("You can now run: python load_tickets_pandas.py")

if __name__ == "__main__":
    clean_and_reimport()
