#!/usr/bin/env python
"""Script to populate Category table with legacy data using specific timestamps."""

import os
import sys
import django
from datetime import datetime
import pytz

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticket_project.settings')
django.setup()

from tickets.models import Category

def load_categories():
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
        ('Security', '2024-03-20T12:07:38+00:00', '2024-03-20T12:07:38+00:00'),
        ('Password', '2024-05-16T12:24:01+00:00', '2024-05-16T12:24:01+00:00'),
        ('Plex UX Report', '2024-05-23T21:30:19+00:00', '2024-05-23T21:30:19+00:00'),
        ('PCInfo', '2024-07-08T18:11:30+00:00', '2024-07-08T18:11:30+00:00'),
        ('Work-From-Home Setup', '2024-10-22T12:05:27+00:00', '2024-10-22T12:05:27+00:00'),
        ('Invalid Email/Ticket', '2024-10-31T16:33:22+00:00', '2024-10-31T16:33:22+00:00'),
        ('Credentials - VPN', '2025-02-19T13:21:27+00:00', '2025-02-19T13:21:27+00:00'),
        ('EUS/ACCT', '2025-02-21T15:50:26+00:00', '2025-02-21T15:50:26+00:00'),
        ('EUS/EMAIL', '2025-02-21T15:50:32+00:00', '2025-02-21T15:50:32+00:00'),
        ('EUS/GENRL', '2025-02-21T15:50:39+00:00', '2025-02-21T15:50:39+00:00'),
        ('EUS/HRDWR', '2025-02-21T15:50:44+00:00', '2025-02-21T15:50:44+00:00'),
        ('EUS/NETW', '2025-02-21T15:50:49+00:00', '2025-02-21T15:50:49+00:00'),
        ('EUS/NEWEQ', '2025-02-21T15:50:55+00:00', '2025-02-21T15:50:55+00:00'),
        ('EUS/PRNT', '2025-02-21T15:51:00+00:00', '2025-02-21T15:51:00+00:00'),
        ('EUS/REMT', '2025-02-21T15:51:06+00:00', '2025-02-21T15:51:06+00:00'),
        ('EUS/SECRTY', '2025-02-21T15:51:11+00:00', '2025-02-21T15:51:11+00:00'),
        ('EUS/SFTWR', '2025-02-21T15:51:17+00:00', '2025-02-21T15:51:17+00:00'),
        ('Outside IT Scope', '2025-02-27T18:15:22+00:00', '2025-02-27T18:15:22+00:00'),
        ('EDI/InvldTP', '2025-03-13T13:47:58+00:00', '2025-03-13T13:47:58+00:00'),
        ('EDI/GXS', '2025-03-13T14:56:50+00:00', '2025-03-13T14:56:50+00:00'),
        ('CustApp/CEDB', '2025-03-13T20:28:12+00:00', '2025-03-13T20:51:00+00:00'),
        ('Cust/Pasture', '2025-03-13T20:38:21+00:00', '2025-03-13T20:51:08+00:00'),
        ('CustApp/PlexRpt', '2025-03-13T21:46:41+00:00', '2025-03-13T21:46:41+00:00'),
        ('Merged', '2025-07-11T15:46:11+00:00', '2025-07-11T15:46:11+00:00'),
    ]
    
    print(f"Loading {len(category_data)} categories with legacy timestamps...")
    
    created_count = 0
    updated_count = 0
    
    for name, created_str, updated_str in category_data:
        # Parse timestamps
        created_at = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
        updated_at = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
        
        # Check if category already exists
        category, created = Category.objects.get_or_create(name=name)
        
        if created:
            print(f"✅ Created category: {name}")
            created_count += 1
        else:
            print(f"🔄 Updated category: {name}")
            updated_count += 1
        
        # Set the specific timestamps (bypass auto_now by using use_auto_now=False)
        category.created_at = created_at
        category.updated_at = updated_at
        category.save(use_auto_now=False)
        
        print(f"   Created: {created_at}")
        print(f"   Updated: {updated_at}")
    
    print(f"\n🎉 Category import completed!")
    print(f"   Categories created: {created_count}")
    print(f"   Categories updated: {updated_count}")
    print(f"   Total categories: {Category.objects.count()}")

if __name__ == '__main__':
    load_categories()
