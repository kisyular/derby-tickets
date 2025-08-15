from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.

class EndUser(models.Model):
    """Table for regular users"""
    end_user_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='end_user_profile')  # Link to Django User
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, default='user')
    location = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    domain = models.CharField(max_length=50, default='derbyfab.com')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'end_users'
        verbose_name = 'End User'
        verbose_name_plural = 'End Users'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Admin(models.Model):
    """Table for admin users"""
    admin_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')  # Link to Django User
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email_address = models.EmailField(unique=True)
    role = models.CharField(max_length=20, default='admin')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'admins'
        verbose_name = 'Admin'
        verbose_name_plural = 'Admins'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email_address})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Ticket(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tickets')  # Back to User model
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')  # Remove limit_choices_to for now
    status = models.CharField(
        max_length=20,
        choices=[
            ('open', 'Open'),
            ('in_progress', 'In Progress'),
            ('closed', 'Closed'),
        ],
        default='open'
    )
    priority = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ],
        default='medium'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    @classmethod
    def get_assignable_users(cls):
        """Return admin users who can be assigned to tickets"""
        return User.objects.filter(is_staff=True)  # Only staff users can be assigned
    
    @property
    def creator_profile(self):
        """Get the EndUser profile of the creator"""
        if hasattr(self.created_by, 'end_user_profile'):
            return self.created_by.end_user_profile
        return None
    
    @property
    def assignee_profile(self):
        """Get the Admin profile of the assignee"""
        if self.assigned_to and hasattr(self.assigned_to, 'admin_profile'):
            return self.assigned_to.admin_profile
        return None
    
    class Meta:
        ordering = ['-created_at']

# Signals to automatically create EndUser/Admin profiles when Django User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create EndUser or Admin profile when a User is created"""
    if created:
        # Create Admin profile for staff/superuser, EndUser profile for regular users
        if instance.is_staff or instance.is_superuser:
            Admin.objects.get_or_create(
                user=instance,
                defaults={
                    'first_name': instance.first_name or '',
                    'last_name': instance.last_name or '',
                    'email_address': instance.email or '',
                    'role': 'admin'
                }
            )
        else:
            EndUser.objects.get_or_create(
                user=instance,
                defaults={
                    'first_name': instance.first_name or '',
                    'last_name': instance.last_name or '',
                    'email': instance.email or '',
                    'role': 'user'
                }
            )

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Update profile when User is saved"""
    try:
        if hasattr(instance, 'admin_profile'):
            # Update admin profile
            profile = instance.admin_profile
            profile.first_name = instance.first_name or profile.first_name
            profile.last_name = instance.last_name or profile.last_name
            profile.email_address = instance.email or profile.email_address
            profile.save()
        elif hasattr(instance, 'end_user_profile'):
            # Update end user profile
            profile = instance.end_user_profile
            profile.first_name = instance.first_name or profile.first_name
            profile.last_name = instance.last_name or profile.last_name
            profile.email = instance.email or profile.email
            profile.save()
    except (Admin.DoesNotExist, EndUser.DoesNotExist):
        pass  # Profile doesn't exist yet, will be created by create_user_profile


