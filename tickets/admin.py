from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import Ticket, UserProfile, Comment, Category
from .audit_models import SecurityEvent, LoginAttempt, UserSession, AuditLog

# Register your models here.

# Inline for UserProfile to be edited within User admin
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile Information'
    fields = ('location', 'department', 'phone')

# Extend Django's User admin to include UserProfile inline
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    
    # Add role information to the list display (without duplicating is_staff)
    list_display = BaseUserAdmin.list_display + ('get_role', 'get_location', 'get_department')
    # Keep the existing list_filter from BaseUserAdmin
    
    def get_role(self, obj):
        """Display user role"""
        if hasattr(obj, 'userprofile'):
            return obj.userprofile.role
        return 'No Profile'
    get_role.short_description = 'Role'
    
    def get_location(self, obj):
        """Display user location"""
        if hasattr(obj, 'userprofile'):
            return obj.userprofile.location or '-'
        return '-'
    get_location.short_description = 'Location'
    
    def get_department(self, obj):
        """Display user department"""
        if hasattr(obj, 'userprofile'):
            return obj.userprofile.department or '-'
        return '-'
    get_department.short_description = 'Department'
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of system users"""
        if obj and obj.username in ['default_user', 'admin']:
            return False
        return super().has_delete_permission(request, obj)
    
    def get_readonly_fields(self, request, obj=None):
        """Make system users' usernames readonly"""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.username in ['default_user', 'admin']:
            if 'username' not in readonly:
                readonly.append('username')
        return readonly
    
    def delete_model(self, request, obj):
        """Custom delete method to ensure signals are triggered"""
        # This ensures the pre_delete signal is fired for individual deletions
        obj.delete()
    
    def delete_queryset(self, request, queryset):
        """Custom bulk delete method to ensure signals are triggered for each user"""
        # Django admin bulk delete bypasses signals, so we delete individually
        for user in queryset:
            # Don't allow deletion of system users
            if user.username not in ['default_user', 'admin']:
                user.delete()  # This will trigger the signal for each user

# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Simplified UserProfile admin (optional - you can still edit profiles separately)
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'location', 'department', 'phone', 'created_at']
    list_filter = ['location', 'department', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'user__email', 'location', 'department']
    list_editable = ['location', 'department', 'phone']
    ordering = ['-created_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Additional Information', {
            'fields': ('location', 'department', 'phone')
        }),
    )

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'title', 'created_by', 'assigned_to', 'status', 'priority', 'category', 'location', 'department', 'created_at', 'closed_on', 'due_on']
    list_filter = ['status', 'priority', 'category', 'location', 'department', 'created_at', 'closed_on', 'created_by', 'assigned_to']
    search_fields = ['ticket_number', 'title', 'description', 'category', 'created_by__username', 'created_by__first_name', 'created_by__last_name', 'created_by__email', 
                     'assigned_to__username', 'assigned_to__first_name', 'assigned_to__last_name', 'assigned_to__email']
    list_editable = ['assigned_to', 'status', 'priority', 'category', 'created_by']
    ordering = ['-created_at']
    list_per_page = 25  # Default number of items per page
    list_max_show_all = 500  # Maximum items to show when "Show all" is clicked
    date_hierarchy = 'created_at'
    readonly_fields = ['ticket_number', 'updated_at', 'first_response_at', 'status_changed_at', 'last_user_response_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by', 'assigned_to')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            # Only show staff users (admins) in the assigned_to dropdown
            kwargs["queryset"] = User.objects.filter(is_staff=True)
        elif db_field.name == "created_by":
            # Show all users for created_by dropdown
            kwargs["queryset"] = User.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('title', 'description', 'category')
        }),
        ('Assignment', {
            'fields': ('created_by', 'assigned_to')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority')
        }),
        ('Location & Department', {
            'fields': ('location', 'department'),
            'description': 'Automatically populated from user profile when ticket is created'
        }),
        ('Ticket Details (Auto-generated)', {
            'fields': ('ticket_number',),
            'classes': ['collapse'],
            'description': 'Automatically generated when ticket is created'
        }),
        ('Dates', {
            'fields': ('created_at', 'closed_on', 'due_on')
        }),
        ('System Tracking (Read-only)', {
            'fields': ('updated_at', 'first_response_at', 'status_changed_at', 'last_user_response_at'),
            'classes': ['collapse'],
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Save model and track who made the changes for email notifications."""
        # Set the user who made the changes for email notifications
        obj._updated_by = request.user
        super().save_model(request, obj, form, change)

# Inline for Comments to be displayed within Ticket admin
class CommentInline(admin.TabularInline):
    model = Comment
    extra = 1
    fields = ('author', 'content', 'is_internal', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ['-created_at']  # Newest first

# Update TicketAdmin to include comments inline
class TicketAdminWithComments(TicketAdmin):
    inlines = [CommentInline]

# Comment Admin
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'author', 'content_preview', 'is_internal', 'created_at']
    list_filter = ['is_internal', 'created_at', 'author']
    search_fields = ['content', 'ticket__title', 'author__username']
    list_per_page = 25
    ordering = ['-created_at']
    
    def content_preview(self, obj):
        """Show a preview of the comment content"""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ticket', 'author')
    
    fieldsets = (
        ('Comment Information', {
            'fields': ('ticket', 'author', 'content')
        }),
        ('Settings', {
            'fields': ('is_internal',)
        }),
    )

# Re-register Ticket with comments
admin.site.unregister(Ticket)
admin.site.register(Ticket, TicketAdminWithComments)

# Category Admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Category Information', {
            'fields': ('name',)
        }),
        ('Timestamps (Read-only)', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse'],
        }),
    )


# =============================================================================
# SECURITY AUDIT ADMIN INTERFACES
# =============================================================================

@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    """Admin interface for security events with comprehensive filtering and search"""
    
    list_display = [
        'timestamp', 'event_type', 'severity', 'get_user_display', 
        'ip_address', 'success', 'resolved', 'get_description_preview'
    ]
    list_filter = [
        'event_type', 'severity', 'success', 'resolved', 'timestamp',
        ('user', admin.RelatedOnlyFieldListFilter)
    ]
    search_fields = [
        'description', 'username_attempted', 'ip_address', 
        'user__username', 'user__email', 'reason'
    ]
    readonly_fields = [
        'timestamp', 'event_type', 'user', 'username_attempted',
        'ip_address', 'user_agent', 'session_key', 'description',
        'success', 'reason', 'metadata'
    ]
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Event Information', {
            'fields': ('timestamp', 'event_type', 'severity', 'success')
        }),
        ('User Information', {
            'fields': ('user', 'username_attempted')
        }),
        ('Request Details', {
            'fields': ('ip_address', 'user_agent', 'session_key')
        }),
        ('Event Details', {
            'fields': ('description', 'reason', 'metadata')
        }),
        ('Resolution', {
            'fields': ('resolved', 'resolved_by', 'resolved_at', 'notes'),
            'classes': ['collapse']
        })
    )
    
    actions = ['mark_resolved', 'mark_unresolved']
    
    def get_user_display(self, obj):
        if obj.user:
            return obj.user.username
        return obj.username_attempted or 'Anonymous'
    get_user_display.short_description = 'User'
    
    def get_description_preview(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    get_description_preview.short_description = 'Description'
    
    def mark_resolved(self, request, queryset):
        queryset.update(resolved=True, resolved_by=request.user, resolved_at=timezone.now())
        self.message_user(request, f"Marked {queryset.count()} events as resolved.")
    mark_resolved.short_description = "Mark selected events as resolved"
    
    def mark_unresolved(self, request, queryset):
        queryset.update(resolved=False, resolved_by=None, resolved_at=None)
        self.message_user(request, f"Marked {queryset.count()} events as unresolved.")
    mark_unresolved.short_description = "Mark selected events as unresolved"


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Admin interface for login attempts with security focus"""
    
    list_display = [
        'timestamp', 'username', 'status', 'ip_address', 
        'is_suspicious', 'attempt_count', 'get_user_display'
    ]
    list_filter = [
        'status', 'is_suspicious', 'lockout_triggered', 'timestamp',
        ('user', admin.RelatedOnlyFieldListFilter)
    ]
    search_fields = [
        'username', 'ip_address', 'user_agent', 'failure_reason',
        'user__username', 'country', 'region'
    ]
    readonly_fields = [
        'timestamp', 'username', 'status', 'ip_address', 'user_agent',
        'failure_reason', 'is_suspicious', 'lockout_triggered',
        'attempt_count', 'user', 'country', 'region', 'isp'
    ]
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Attempt Information', {
            'fields': ('timestamp', 'username', 'status', 'user')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent', 'failure_reason')
        }),
        ('Security Analysis', {
            'fields': ('is_suspicious', 'lockout_triggered', 'attempt_count')
        }),
        ('Geographic Information', {
            'fields': ('country', 'region', 'isp'),
            'classes': ['collapse']
        })
    )
    
    def get_user_display(self, obj):
        return obj.user.username if obj.user else 'No Account'
    get_user_display.short_description = 'Account'


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Admin interface for user sessions"""
    
    list_display = [
        'user', 'created_at', 'last_activity', 'is_active',
        'get_duration', 'ip_address', 'is_suspicious'
    ]
    list_filter = [
        'is_active', 'is_suspicious', 'forced_logout', 'login_method',
        'created_at', 'last_activity'
    ]
    search_fields = [
        'user__username', 'ip_address', 'user_agent', 
        'session_key', 'country', 'region', 'city'
    ]
    readonly_fields = [
        'user', 'session_key', 'created_at', 'last_activity', 'ended_at',
        'ip_address', 'user_agent', 'login_method', 'country', 'region', 'city'
    ]
    ordering = ['-last_activity']
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'session_key', 'login_method')
        }),
        ('Timeline', {
            'fields': ('created_at', 'last_activity', 'ended_at', 'is_active')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Security Flags', {
            'fields': ('is_suspicious', 'forced_logout')
        }),
        ('Geographic Information', {
            'fields': ('country', 'region', 'city'),
            'classes': ['collapse']
        })
    )
    
    actions = ['force_logout_sessions']
    
    def get_duration(self, obj):
        duration = obj.duration
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m"
    get_duration.short_description = 'Duration'
    
    def force_logout_sessions(self, request, queryset):
        active_sessions = queryset.filter(is_active=True)
        count = active_sessions.update(
            is_active=False,
            ended_at=timezone.now(),
            forced_logout=True
        )
        self.message_user(request, f"Forced logout of {count} active sessions.")
    force_logout_sessions.short_description = "Force logout selected sessions"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for audit logs"""
    
    list_display = [
        'timestamp', 'action', 'user', 'get_object_display',
        'risk_level', 'ip_address', 'get_description_preview'
    ]
    list_filter = [
        'action', 'risk_level', 'timestamp', 'object_type',
        ('user', admin.RelatedOnlyFieldListFilter),
        ('target_user', admin.RelatedOnlyFieldListFilter)
    ]
    search_fields = [
        'description', 'object_repr', 'user__username', 
        'target_user__username', 'ip_address', 'request_path'
    ]
    readonly_fields = [
        'timestamp', 'action', 'user', 'target_user', 'object_type',
        'object_id', 'object_repr', 'changes', 'description',
        'ip_address', 'user_agent', 'request_path', 'risk_level'
    ]
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Action Information', {
            'fields': ('timestamp', 'action', 'risk_level')
        }),
        ('User Information', {
            'fields': ('user', 'target_user')
        }),
        ('Object Information', {
            'fields': ('object_type', 'object_id', 'object_repr')
        }),
        ('Details', {
            'fields': ('description', 'changes')
        }),
        ('Request Context', {
            'fields': ('ip_address', 'user_agent', 'request_path'),
            'classes': ['collapse']
        })
    )
    
    def get_object_display(self, obj):
        if obj.object_type and obj.object_repr:
            return f"{obj.object_type}: {obj.object_repr[:30]}"
        return "-"
    get_object_display.short_description = 'Object'
    
    def get_description_preview(self, obj):
        return obj.description[:40] + '...' if len(obj.description) > 40 else obj.description
    get_description_preview.short_description = 'Description'
