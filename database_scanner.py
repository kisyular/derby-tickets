#!/usr/bin/env python
"""
Comprehensive database reader - shows all users, tickets, and comments
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticket_project.settings')
django.setup()

from django.contrib.auth.models import User
from tickets.models import Ticket, Comment, UserProfile

def print_all_database_contents():
    """Print everything in the database for verification"""
    
    print("🗄️  COMPLETE DATABASE CONTENTS")
    print("=" * 80)
    
    # 1. ALL USERS
    print("\n👥 ALL USERS:")
    print("-" * 80)
    users = User.objects.all().order_by('id')
    print(f"Total Users: {users.count()}")
    print(f"{'ID':<4} {'USERNAME':<20} {'EMAIL':<25} {'NAME':<25} {'STAFF':<6} {'SUPER':<6}")
    print("-" * 80)
    
    for user in users:
        full_name = f"{user.first_name} {user.last_name}".strip() or "No Name"
        print(f"{user.id:<4} {user.username:<20} {user.email:<25} {full_name:<25} {user.is_staff:<6} {user.is_superuser:<6}")
    
    # 2. ALL USER PROFILES
    print(f"\n📋 ALL USER PROFILES:")
    print("-" * 80)
    profiles = UserProfile.objects.all().order_by('user__id')
    print(f"Total Profiles: {profiles.count()}")
    print(f"{'ID':<4} {'USER_ID':<8} {'USERNAME':<20} {'DEPARTMENT':<15} {'LOCATION':<15}")
    print("-" * 80)
    
    for profile in profiles:
        username = profile.user.username if profile.user else "ORPHANED"
        user_id = profile.user.id if profile.user else "None"
        print(f"{profile.id:<4} {user_id:<8} {username:<20} {profile.department:<15} {profile.location:<15}")
    
    # 3. ALL TICKETS
    print(f"\n🎫 ALL TICKETS:")
    print("-" * 80)
    tickets = Ticket.objects.all().order_by('id')
    print(f"Total Tickets: {tickets.count()}")
    print(f"{'ID':<4} {'TITLE':<40} {'CREATED_BY':<15} {'ASSIGNED_TO':<15} {'STATUS':<12} {'PRIORITY':<8}")
    print("-" * 80)
    
    for ticket in tickets:
        title = ticket.title[:40] if len(ticket.title) <= 40 else ticket.title[:37] + "..."
        created_by = ticket.created_by.username if ticket.created_by else "None"
        assigned_to = ticket.assigned_to.username if ticket.assigned_to else "None"
        
        print(f"{ticket.id:<4} {title:<40} {created_by:<15} {assigned_to:<15} {ticket.status:<12} {ticket.priority:<8}")
    
    # 4. ALL COMMENTS
    print(f"\n💬 ALL COMMENTS:")
    print("-" * 80)
    comments = Comment.objects.all().order_by('id')
    print(f"Total Comments: {comments.count()}")
    print(f"{'ID':<4} {'TICKET_ID':<10} {'AUTHOR':<15} {'CONTENT':<50} {'INTERNAL':<8} {'CREATED':<20}")
    print("-" * 80)
    
    for comment in comments:
        content = comment.content[:50] if len(comment.content) <= 50 else comment.content[:47] + "..."
        author = comment.author.username if comment.author else "None"
        created = comment.created_at.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"{comment.id:<4} #{comment.ticket.id:<9} {author:<15} {content:<50} {comment.is_internal:<8} {created:<20}")
    
    # 5. DETAILED ANALYSIS
    print(f"\n🔍 DETAILED ANALYSIS:")
    print("-" * 80)
    
    # Check for specific users
    users_to_check = ['testuser_delete', 'default_user', 'admin', 'rellika']
    for username in users_to_check:
        try:
            user = User.objects.get(username=username)
            print(f"✅ {username} exists (ID: {user.id})")
            
            # Count their tickets and comments
            tickets_created = Ticket.objects.filter(created_by=user).count()
            tickets_assigned = Ticket.objects.filter(assigned_to=user).count()
            comments_made = Comment.objects.filter(author=user).count()
            
            print(f"   - Tickets created: {tickets_created}")
            print(f"   - Tickets assigned: {tickets_assigned}")
            print(f"   - Comments made: {comments_made}")
            
        except User.DoesNotExist:
            print(f"❌ {username} does NOT exist")
    
    # 6. ORPHANED DATA CHECK
    print(f"\n🔍 ORPHANED DATA CHECK:")
    print("-" * 80)
    
    # Check for tickets with missing users
    orphaned_tickets_created = Ticket.objects.filter(created_by__isnull=True)
    orphaned_tickets_assigned = Ticket.objects.filter(assigned_to__isnull=True)
    orphaned_comments = Comment.objects.filter(author__isnull=True)
    orphaned_profiles = UserProfile.objects.filter(user__isnull=True)
    
    print(f"Tickets with no creator: {orphaned_tickets_created.count()}")
    print(f"Tickets with no assignee: {orphaned_tickets_assigned.count()}")
    print(f"Comments with no author: {orphaned_comments.count()}")
    print(f"Orphaned user profiles: {orphaned_profiles.count()}")
    
    if orphaned_tickets_created.exists():
        print("  Tickets with no creator:")
        for ticket in orphaned_tickets_created:
            print(f"    - #{ticket.id}: {ticket.title}")
    
    if orphaned_comments.exists():
        print("  Comments with no author:")
        for comment in orphaned_comments:
            print(f"    - Comment #{comment.id} on Ticket #{comment.ticket.id}")
    
    if orphaned_profiles.exists():
        print("  Orphaned profiles:")
        for profile in orphaned_profiles:
            print(f"    - Profile #{profile.id} (user_id: {profile.user_id})")
    
    print(f"\n✅ DATABASE SCAN COMPLETE!")
    print("=" * 80)

if __name__ == '__main__':
    print_all_database_contents()
