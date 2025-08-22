"""
Database models for comprehensive security audit trail.
Stores all security events, login attempts, and user actions in the database.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import json


class SecurityEvent(models.Model):
    """
    Comprehensive security event logging in database.
    Complements file-based logging with searchable, queryable data.
    """
    
    EVENT_TYPES = [
        ('LOGIN_SUCCESS', 'Successful Login'),
        ('LOGIN_FAILED', 'Failed Login'),
        ('LOGIN_BLOCKED', 'Blocked Login Attempt'),
        ('ACCOUNT_LOCKED', 'Account Locked'),
        ('UNAUTHORIZED_DOMAIN', 'Unauthorized Domain'),
        ('SUSPICIOUS_ACTIVITY', 'Suspicious Activity'),
        ('PASSWORD_CHANGED', 'Password Changed'),
        ('ACCOUNT_CREATED', 'Account Created'),
        ('ACCOUNT_DISABLED', 'Account Disabled'),
        ('PRIVILEGE_ESCALATION', 'Privilege Change'),
        ('DATA_ACCESS', 'Data Access'),
        ('SYSTEM_ACCESS', 'System Access'),
        ('API_ACCESS', 'API Access'),
        ('BRUTE_FORCE', 'Brute Force Attack'),
        ('SESSION_HIJACK', 'Session Hijacking'),
        ('OTHER', 'Other Security Event'),
    ]
    
    SEVERITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Event identification
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='MEDIUM', db_index=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # User information
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    username_attempted = models.CharField(max_length=150, blank=True, db_index=True)  # For failed attempts
    
    # Request information
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField(blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    
    # Event details
    description = models.TextField()
    success = models.BooleanField(default=False, db_index=True)
    reason = models.CharField(max_length=255, blank=True)  # Failure reason
    
    # Additional context (JSON field for flexible data storage)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Tracking fields
    resolved = models.BooleanField(default=False, db_index=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_events')
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Custom manager
    objects = models.Manager()  # Default manager
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['severity', 'resolved']),
        ]
        verbose_name = 'Security Event'
        verbose_name_plural = 'Security Events'
    
    def __str__(self):
        user_str = self.user.username if self.user else self.username_attempted or 'Anonymous'
        return f"{self.get_event_type_display()} - {user_str} ({self.timestamp})"
    
    def clean(self):
        if not self.user and not self.username_attempted:
            raise ValidationError('Either user or username_attempted must be provided')
    
    @property
    def is_critical(self):
        return self.severity == 'CRITICAL'
    
    @property
    def is_recent(self):
        """Check if event occurred in the last 24 hours"""
        return (timezone.now() - self.timestamp).days < 1
    
    @classmethod
    def recent_events(cls, hours=24):
        """Get events from the last N hours"""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return cls.objects.filter(timestamp__gte=cutoff)
    
    @classmethod
    def critical_events(cls):
        """Get unresolved critical events"""
        return cls.objects.filter(severity='CRITICAL', resolved=False)
    
    @classmethod
    def failed_logins(cls, hours=24):
        """Get failed login attempts from the last N hours"""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return cls.objects.filter(
            event_type='LOGIN_FAILED',
            timestamp__gte=cutoff
        )
    
    @classmethod
    def by_user(cls, user):
        """Get all events for a specific user"""
        return cls.objects.filter(
            models.Q(user=user) | models.Q(username_attempted=user.username)
        )


class LoginAttempt(models.Model):
    """
    Detailed login attempt tracking for analytics and security monitoring.
    """
    
    STATUS_CHOICES = [
        ('SUCCESS', 'Successful'),
        ('FAILED', 'Failed'),
        ('BLOCKED', 'Blocked'),
        ('LOCKED', 'Account Locked'),
    ]
    
    # Attempt details
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    username = models.CharField(max_length=150, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, db_index=True)
    
    # Technical details
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField(blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    
    # Security context
    is_suspicious = models.BooleanField(default=False, db_index=True)
    lockout_triggered = models.BooleanField(default=False)
    attempt_count = models.PositiveIntegerField(default=1)  # Current attempt in sequence
    
    # Geographic/Network info (optional)
    country = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    isp = models.CharField(max_length=200, blank=True)
    
    # Reference to user (if successful or if user exists)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Custom manager
    objects = models.Manager()  # Default manager
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['username', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['status', 'timestamp']),
            models.Index(fields=['is_suspicious', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.username} - {self.get_status_display()} ({self.timestamp})"
    
    @property
    def is_failed(self):
        return self.status in ['FAILED', 'BLOCKED', 'LOCKED']
    
    @classmethod
    def failed_attempts(cls, username=None, ip_address=None, hours=24):
        """Get failed attempts by username or IP in the last N hours"""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        queryset = cls.objects.filter(
            status__in=['FAILED', 'BLOCKED', 'LOCKED'],
            timestamp__gte=cutoff
        )
        
        if username:
            queryset = queryset.filter(username=username)
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        
        return queryset
    
    @classmethod
    def suspicious_attempts(cls, hours=24):
        """Get suspicious login attempts from the last N hours"""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return cls.objects.filter(is_suspicious=True, timestamp__gte=cutoff)


class UserSession(models.Model):
    """
    Track user sessions for security monitoring and analytics.
    """
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    
    # Session lifecycle
    created_at = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Security details
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    login_method = models.CharField(max_length=50, default='password')  # password, 2fa, sso, etc.
    
    # Geographic info
    country = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Security flags
    is_suspicious = models.BooleanField(default=False)
    forced_logout = models.BooleanField(default=False)  # Admin forced logout
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['last_activity', 'is_active']),
            models.Index(fields=['is_suspicious']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at}"
    
    @property
    def duration(self):
        """Calculate session duration"""
        end_time = self.ended_at or timezone.now()
        return end_time - self.created_at
    
    @property
    def is_long_running(self):
        """Check if session is unusually long (>8 hours)"""
        return self.duration.total_seconds() > 28800  # 8 hours


class AuditLog(models.Model):
    """
    Comprehensive audit trail for all user actions and system events.
    """
    
    ACTION_TYPES = [
        ('CREATE', 'Created'),
        ('READ', 'Viewed'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('LOGIN', 'Logged In'),
        ('LOGOUT', 'Logged Out'),
        ('PERMISSION_CHANGE', 'Permission Changed'),
        ('CONFIGURATION_CHANGE', 'Configuration Changed'),
        ('SYSTEM_ACCESS', 'System Access'),
        ('DATA_EXPORT', 'Data Export'),
        ('OTHER', 'Other Action'),
    ]
    
    # Event identification
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    action = models.CharField(max_length=50, choices=ACTION_TYPES, db_index=True)
    
    # User and target information
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_targets')
    
    # Object information (generic relations could be added)
    object_type = models.CharField(max_length=100, blank=True)  # Model name
    object_id = models.CharField(max_length=100, blank=True)    # Object ID
    object_repr = models.CharField(max_length=255, blank=True)  # String representation
    
    # Change details
    changes = models.JSONField(default=dict, blank=True)  # Before/after values
    description = models.TextField()
    
    # Request context
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    
    # Risk assessment
    risk_level = models.CharField(
        max_length=10,
        choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')],
        default='LOW',
        db_index=True
    )
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['risk_level', 'timestamp']),
        ]
    
    def __str__(self):
        user_str = self.user.username if self.user else 'System'
        return f"{user_str} {self.get_action_display()} {self.object_type} ({self.timestamp})"


# Manager classes for common queries
class SecurityEventManager(models.Manager):
    def recent_events(self, hours=24):
        """Get events from the last N hours"""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(timestamp__gte=cutoff)
    
    def critical_events(self):
        """Get unresolved critical events"""
        return self.filter(severity='CRITICAL', resolved=False)
    
    def failed_logins(self, hours=24):
        """Get failed login attempts from the last N hours"""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(
            event_type='LOGIN_FAILED',
            timestamp__gte=cutoff
        )
    
    def by_user(self, user):
        """Get all events for a specific user"""
        return self.filter(
            models.Q(user=user) | models.Q(username_attempted=user.username)
        )
