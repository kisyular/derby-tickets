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

class Category(models.Model):
    """Category model for ticket categorization with legacy timestamp support"""
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(null=True, blank=True, help_text="When category was created")
    updated_at = models.DateTimeField(null=True, blank=True, help_text="When category was last updated")

    def save(self, *args, **kwargs):
        """Override save to handle auto timestamps based on use_auto_now flag"""
        use_auto_now = kwargs.pop('use_auto_now', True)
        
        if use_auto_now:
            # For new categories created through web interface - set current time
            from django.utils import timezone
            now = timezone.now()
            if not self.created_at:
                self.created_at = now
            self.updated_at = now
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

class Ticket(models.Model):
    """Simplified ticket model using only Django User"""
    ticket_number = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="Sequential ticket number from external system")
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, help_text="Ticket category")
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
            ('Urgent', 'Urgent'),
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
        """Override save to handle auto timestamps, user profile info, and ticket number generation"""
        use_auto_now = kwargs.pop('use_auto_now', True)
        
        if use_auto_now and not self.created_at:
            # For new tickets created through web interface - set current time
            from django.utils import timezone
            self.created_at = timezone.now()
        
        # Auto-generate ticket number for new tickets if not set
        if not self.ticket_number:
            self.ticket_number = self._generate_ticket_number()
        
        # Auto-populate location and department from user profile if not set
        if self.created_by and hasattr(self.created_by, 'userprofile'):
            profile = self.created_by.userprofile
            if not self.location and profile.location:
                self.location = profile.location
            if not self.department and profile.department:
                self.department = profile.department
        
        super().save(*args, **kwargs)
    
    def _generate_ticket_number(self):
        """Generate a unique ticket number."""
        # Get the highest existing ticket number
        last_ticket = Ticket.objects.filter(
            ticket_number__isnull=False,
            ticket_number__regex=r'^\d+$'  # Only numeric ticket numbers
        ).extra(
            select={'ticket_num_int': 'CAST(ticket_number AS INTEGER)'}
        ).order_by('-ticket_num_int').first()
        
        if last_ticket and last_ticket.ticket_number.isdigit():
            next_number = int(last_ticket.ticket_number) + 1
        else:
            # If no existing numeric tickets, start from a reasonable number
            # Check if we have any imported tickets to continue the sequence
            all_tickets = Ticket.objects.filter(ticket_number__isnull=False)
            if all_tickets.exists():
                # Find the highest numeric ticket number
                max_num = 0
                for ticket in all_tickets:
                    try:
                        num = int(ticket.ticket_number)
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        continue
                next_number = max_num + 1 if max_num > 0 else 1
            else:
                next_number = 1
        
        return str(next_number)

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
        ordering = ['-created_at']  # Newest first for better UX
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



