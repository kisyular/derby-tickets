from django.contrib import admin
from django.contrib.auth.models import User
from .models import Ticket, EndUser, Admin

# Register your models here.

@admin.register(EndUser)
class EndUserAdmin(admin.ModelAdmin):
    list_display = ['end_user_id', 'first_name', 'last_name', 'email', 'role', 'location', 'department', 'domain', 'created_at']
    list_filter = ['role', 'location', 'department', 'domain', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'location', 'department']
    list_editable = ['role', 'location', 'department']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Work Information', {
            'fields': ('role', 'location', 'department', 'domain')
        }),
    )

@admin.register(Admin)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['admin_id', 'first_name', 'last_name', 'email_address', 'role', 'full_name', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['first_name', 'last_name', 'email_address']
    list_editable = ['role']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email_address')
        }),
        ('Role Information', {
            'fields': ('role',)
        }),
    )

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'created_by', 'assigned_to', 'status', 'priority', 'created_at', 'updated_at']
    list_filter = ['status', 'priority', 'created_at', 'created_by', 'assigned_to']
    search_fields = ['title', 'description', 'created_by__username', 'created_by__first_name', 'created_by__last_name', 'created_by__email', 
                     'assigned_to__username', 'assigned_to__first_name', 'assigned_to__last_name', 'assigned_to__email']
    list_editable = ['created_by', 'assigned_to', 'status', 'priority']
    ordering = ['-created_at']
    
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
            'fields': ('title', 'description')
        }),
        ('Assignment', {
            'fields': ('created_by', 'assigned_to')
        }),
        ('Status', {
            'fields': ('status', 'priority')
        }),
    )
