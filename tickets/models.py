from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# Import audit models for comprehensive security tracking
from .audit_models import SecurityEvent, LoginAttempt, UserSession, AuditLog

# SIMPLIFIED APPROACH: Use Django User model + minimal profile extension


class UserProfile(models.Model):
    """Single profile model for additional user information"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="userprofile"
    )

    # Additional fields that Django User doesn't have
    location = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Role is already handled by User.is_staff and User.is_superuser
    # first_name, last_name, email are already in User model

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.get_full_name()} - Profile"

    @property
    def role(self):
        """Get user role based on Django permissions"""
        if self.user.is_superuser:
            return "superuser"
        elif self.user.is_staff:
            return "admin"
        else:
            return "user"

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def email(self):
        return self.user.email


class Category(models.Model):
    """Category model for ticket categorization with legacy timestamp support"""

    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(
        null=True, blank=True, help_text="When category was created"
    )
    updated_at = models.DateTimeField(
        null=True, blank=True, help_text="When category was last updated"
    )

    def save(self, *args, **kwargs):
        """Override save to handle auto timestamps based on use_auto_now flag"""
        use_auto_now = kwargs.pop("use_auto_now", True)

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
        ordering = ["name"]


class Ticket(models.Model):
    # CC fields
    cc_admins = models.ManyToManyField(
        User,
        blank=True,
        related_name="cc_admin_tickets",
        help_text="Additional staff/admins to CC on this ticket",
        limit_choices_to={"is_staff": True},
    )
    cc_non_admins = models.ManyToManyField(
        User,
        blank=True,
        related_name="cc_non_admin_tickets",
        help_text="Additional non-admin users to CC on this ticket",
        limit_choices_to={"is_staff": False},
    )
    """Simplified ticket model using only Django User"""
    ticket_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Sequential ticket number from external system",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Ticket category",
    )
    location = models.CharField(
        max_length=100, blank=True, help_text="User's location when ticket was created"
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="User's department when ticket was created",
    )

    # Direct relationships to User model
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_tickets"
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        limit_choices_to={"is_staff": True},  # Only staff can be assigned tickets
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("Open", "Open"),
            ("In Progress", "In Progress"),
            ("Closed", "Closed"),
        ],
        default="Open",
    )
    priority = models.CharField(
        max_length=20,
        choices=[
            ("Low", "Low"),
            ("Medium", "Medium"),
            ("High", "High"),
            ("Urgent", "Urgent"),
        ],
        default="Medium",
    )

    # Response time tracking fields
    first_response_at = models.DateTimeField(
        null=True, blank=True, help_text="When first response was provided"
    )
    status_changed_at = models.DateTimeField(
        null=True, blank=True, help_text="When status was last changed"
    )
    last_user_response_at = models.DateTimeField(
        null=True, blank=True, help_text="When user last responded"
    )
    closed_on = models.DateTimeField(
        null=True, blank=True, help_text="When ticket was closed"
    )
    due_on = models.DateTimeField(
        null=True, blank=True, help_text="Due date for the ticket"
    )

    # Date fields
    created_at = models.DateTimeField(
        null=True, blank=True, help_text="When ticket was created"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Override save to handle auto timestamps, user profile info, and ticket number generation"""
        use_auto_now = kwargs.pop("use_auto_now", True)

        if use_auto_now and not self.created_at:
            # For new tickets created through web interface - set current time
            from django.utils import timezone

            self.created_at = timezone.now()

        # Auto-generate ticket number for new tickets if not set
        if not self.ticket_number:
            self.ticket_number = self._generate_ticket_number()

        # Auto-populate location and department from user profile if not set
        if self.created_by and hasattr(self.created_by, "userprofile"):
            profile = self.created_by.userprofile
            if not self.location and profile.location:
                self.location = profile.location
            if not self.department and profile.department:
                self.department = profile.department

        super().save(*args, **kwargs)

    def _generate_ticket_number(self):
        """Generate a unique ticket number."""
        # Get all existing ticket numbers and find the highest numeric one
        all_tickets = Ticket.objects.filter(ticket_number__isnull=False).values_list(
            "ticket_number", flat=True
        )

        max_num = 0
        for ticket_number in all_tickets:
            try:
                # Try to convert to integer - only consider numeric ticket numbers
                num = int(str(ticket_number).strip())
                if num > max_num:
                    max_num = num
            except (ValueError, TypeError):
                # Skip non-numeric ticket numbers
                continue

        # Next number is max + 1, or 1 if no numeric tickets exist
        next_number = max_num + 1 if max_num > 0 else 1

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
        return getattr(self.created_by, "userprofile", None)

    @property
    def assignee_profile(self):
        """Get the profile of the assignee"""
        if self.assigned_to:
            return getattr(self.assigned_to, "userprofile", None)
        return None

    class Meta:
        ordering = ["-created_at"]


