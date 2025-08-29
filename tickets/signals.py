from django.db.models.signals import post_save, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Ticket, Comment
from .email_utils import (
    send_ticket_assigned_notification,
    send_comment_notification,
    send_ticket_updated_notification,
)
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Ticket)
def track_ticket_changes(sender, instance, **kwargs):
    """Track changes to ticket before saving."""
    if instance.pk:  # Only for existing tickets
        try:
            old_ticket = Ticket.objects.get(pk=instance.pk)
            instance._old_priority = old_ticket.priority
            instance._old_status = old_ticket.status
            instance._old_assigned_to = old_ticket.assigned_to
        except Ticket.DoesNotExist:
            instance._old_priority = None
            instance._old_status = None
            instance._old_assigned_to = None
    else:
        instance._old_priority = None
        instance._old_status = None
        instance._old_assigned_to = None


@receiver(post_save, sender=Ticket)
def ticket_saved(sender, instance, created, **kwargs):
    """Handle ticket creation and updates."""
    try:
        if created:
            # New ticket created
            logger.info(f"New ticket created: {instance.id}")
            # send_ticket_created_notification(instance)  # <-- Removed, now sent from view after attachments
        else:
            # Existing ticket updated
            changed_fields = {}

            # Check for priority change
            if (
                hasattr(instance, "_old_priority")
                and instance._old_priority != instance.priority
            ):
                priority_choices = dict(instance._meta.get_field("priority").choices)
                changed_fields["priority"] = {
                    "old": priority_choices.get(
                        instance._old_priority, instance._old_priority
                    ),
                    "new": priority_choices.get(instance.priority, instance.priority),
                }

            # Check for status change
            if (
                hasattr(instance, "_old_status")
                and instance._old_status != instance.status
            ):
                status_choices = dict(instance._meta.get_field("status").choices)
                changed_fields["status"] = {
                    "old": status_choices.get(
                        instance._old_status, instance._old_status
                    ),
                    "new": status_choices.get(instance.status, instance.status),
                }

            # Check for assignment change
            old_assigned = getattr(instance, "_old_assigned_to", None)
            if old_assigned != instance.assigned_to:
                if instance.assigned_to:
                    # Ticket was assigned
                    logger.info(
                        f"Ticket {instance.id} assigned to {instance.assigned_to}"
                    )
                    send_ticket_assigned_notification(instance)

                # Track assignment change for update notification
                changed_fields["assigned_to"] = {
                    "old": (
                        old_assigned.get_full_name() if old_assigned else "Unassigned"
                    ),
                    "new": (
                        instance.assigned_to.get_full_name()
                        if instance.assigned_to
                        else "Unassigned"
                    ),
                }

            # Send update notification if there were significant changes
            if changed_fields:
                logger.info(
                    f"Ticket {instance.id} updated with changes: {list(changed_fields.keys())}"
                )
                # Get the user who made the change (if available from request)
                updated_by = getattr(instance, "_updated_by", None)
                if updated_by:
                    send_ticket_updated_notification(
                        instance, changed_fields, updated_by
                    )
                else:
                    logger.warning(f"No updated_by user found for ticket {instance.id}")

    except Exception as e:
        logger.error(f"Error in ticket_saved signal: {e}")


@receiver(post_save, sender=Comment)
def comment_saved(sender, instance, created, **kwargs):
    """Handle new comments."""
    if created:
        try:
            logger.info(
                f"New comment added to ticket {instance.ticket.id} by {instance.author}"
            )
            send_comment_notification(instance, instance.ticket)
        except Exception as e:
            logger.error(f"Error in comment_saved signal: {e}")


@receiver(user_logged_in)
def handle_user_login_signal(sender, request, user, **kwargs):
    """Handle Django's built-in login signal for session tracking."""
    try:
        # Import here to avoid circular imports
        from .audit_security import audit_security_manager

        # Only create session if it doesn't exist (avoid duplicate creation from our views)
        from .audit_models import UserSession

        session_key = request.session.session_key

        if session_key:
            existing_session = UserSession.objects.filter(
                user=user, session_key=session_key, is_active=True
            ).exists()

            if not existing_session:
                audit_security_manager.create_user_session(
                    request=request,
                    user=user,
                    login_method=(
                        "django_admin" if "/admin/" in request.path else "password"
                    ),
                )
                logger.info(f"Session created via signal for user: {user.username}")
    except Exception as e:
        logger.error(f"Error in handle_user_login_signal: {e}")


@receiver(user_logged_out)
def handle_user_logout_signal(sender, request, user, **kwargs):
    """Handle Django's built-in logout signal for session tracking."""
    try:
        # Import here to avoid circular imports
        from .audit_security import audit_security_manager

        if user:
            audit_security_manager.end_user_session(request, user)
            logger.info(f"Session ended via signal for user: {user.username}")
    except Exception as e:
        logger.error(f"Error in handle_user_logout_signal: {e}")
