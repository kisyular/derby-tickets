"""
Django management command to display security audit dashboard.
Shows comprehensive security metrics and recent events.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Q
from tickets.audit_security import audit_security_manager
from tickets.audit_models import SecurityEvent, LoginAttempt, UserSession, AuditLog
import json


class Command(BaseCommand):
    help = 'Display comprehensive security audit dashboard'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Number of hours to look back (default: 24)'
        )
        parser.add_argument(
            '--show-events',
            action='store_true',
            help='Show recent security events'
        )
        parser.add_argument(
            '--show-attempts',
            action='store_true',
            help='Show recent login attempts'
        )
        parser.add_argument(
            '--show-sessions',
            action='store_true',
            help='Show active sessions'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output in JSON format'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        
        # Get comprehensive security summary
        summary = audit_security_manager.get_security_summary(hours)
        
        if options['json']:
            self.stdout.write(json.dumps(summary, indent=2, default=str))
            return
        
        # Display formatted dashboard
        self.display_dashboard(summary, hours, options)
    
    def display_dashboard(self, summary, hours, options):
        """Display a formatted security dashboard"""
        
        # Header
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS(f"SECURITY AUDIT DASHBOARD - Last {hours} Hours"))
        self.stdout.write(self.style.SUCCESS("=" * 80))
        
        # Security Events Summary
        self.stdout.write(self.style.WARNING("\n📊 SECURITY EVENTS SUMMARY"))
        self.stdout.write("-" * 40)
        events = summary['security_events']
        self.stdout.write(f"Total Events: {events['total']}")
        self.stdout.write(f"Critical Unresolved: {events['critical_unresolved']}")
        
        if events['by_severity']:
            self.stdout.write("\nBy Severity:")
            for severity, count in events['by_severity'].items():
                icon = self.get_severity_icon(severity)
                self.stdout.write(f"  {icon} {severity}: {count}")
        
        if events['by_type'] and len(events['by_type']) > 0:
            self.stdout.write("\nTop Event Types:")
            sorted_types = sorted(events['by_type'].items(), key=lambda x: x[1], reverse=True)[:5]
            for event_type, count in sorted_types:
                self.stdout.write(f"  • {event_type}: {count}")
        
        # Login Attempts Summary
        self.stdout.write(self.style.WARNING("\n🔐 LOGIN ATTEMPTS SUMMARY"))
        self.stdout.write("-" * 40)
        logins = summary['login_attempts']
        success_rate = ((logins['total'] - logins['failed']) / logins['total'] * 100) if logins['total'] > 0 else 100
        
        self.stdout.write(f"Total Attempts: {logins['total']}")
        self.stdout.write(f"Failed Attempts: {logins['failed']}")
        self.stdout.write(f"Success Rate: {success_rate:.1f}%")
        self.stdout.write(f"Suspicious Attempts: {logins['suspicious']}")
        self.stdout.write(f"Unique IPs: {logins['unique_ips']}")
        self.stdout.write(f"Unique Usernames: {logins['unique_usernames']}")
        
        # Sessions Summary
        self.stdout.write(self.style.WARNING("\n🔄 SESSIONS SUMMARY"))
        self.stdout.write("-" * 40)
        sessions = summary['sessions']
        self.stdout.write(f"Active Sessions: {sessions['active']}")
        self.stdout.write(f"Suspicious Sessions: {sessions['suspicious']}")
        self.stdout.write(f"Long-Running Sessions: {sessions['long_running']}")
        
        # Threat Intelligence
        threats = summary['top_threats']
        if threats['ips']:
            self.stdout.write(self.style.ERROR("\n⚠️  TOP THREAT IPs"))
            self.stdout.write("-" * 40)
            for threat in threats['ips'][:5]:
                self.stdout.write(f"  🚨 {threat['ip_address']}: {threat['count']} failed attempts")
        
        if threats['usernames']:
            self.stdout.write(self.style.ERROR("\n👤 TOP TARGETED USERNAMES"))
            self.stdout.write("-" * 40)
            for threat in threats['usernames'][:5]:
                self.stdout.write(f"  🎯 {threat['username']}: {threat['count']} attempts")
        
        # Detailed views if requested
        if options['show_events']:
            self.show_recent_events(hours)
        
        if options['show_attempts']:
            self.show_recent_attempts(hours)
        
        if options['show_sessions']:
            self.show_active_sessions()
        
        # Security recommendations
        self.show_recommendations(summary)
    
    def show_recent_events(self, hours):
        """Show recent security events"""
        self.stdout.write(self.style.WARNING(f"\n📋 RECENT SECURITY EVENTS (Last {hours}h)"))
        self.stdout.write("-" * 80)
        
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        events = SecurityEvent.objects.filter(timestamp__gte=cutoff).order_by('-timestamp')[:20]
        
        for event in events:
            timestamp = event.timestamp.strftime('%m/%d %H:%M')
            user = event.user.username if event.user else event.username_attempted or 'Unknown'
            severity_icon = self.get_severity_icon(event.severity)
            
            self.stdout.write(f"{timestamp} {severity_icon} {event.get_event_type_display()}")
            self.stdout.write(f"         User: {user} | IP: {event.ip_address}")
            self.stdout.write(f"         {event.description}")
            if event.reason:
                self.stdout.write(f"         Reason: {event.reason}")
            self.stdout.write("")
    
    def show_recent_attempts(self, hours):
        """Show recent login attempts"""
        self.stdout.write(self.style.WARNING(f"\n🔑 RECENT LOGIN ATTEMPTS (Last {hours}h)"))
        self.stdout.write("-" * 80)
        
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        attempts = LoginAttempt.objects.filter(timestamp__gte=cutoff).order_by('-timestamp')[:20]
        
        for attempt in attempts:
            timestamp = attempt.timestamp.strftime('%m/%d %H:%M')
            status_icon = self.get_status_icon(attempt.status)
            suspicious = " 🚨" if attempt.is_suspicious else ""
            
            self.stdout.write(f"{timestamp} {status_icon} {attempt.username}")
            self.stdout.write(f"         Status: {attempt.get_status_display()}{suspicious}")
            self.stdout.write(f"         IP: {attempt.ip_address}")
            if attempt.failure_reason:
                self.stdout.write(f"         Reason: {attempt.failure_reason}")
            self.stdout.write("")
    
    def show_active_sessions(self):
        """Show active sessions"""
        self.stdout.write(self.style.WARNING("\n💻 ACTIVE SESSIONS"))
        self.stdout.write("-" * 80)
        
        sessions = UserSession.objects.filter(is_active=True).order_by('-last_activity')[:20]
        
        for session in sessions:
            last_activity = session.last_activity.strftime('%m/%d %H:%M')
            duration = session.duration
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            
            suspicious = " 🚨" if session.is_suspicious else ""
            long_running = " ⏰" if session.is_long_running else ""
            
            self.stdout.write(f"{session.user.username}{suspicious}{long_running}")
            self.stdout.write(f"         Last Activity: {last_activity}")
            self.stdout.write(f"         Duration: {hours}h {minutes}m")
            self.stdout.write(f"         IP: {session.ip_address}")
            if session.country:
                self.stdout.write(f"         Location: {session.country}")
            self.stdout.write("")
    
    def show_recommendations(self, summary):
        """Show security recommendations based on current state"""
        self.stdout.write(self.style.WARNING("\n💡 SECURITY RECOMMENDATIONS"))
        self.stdout.write("-" * 80)
        
        recommendations = []
        
        # Check for critical issues
        if summary['security_events']['critical_unresolved'] > 0:
            recommendations.append("🔴 URGENT: Investigate unresolved critical security events")
        
        # Check for high failure rates
        login_total = summary['login_attempts']['total']
        login_failed = summary['login_attempts']['failed']
        if login_total > 0:
            failure_rate = (login_failed / login_total) * 100
            if failure_rate > 50:
                recommendations.append(f"🔴 HIGH: Login failure rate is {failure_rate:.1f}% - possible attack")
            elif failure_rate > 25:
                recommendations.append(f"🟡 MEDIUM: Login failure rate is {failure_rate:.1f}% - monitor closely")
        
        # Check for suspicious activity
        if summary['login_attempts']['suspicious'] > 5:
            recommendations.append("🟡 MEDIUM: High number of suspicious login attempts detected")
        
        # Check for long-running sessions
        if summary['sessions']['long_running'] > 0:
            recommendations.append("🟡 MEDIUM: Long-running sessions detected - review for security")
        
        # Check for multiple IPs
        if summary['login_attempts']['unique_ips'] > 10:
            recommendations.append("🟡 MEDIUM: High number of unique IPs - possible distributed attack")
        
        if not recommendations:
            recommendations.append("✅ GREEN: No immediate security concerns detected")
        
        for rec in recommendations:
            self.stdout.write(f"  {rec}")
        
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 80))
    
    def get_severity_icon(self, severity):
        """Get icon for severity level"""
        icons = {
            'LOW': '🟢',
            'MEDIUM': '🟡',
            'HIGH': '🔴',
            'CRITICAL': '💀'
        }
        return icons.get(severity, '⚪')
    
    def get_status_icon(self, status):
        """Get icon for login status"""
        icons = {
            'SUCCESS': '✅',
            'FAILED': '❌',
            'BLOCKED': '🚫',
            'LOCKED': '🔒'
        }
        return icons.get(status, '❓')
