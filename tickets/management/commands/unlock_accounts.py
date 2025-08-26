"""
Management command to unlock locked user accounts and manage security lockouts.
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from django.db import models
from tickets.security import SecurityManager
from tickets.audit_models import SecurityEvent, LoginAttempt, UserSession, AuditLog
import sys


class Command(BaseCommand):
    help = 'Manage user account lockouts and security restrictions'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--unlock-user',
            type=str,
            help='Unlock a specific user by username or email'
        )
        parser.add_argument(
            '--unlock-ip',
            type=str,
            help='Unlock a specific IP address'
        )
        parser.add_argument(
            '--unlock-all',
            action='store_true',
            help='Unlock all currently locked accounts and IPs'
        )
        parser.add_argument(
            '--list-locked',
            action='store_true',
            help='List all currently locked accounts and IPs'
        )
        parser.add_argument(
            '--reset-attempts',
            type=str,
            help='Reset failed attempt counter for user or IP'
        )
        parser.add_argument(
            '--show-attempts',
            type=str,
            help='Show current attempt count for user or IP'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force the operation without confirmation'
        )
    
    def handle(self, *args, **options):
        if options['list_locked']:
            self.list_locked_accounts()
        elif options['unlock_user']:
            self.unlock_user(options['unlock_user'], force=options['force'])
        elif options['unlock_ip']:
            self.unlock_ip(options['unlock_ip'], force=options['force'])
        elif options['unlock_all']:
            self.unlock_all(force=options['force'])
        elif options['reset_attempts']:
            self.reset_attempts(options['reset_attempts'], force=options['force'])
        elif options['show_attempts']:
            self.show_attempts(options['show_attempts'])
        else:
            self.print_help()
    
    def print_help(self):
        self.stdout.write(self.style.SUCCESS("🔐 Derby Tickets Security Management"))
        self.stdout.write("=" * 50)
        self.stdout.write("")
        self.stdout.write("Available commands:")
        self.stdout.write("  --list-locked              List all locked accounts and IPs")
        self.stdout.write("  --unlock-user <username>   Unlock specific user")
        self.stdout.write("  --unlock-ip <ip>          Unlock specific IP address")
        self.stdout.write("  --unlock-all              Unlock all locked accounts")
        self.stdout.write("  --reset-attempts <id>     Reset attempt counter")
        self.stdout.write("  --show-attempts <id>      Show current attempts")
        self.stdout.write("  --force                   Skip confirmation prompts")
        self.stdout.write("")
        self.stdout.write("Examples:")
        self.stdout.write("  python manage.py unlock_accounts --list-locked")
        self.stdout.write("  python manage.py unlock_accounts --unlock-user alice.wilson@derbyfab.com")
        self.stdout.write("  python manage.py unlock_accounts --unlock-ip 192.168.1.100")
        self.stdout.write("  python manage.py unlock_accounts --unlock-all --force")
    
    def list_locked_accounts(self):
        """List all currently locked accounts and IPs"""
        self.stdout.write(self.style.SUCCESS("🔍 Checking for locked accounts..."))
        self.stdout.write("")
        
        # Check cache for locked accounts
        locked_users = []
        locked_ips = []
        
        # Get recent failed login attempts to identify potential lockouts
        recent_attempts = LoginAttempt.objects.filter(
            timestamp__gte=timezone.now() - timezone.timedelta(minutes=30),
            status__in=['FAILED', 'BLOCKED', 'LOCKED']
        ).values('username', 'ip_address').distinct()
        
        for attempt in recent_attempts:
            username = attempt['username']
            ip_address = attempt['ip_address']
            
            # Check if user is locked
            if SecurityManager.is_locked_out(username):
                attempts = SecurityManager.get_attempt_count(username)
                locked_users.append((username, attempts, ip_address))
            
            # Check if IP is locked
            if SecurityManager.is_locked_out(ip_address):
                attempts = SecurityManager.get_attempt_count(ip_address)
                if ip_address not in [item[2] for item in locked_ips]:
                    locked_ips.append((ip_address, attempts, username))
        
        # Display results
        if locked_users:
            self.stdout.write(self.style.ERROR("🚫 LOCKED USERS:"))
            self.stdout.write("-" * 40)
            for username, attempts, ip in locked_users:
                self.stdout.write(f"  👤 {username}")
                self.stdout.write(f"     Attempts: {attempts}")
                self.stdout.write(f"     Last IP: {ip}")
                self.stdout.write("")
        else:
            self.stdout.write(self.style.SUCCESS("✅ No locked users found"))
        
        if locked_ips:
            self.stdout.write(self.style.ERROR("🚫 LOCKED IP ADDRESSES:"))
            self.stdout.write("-" * 40)
            for ip, attempts, last_user in locked_ips:
                self.stdout.write(f"  🌐 {ip}")
                self.stdout.write(f"     Attempts: {attempts}")
                self.stdout.write(f"     Last User: {last_user}")
                self.stdout.write("")
        else:
            self.stdout.write(self.style.SUCCESS("✅ No locked IPs found"))
        
        # Show recent security events
        recent_locks = SecurityEvent.objects.filter(
            event_type='ACCOUNT_LOCKED',
            timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
        ).order_by('-timestamp')[:10]
        
        if recent_locks:
            self.stdout.write(self.style.WARNING("📊 RECENT LOCKOUTS (Last 24 hours):"))
            self.stdout.write("-" * 40)
            for event in recent_locks:
                user_str = event.user.username if event.user else event.username_attempted
                self.stdout.write(f"  {user_str} at {event.timestamp}")
                self.stdout.write(f"     IP: {event.ip_address}")
                self.stdout.write(f"     Reason: {event.description}")
                self.stdout.write("")
    
    def unlock_user(self, username, force=False):
        """Unlock a specific user account"""
        if not force:
            confirm = input(f"Unlock user '{username}'? (y/N): ")
            if confirm.lower() != 'y':
                self.stdout.write("Operation cancelled.")
                return
        
        # Clear lockout and attempts
        SecurityManager.clear_attempts(username)
        
        # Log the unlock action
        SecurityEvent.objects.create(
            event_type='OTHER',
            severity='MEDIUM',
            username_attempted=username,
            ip_address='127.0.0.1',  # Admin action
            description=f'Account manually unlocked by admin',
            success=True,
            metadata={'action': 'manual_unlock', 'admin_action': True}
        )
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ User '{username}' has been unlocked")
        )
    
    def unlock_ip(self, ip_address, force=False):
        """Unlock a specific IP address"""
        if not force:
            confirm = input(f"Unlock IP '{ip_address}'? (y/N): ")
            if confirm.lower() != 'y':
                self.stdout.write("Operation cancelled.")
                return
        
        # Clear lockout and attempts
        SecurityManager.clear_attempts(ip_address)
        
        # Log the unlock action
        SecurityEvent.objects.create(
            event_type='OTHER',
            severity='MEDIUM',
            ip_address=ip_address,
            description=f'IP address manually unlocked by admin',
            success=True,
            metadata={'action': 'manual_unlock', 'admin_action': True}
        )
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ IP '{ip_address}' has been unlocked")
        )
    
    def unlock_all(self, force=False):
        """Unlock all currently locked accounts"""
        if not force:
            confirm = input("Unlock ALL locked accounts and IPs? (y/N): ")
            if confirm.lower() != 'y':
                self.stdout.write("Operation cancelled.")
                return
        
        # Clear all cache entries that start with our lockout prefixes
        cache.clear()  # Simple approach - clear all cache
        
        # Log the mass unlock action
        SecurityEvent.objects.create(
            event_type='OTHER',
            severity='HIGH',
            ip_address='127.0.0.1',  # Admin action
            description='All accounts and IPs manually unlocked by admin (mass unlock)',
            success=True,
            metadata={'action': 'mass_unlock', 'admin_action': True}
        )
        
        self.stdout.write(
            self.style.SUCCESS("✅ All locked accounts and IPs have been unlocked")
        )
    
    def reset_attempts(self, identifier, force=False):
        """Reset attempt counter for user or IP"""
        attempts = SecurityManager.get_attempt_count(identifier)
        
        if attempts == 0:
            self.stdout.write(f"No attempts recorded for '{identifier}'")
            return
        
        if not force:
            confirm = input(f"Reset {attempts} attempts for '{identifier}'? (y/N): ")
            if confirm.lower() != 'y':
                self.stdout.write("Operation cancelled.")
                return
        
        SecurityManager.clear_attempts(identifier)
        self.stdout.write(
            self.style.SUCCESS(f"✅ Reset {attempts} attempts for '{identifier}'")
        )
    
    def show_attempts(self, identifier):
        """Show current attempt count for user or IP"""
        attempts = SecurityManager.get_attempt_count(identifier)
        is_locked = SecurityManager.is_locked_out(identifier)
        
        self.stdout.write(f"📊 Status for '{identifier}':")
        self.stdout.write(f"   Attempts: {attempts}")
        self.stdout.write(f"   Locked: {'Yes' if is_locked else 'No'}")
        
        if attempts > 0:
            # Show recent login attempts from database
            recent_attempts = LoginAttempt.objects.filter(
                models.Q(username=identifier) | models.Q(ip_address=identifier),
                timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
            ).order_by('-timestamp')[:5]
            
            if recent_attempts:
                self.stdout.write("   Recent attempts:")
                for attempt in recent_attempts:
                    status_color = self.style.ERROR if attempt.status != 'SUCCESS' else self.style.SUCCESS
                    self.stdout.write(f"     {status_color(attempt.status)} - {attempt.timestamp}")
