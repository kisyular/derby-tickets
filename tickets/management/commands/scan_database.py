from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tickets.models import Ticket, Comment, UserProfile, Category


class Command(BaseCommand):
    help = 'Scan and display database contents'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Number of records to display per model (default: 5)',
        )
        parser.add_argument(
            '--model',
            type=str,
            choices=['users', 'profiles', 'tickets', 'comments', 'categories', 'all'],
            default='all',
            help='Specific model to scan (default: all)',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        model = options['model']

        self.stdout.write(" DATABASE CONTENTS SCAN")
        self.stdout.write("=" * 80)
        
        if model in ['users', 'all']:
            self.scan_users(limit)
        
        if model in ['profiles', 'all']:
            self.scan_profiles(limit)
            
        if model in ['categories', 'all']:
            self.scan_categories(limit)
        
        if model in ['tickets', 'all']:
            self.scan_tickets(limit)
        
        if model in ['comments', 'all']:
            self.scan_comments(limit)

    def scan_users(self, limit):
        """Scan and display users."""
        self.stdout.write(f"\nUSERS (First {limit}):")
        self.stdout.write("-" * 80)
        users = User.objects.all().order_by('id')
        self.stdout.write(f"Total Users: {users.count()}")
        self.stdout.write(f"{'ID':<4} {'USERNAME':<20} {'EMAIL':<25} {'NAME':<25} {'STAFF':<6} {'SUPER':<6}")
        self.stdout.write("-" * 80)
        
        for user in users[:limit]:
            full_name = f"{user.first_name} {user.last_name}".strip() or "No Name"
            self.stdout.write(f"{user.id:<4} {user.username:<20} {user.email:<25} {full_name:<25} {user.is_staff:<6} {user.is_superuser:<6}")
        
        if users.count() > limit:
            self.stdout.write(f"... and {users.count() - limit} more users")

    def scan_profiles(self, limit):
        """Scan and display user profiles."""
        self.stdout.write(f"\nUSER PROFILES (First {limit}):")
        self.stdout.write("-" * 80)
        profiles = UserProfile.objects.all().order_by('user__id')
        self.stdout.write(f"Total Profiles: {profiles.count()}")
        self.stdout.write(f"{'ID':<4} {'USER_ID':<8} {'USERNAME':<20} {'DEPARTMENT':<15} {'LOCATION':<15}")
        self.stdout.write("-" * 80)
        
        for profile in profiles[:limit]:
            username = profile.user.username if profile.user else "ORPHANED"
            user_id = profile.user.id if profile.user else "None"
            self.stdout.write(f"{profile.id:<4} {user_id:<8} {username:<20} {profile.department:<15} {profile.location:<15}")
        
        if profiles.count() > limit:
            self.stdout.write(f"... and {profiles.count() - limit} more profiles")

    def scan_categories(self, limit):
        """Scan and display categories."""
        self.stdout.write(f"\nCATEGORIES (First {limit}):")
        self.stdout.write("-" * 80)
        categories = Category.objects.all().order_by('id')
        self.stdout.write(f"Total Categories: {categories.count()}")
        self.stdout.write(f"{'ID':<4} {'NAME':<30} {'CREATED':<20}")
        self.stdout.write("-" * 80)
        
        for category in categories[:limit]:
            created = category.created_at.strftime('%Y-%m-%d %H:%M') if category.created_at else "Unknown"
            self.stdout.write(f"{category.id:<4} {category.name:<30} {created:<20}")
        
        if categories.count() > limit:
            self.stdout.write(f"... and {categories.count() - limit} more categories")

    def scan_tickets(self, limit):
        """Scan and display tickets."""
        self.stdout.write(f"\nTICKETS (First {limit}):")
        self.stdout.write("-" * 80)
        tickets = Ticket.objects.all().order_by('-created_at')
        self.stdout.write(f"Total Tickets: {tickets.count()}")
        self.stdout.write(f"{'ID':<6} {'TITLE':<30} {'STATUS':<12} {'PRIORITY':<8} {'CATEGORY':<15} {'CREATED':<12}")
        self.stdout.write("-" * 80)
        
        for ticket in tickets[:limit]:
            title = ticket.title[:29] if ticket.title else "No Title"
            category = ticket.category.name[:14] if ticket.category else "None"
            created = ticket.created_at.strftime('%Y-%m-%d') if ticket.created_at else "Unknown"
            self.stdout.write(f"{ticket.id:<6} {title:<30} {ticket.status:<12} {ticket.priority:<8} {category:<15} {created:<12}")
        
        if tickets.count() > limit:
            self.stdout.write(f"... and {tickets.count() - limit} more tickets")

    def scan_comments(self, limit):
        """Scan and display comments."""
        self.stdout.write(f"\nCOMMENTS (First {limit}):")
        self.stdout.write("-" * 80)
        comments = Comment.objects.all().order_by('-created_at')
        self.stdout.write(f"Total Comments: {comments.count()}")
        self.stdout.write(f"{'ID':<6} {'TICKET_ID':<10} {'AUTHOR':<20} {'CONTENT':<40} {'CREATED':<12}")
        self.stdout.write("-" * 80)
        
        for comment in comments[:limit]:
            author = comment.author.username if comment.author else "Unknown"
            content = comment.content[:39] if comment.content else "No Content"
            created = comment.created_at.strftime('%Y-%m-%d') if comment.created_at else "Unknown"
            self.stdout.write(f"{comment.id:<6} {comment.ticket.id:<10} {author:<20} {content:<40} {created:<12}")
        
        if comments.count() > limit:
            self.stdout.write(f"... and {comments.count() - limit} more comments")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("Database scan completed!")
