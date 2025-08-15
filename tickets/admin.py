from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Ticket

# Register your models here.

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'created_by', 'assigned_to', 'status', 'priority', 'created_at', 'updated_at']
    list_filter = ['status', 'priority', 'created_at', 'created_by', 'assigned_to']
    search_fields = ['title', 'description', 'created_by__username', 'assigned_to__username']
    list_editable = ['status', 'priority', 'assigned_to']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by', 'assigned_to')

# Customize the User admin to make it easier to create users
class CustomUserAdmin(UserAdmin):
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj:  # Adding new user
            return (
                (None, {'fields': ('username', 'password1', 'password2')}),
                ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
                ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
            )
        return fieldsets

# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
