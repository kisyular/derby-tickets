from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# SIMPLIFIED APPROACH: Use Django User model + minimal profile extension

class UserProfile(models.Model):
    """Single profile model for additional user information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    
    # Additional fields that Django User doesn't have
    location = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Role is already handled by User.is_staff and User.is_superuser
    # first_name, last_name, email are already in User model
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Profile"
    
    @property
    def role(self):
        """Get user role based on Django permissions"""
        if self.user.is_superuser:
            return 'superuser'
        elif self.user.is_staff:
            return 'admin'
        else:
            return 'user'
    
    @property
    def full_name(self):
        return self.user.get_full_name()
    
    @property
    def email(self):
        return self.user.email

class Ticket(models.Model):
    """Simplified ticket model using only Django User"""
    ticket_number = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="Sequential ticket number from external system")
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100, blank=True, help_text="Ticket category")
    location = models.CharField(max_length=100, blank=True, help_text="User's location when ticket was created")
    department = models.CharField(max_length=100, blank=True, help_text="User's department when ticket was created")

    # Direct relationships to User model
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_tickets')
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        limit_choices_to={'is_staff': True}  # Only staff can be assigned tickets
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('Open', 'Open'),
            ('In Progress', 'In Progress'),
            ('Closed', 'Closed'),
        ],
        default='Open'
    )
    priority = models.CharField(
        max_length=20,
        choices=[
            ('Low', 'Low'),
            ('Medium', 'Medium'),
            ('High', 'High'),
        ],
        default='Medium'
    )

    # Response time tracking fields
    first_response_at = models.DateTimeField(null=True, blank=True, help_text="When first response was provided")
    status_changed_at = models.DateTimeField(null=True, blank=True, help_text="When status was last changed")
    last_user_response_at = models.DateTimeField(null=True, blank=True, help_text="When user last responded")
    closed_on = models.DateTimeField(null=True, blank=True, help_text="When ticket was closed")
    due_on = models.DateTimeField(null=True, blank=True, help_text="Due date for the ticket")
    
    # Date fields
    created_at = models.DateTimeField(null=True, blank=True, help_text="When ticket was created")
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Override save to handle auto timestamps and user profile info"""
        use_auto_now = kwargs.pop('use_auto_now', True)
        
        if use_auto_now and not self.created_at:
            # For new tickets created through web interface - set current time
            from django.utils import timezone
            self.created_at = timezone.now()
        
        # Auto-populate location and department from user profile if not set
        if self.created_by and hasattr(self.created_by, 'userprofile'):
            profile = self.created_by.userprofile
            if not self.location and profile.location:
                self.location = profile.location
            if not self.department and profile.department:
                self.department = profile.department
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @classmethod
    def get_assignable_users(cls):
        """Return users who can be assigned to tickets"""
        return User.objects.filter(is_staff=True)

    @property
    def creator_profile(self):
        """Get the profile of the creator"""
        return getattr(self.created_by, 'userprofile', None)

    @property
    def assignee_profile(self):
        """Get the profile of the assignee"""
        if self.assigned_to:
            return getattr(self.assigned_to, 'userprofile', None)
        return None

    class Meta:
        ordering = ['-created_at']

class Comment(models.Model):
    """Comments on tickets for communication and updates"""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For internal notes vs public comments
    is_internal = models.BooleanField(default=False, help_text="Internal notes visible only to staff")
    
    class Meta:
        ordering = ['created_at']  # Oldest first for conversation flow
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
    
    def __str__(self):
        return f"Comment by {self.author.username} on Ticket #{self.ticket.id}"
    
    @property
    def author_profile(self):
        """Get the profile of the comment author"""
        return getattr(self.author, 'userprofile', None)

# Signal to automatically create UserProfile when User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when a User is created"""
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Ensure profile exists when User is saved"""
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()
    else:
        UserProfile.objects.create(user=instance)