class Comment(models.Model):
    """Comments on tickets for communication and updates"""

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name="comments")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # For internal notes vs public comments
    is_internal = models.BooleanField(
        default=False, help_text="Internal notes visible only to staff"
    )

    class Meta:
        ordering = ["-created_at"]  # Newest first for better UX
        verbose_name = "Comment"
        verbose_name_plural = "Comments"

    def __str__(self):
        return f"Comment by {self.author.username} on Ticket #{self.ticket.id}"

    @property
    def author_profile(self):
        """Get the profile of the comment author"""
        return getattr(self.author, "userprofile", None)


# Signal to automatically create UserProfile when User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when a User is created"""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Ensure profile exists when User is saved"""
    if hasattr(instance, "userprofile"):
        instance.userprofile.save()
    else:
        UserProfile.objects.create(user=instance)


class APIToken(models.Model):
    """
    API tokens for external integrations and API access.
    """

    token = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=100, help_text="Descriptive name for this token")
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="api_tokens"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Optional: Add permissions or restrictions
    allowed_endpoints = models.TextField(
        blank=True,
        help_text="Comma-separated list of allowed endpoints. Leave blank for all endpoints.",
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Optional expiration date"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"

    def __str__(self):
        return f"{self.name} ({self.token[:8]}...)"

    def is_valid(self):
        """Check if token is valid and not expired"""
        if not self.is_active:
            return False

        if self.expires_at and self.expires_at < timezone.now():
            return False

        return True

    def update_last_used(self):
        """Update the last used timestamp"""
        from django.utils import timezone

        self.last_used = timezone.now()
        self.save(update_fields=["last_used"])


def ticket_attachment_upload_path(instance, filename):
    """
    Generate upload path for ticket attachments - stored in protected directory.
    Structure: protected/attachments/tickets/<ticket_id>/<filename>
    """
    import os
    from django.utils.text import get_valid_filename

    # Sanitize filename
    filename = get_valid_filename(filename)

    # Create path based on ticket ID - now in protected folder
    ticket_id = instance.ticket.id if instance.ticket.id else "tmp"
    return f"protected/attachments/tickets/{ticket_id}/{filename}"


class TicketAttachment(models.Model):
    """Model for ticket file attachments (images and PDFs)"""

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="attachments",
        help_text="The ticket this attachment belongs to",
    )

    file = models.FileField(
        upload_to=ticket_attachment_upload_path,
        help_text="Uploaded file (images: JPG, PNG, WebP; documents: PDF)",
    )

    original_filename = models.CharField(
        max_length=255, help_text="Original filename when uploaded"
    )

    file_type = models.CharField(
        max_length=20,
        choices=[
            ("IMAGE", "Image"),
            ("PDF", "PDF Document"),
        ],
        help_text="Type of uploaded file",
    )

    file_size = models.PositiveIntegerField(help_text="File size in bytes")

    uploaded_by = models.ForeignKey(
        User, on_delete=models.PROTECT, help_text="User who uploaded this attachment"
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True, help_text="When this attachment was uploaded"
    )

    description = models.CharField(
        max_length=200, blank=True, help_text="Optional description of the attachment"
    )

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Ticket Attachment"
        verbose_name_plural = "Ticket Attachments"

    def __str__(self):
        return f"{self.original_filename} - {self.ticket.title}"

    @property
    def is_image(self):
        """Check if attachment is an image"""
        return self.file_type == "IMAGE"

    @property
    def is_pdf(self):
        """Check if attachment is a PDF"""
        return self.file_type == "PDF"

    @property
    def file_size_mb(self):
        """Get file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)

    def get_secure_url(self):
        """Get the secure URL for this attachment"""
        from django.urls import reverse
        import os

        filename = os.path.basename(self.file.name)
        return reverse(
            "tickets:secure_file",
            kwargs={"ticket_id": self.ticket.id, "filename": filename},
        )

    def save(self, *args, **kwargs):
        """Override save to set file metadata"""
        if self.file:
            # Set original filename if not set
            if not self.original_filename:
                self.original_filename = self.file.name

            # Set file size
            if not self.file_size:
                self.file_size = self.file.size

            # Determine file type based on content type
            if not self.file_type:
                content_type = getattr(self.file.file, "content_type", "")
                if content_type.startswith("image/"):
                    self.file_type = "IMAGE"
                elif content_type == "application/pdf":
                    self.file_type = "PDF"

        super().save(*args, **kwargs)


# Signal to auto-generate token when creating APIToken through Django admin
@receiver(post_save, sender=APIToken)
def generate_api_token_on_create(sender, instance, created, **kwargs):
    """Auto-generate token when APIToken is created without one"""
    if created and not instance.token:
        from .api_auth import generate_api_token

        instance.token = generate_api_token()
        instance.save(update_fields=["token"])


@receiver(post_save, sender=Ticket)
def update_closed_on(sender, instance, created, **kwargs):
    """
    Update closed_on when status changes to 'Closed'.
    Clear closed_on if status changes to anything else.
    Works for both admin and web interface.
    """
    if instance.status == "Closed":
        if not instance.closed_on:
            instance.closed_on = timezone.now()
            instance.save(update_fields=["closed_on"])
    else:
        if instance.closed_on:
            instance.closed_on = None
            instance.save(update_fields=["closed_on"])


class ComputerInfo(models.Model):
    """
    Model for computer information from the Computers database.
    This is a read-only model that maps to the existing computer table.
    """

    serial_number = models.CharField(max_length=100, primary_key=True)
    hostname = models.CharField(max_length=100, db_column="hostName")
    wan_ip = models.GenericIPAddressField(null=True, blank=True)
    isp = models.CharField(max_length=200, blank=True)
    wan_geo_loc = models.CharField(max_length=200, blank=True, db_column="wan_geoLoc")
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    mac = models.CharField(max_length=50, blank=True)
    derby_plant_loc = models.CharField(max_length=100, blank=True)
    current_user = models.CharField(max_length=100, blank=True)
    domain = models.CharField(max_length=100, blank=True)
    pc_make_model = models.CharField(max_length=200, blank=True)
    ram = models.CharField(max_length=50, blank=True)
    processor_name = models.CharField(max_length=200, blank=True)
    date = models.CharField(
        max_length=50, blank=True
    )  # Keeping as CharField since format varies
    os_name = models.CharField(max_length=200, blank=True)

    class Meta:
        managed = False  # Don't let Django manage this table
        db_table = "pcInfo"  # Correct table name from discovery
        app_label = "tickets"
        verbose_name = "Computer Information"
        verbose_name_plural = "Computer Information"

    def __str__(self):
        return f"{self.hostname} ({self.current_user})"


class TicketComputerInfo(models.Model):
    """
    Links tickets to computer information at the time of ticket creation.
    This stores a snapshot of the computer info when the ticket was created.
    """

    ticket = models.OneToOneField(
        Ticket, on_delete=models.CASCADE, related_name="computer_info"
    )
    serial_number = models.CharField(max_length=100)
    hostname = models.CharField(max_length=100)
    wan_ip = models.GenericIPAddressField(null=True, blank=True)
    isp = models.CharField(max_length=200, blank=True)
    wan_geo_loc = models.CharField(max_length=200, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    mac = models.CharField(max_length=50, blank=True)
    derby_plant_loc = models.CharField(max_length=100, blank=True)
    current_user = models.CharField(max_length=100, blank=True)
    domain = models.CharField(max_length=100, blank=True)
    pc_make_model = models.CharField(max_length=200, blank=True)
    ram = models.CharField(max_length=50, blank=True)
    processor_name = models.CharField(max_length=200, blank=True)
    os_name = models.CharField(max_length=200, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ticket Computer Information"
        verbose_name_plural = "Ticket Computer Information"

    def __str__(self):
        return f"{self.ticket.title} - {self.hostname}"


class TicketUpdate(models.Model):
    """
    Timeline updates for tickets - tracks all administrative actions and changes.
    This provides a user-friendly timeline display of ticket history.
    """

    UPDATE_TYPES = [
        ("ASSIGNED", "Ticket Assigned"),
        ("UNASSIGNED", "Ticket Unassigned"),
        ("STATUS_CHANGED", "Status Changed"),
        ("PRIORITY_CHANGED", "Priority Changed"),
        ("CC_ADMIN_ADDED", "CC Admin Added"),
        ("CC_ADMIN_REMOVED", "CC Admin Removed"),
        ("CC_USER_ADDED", "CC User Added"),
        ("CC_USER_REMOVED", "CC User Removed"),
        ("TITLE_CHANGED", "Title Changed"),
        ("DESCRIPTION_CHANGED", "Description Changed"),
        ("CATEGORY_CHANGED", "Category Changed"),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="updates")
    update_type = models.CharField(max_length=20, choices=UPDATE_TYPES)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who made the change",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Change details - flexible JSON field for different update types
    change_data = models.JSONField(default=dict, help_text="Details of what changed")

    # Human-readable description
    description = models.CharField(
        max_length=500, help_text="Human-readable description of the change"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ticket Update"
        verbose_name_plural = "Ticket Updates"

    def __str__(self):
        user_name = (
            self.user.get_full_name()
            if self.user and self.user.get_full_name()
            else (self.user.username if self.user else "System")
        )
        return f"{user_name}: {self.description}"

    @property
    def user_display_name(self):
        """Get the display name for the user who made the change"""
        if not self.user:
            return "System"
        return self.user.get_full_name() or self.user.username

    @property
    def icon_class(self):
        """Get the appropriate FontAwesome icon for this update type"""
        icon_map = {
            "ASSIGNED": "fas fa-user-plus",
            "UNASSIGNED": "fas fa-user-minus",
            "STATUS_CHANGED": "fas fa-toggle-on bg-info",
            "PRIORITY_CHANGED": "fas fa-exclamation-triangle bg-warning",
            "CC_ADMIN_ADDED": "fas fa-user-shield bg-danger",
            "CC_ADMIN_REMOVED": "fas fa-user-shield bg-danger",
            "CC_USER_ADDED": "fas fa-users bg-primary",
            "CC_USER_REMOVED": "fas fa-users bg-primary",
            "TITLE_CHANGED": "fas fa-edit bg-success",
            "DESCRIPTION_CHANGED": "fas fa-file-alt bg-secondary",
            "CATEGORY_CHANGED": "fas fa-tag",
        }
        return icon_map.get(self.update_type, "fas fa-history")

    @classmethod
    def create_from_audit_log(cls, audit_log):
        """
        Create TicketUpdate entries from AuditLog entries for tickets.
        This method processes audit logs and creates user-friendly timeline entries.
        """
        if audit_log.object_type != "Ticket":
            return []

        updates = []
        ticket_id = audit_log.object_id

        try:
            ticket = Ticket.objects.get(id=ticket_id)
        except Ticket.DoesNotExist:
            return []

        changes = audit_log.changes or {}

        # Process different types of changes
        for field, change_info in changes.items():
            old_value = change_info.get("old", "")
            new_value = change_info.get("new", "")

            if field == "assigned_to":
                if old_value and not new_value:
                    # Unassigned
                    update = cls(
                        ticket=ticket,
                        update_type="UNASSIGNED",
                        user=audit_log.user,
                        created_at=audit_log.timestamp,
                        change_data={"old_assignee": old_value},
                        description=f"unassigned this ticket from {old_value}",
                    )
                elif new_value:
                    # Assigned
                    update = cls(
                        ticket=ticket,
                        update_type="ASSIGNED",
                        user=audit_log.user,
                        created_at=audit_log.timestamp,
                        change_data={
                            "new_assignee": new_value,
                            "old_assignee": old_value,
                        },
                        description=f"assigned this ticket to {new_value}",
                    )
                else:
                    continue
                updates.append(update)

            elif field == "status":
                update = cls(
                    ticket=ticket,
                    update_type="STATUS_CHANGED",
                    user=audit_log.user,
                    created_at=audit_log.timestamp,
                    change_data={"old_status": old_value, "new_status": new_value},
                    description=f"changed status from {old_value} to {new_value}",
                )
                updates.append(update)

            elif field == "priority":
                update = cls(
                    ticket=ticket,
                    update_type="PRIORITY_CHANGED",
                    user=audit_log.user,
                    created_at=audit_log.timestamp,
                    change_data={"old_priority": old_value, "new_priority": new_value},
                    description=f"changed priority from {old_value} to {new_value}",
                )
                updates.append(update)

            elif field == "title":
                update = cls(
                    ticket=ticket,
                    update_type="TITLE_CHANGED",
                    user=audit_log.user,
                    created_at=audit_log.timestamp,
                    change_data={"old_title": old_value, "new_title": new_value},
                    description=f"changed title",
                )
                updates.append(update)

            elif field == "description":
                update = cls(
                    ticket=ticket,
                    update_type="DESCRIPTION_CHANGED",
                    user=audit_log.user,
                    created_at=audit_log.timestamp,
                    change_data={
                        "old_description": old_value,
                        "new_description": new_value,
                    },
                    description=f"updated description",
                )
                updates.append(update)

            elif field == "cc_admins":
                # Handle CC admin changes
                new_users = new_value if isinstance(new_value, list) else []
                for user in new_users:
                    update = cls(
                        ticket=ticket,
                        update_type="CC_ADMIN_ADDED",
                        user=audit_log.user,
                        created_at=audit_log.timestamp,
                        change_data={"added_user": user},
                        description=f"added {user} to CC Admins",
                    )
                    updates.append(update)

            elif field == "cc_non_admins":
                # Handle CC non-admin changes
                new_users = new_value if isinstance(new_value, list) else []
                for user in new_users:
                    update = cls(
                        ticket=ticket,
                        update_type="CC_USER_ADDED",
                        user=audit_log.user,
                        created_at=audit_log.timestamp,
                        change_data={"added_user": user},
                        description=f"added {user} to CC Users",
                    )
                    updates.append(update)

        return updates
