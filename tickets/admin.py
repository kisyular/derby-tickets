from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django import forms
from .models import Ticket, UserProfile

# Custom form for UserProfile inline
class UserProfileInlineForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['role']

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
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            # Only show admin users in the assigned_to dropdown
            kwargs["queryset"] = User.objects.filter(profile__role='admin').select_related('profile')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    form = UserProfileInlineForm
    list_display = ['user', 'role', 'user_email', 'user_first_name', 'user_last_name']
    list_filter = ['role']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    list_editable = ['role']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def user_first_name(self, obj):
        return obj.user.first_name
    user_first_name.short_description = 'First Name'
    
    def user_last_name(self, obj):
        return obj.user.last_name
    user_last_name.short_description = 'Last Name'

# Custom User Admin with UserProfile inline
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    form = UserProfileInlineForm
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ['role']
    max_num = 1
    min_num = 0  # Allow creation without requiring profile
    extra = 1

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    
    def save_model(self, request, obj, form, change):
        """Override save_model to handle UserProfile creation safely"""
        super().save_model(request, obj, form, change)
        
        # Ensure UserProfile exists after saving the user
        if not hasattr(obj, 'profile'):
            role = 'admin' if (obj.is_superuser or obj.is_staff) else 'user'
            UserProfile.objects.get_or_create(user=obj, defaults={'role': role})
    
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
