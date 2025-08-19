from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Ticket, UserProfile, Comment, Category

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

# Inline for Comments to be displayed within Ticket admin
class CommentInline(admin.TabularInline):
    model = Comment
    extra = 1
    fields = ('author', 'content', 'is_internal', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ['created_at']

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
