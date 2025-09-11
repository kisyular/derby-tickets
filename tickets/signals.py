from django.db.models.signals import post_save, pre_save, m2m_changed
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Ticket, Comment
from .email_utils import (
    send_ticket_assigned_notification,
    send_comment_notification,
    send_ticket_updated_notification,
    send_ticket_cc_updated_notification,
)
from .async_email import send_email_async  # Import async wrapper
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Ticket)
def track_ticket_changes(sender, instance, **kwargs):
    """Track changes to ticket before saving."""
    if instance.pk:  # Only for existing tickets
        try:
            # Only capture old values on the FIRST pre_save call
            if not hasattr(instance, "_old_status"):
                old_ticket = Ticket.objects.get(pk=instance.pk)
                print(
                    f"DEBUG: pre_save triggered for ticket {instance.pk} (FIRST CALL)"
                )
                print(
                    f"DEBUG: DB status: '{old_ticket.status}', Instance status: '{instance.status}'"
                )
                instance._old_priority = old_ticket.priority
                instance._old_status = old_ticket.status
                instance._old_assigned_to = old_ticket.assigned_to
                # Track CC fields before save
                instance._old_cc_admins = set(
                    old_ticket.cc_admins.values_list("id", flat=True)
                )
                instance._old_cc_non_admins = set(
                    old_ticket.cc_non_admins.values_list("id", flat=True)
                )
            else:
                print(
                    f"DEBUG: pre_save triggered for ticket {instance.pk} (SUBSEQUENT CALL - IGNORED)"
                )
        except Ticket.DoesNotExist:
            instance._old_priority = None
            instance._old_status = None
            instance._old_assigned_to = None
            instance._old_cc_admins = set()
            instance._old_cc_non_admins = set()
    else:
        instance._old_priority = None
        instance._old_status = None
        instance._old_assigned_to = None
        instance._old_cc_admins = set()
        instance._old_cc_non_admins = set()


@receiver(post_save, sender=Ticket)
def ticket_saved(sender, instance, created, **kwargs):
    """Handle ticket creation and updates."""
    print(
        f"DEBUG: post_save triggered for ticket {instance.id}, status={instance.status}, created={created}"
    )
    try:
        if created:
            # New ticket created
            logger.info(f"New ticket created: {instance.id}")
            # send_ticket_created_notification(instance)  # <-- Removed, now sent from view after attachments

            # Check if new ticket was created with assignment
            if instance.assigned_to:
                logger.info(
                    f"New ticket {instance.id} created with assignment to {instance.assigned_to}"
                )
                # Send assignment notification asynchronously
                send_email_async(send_ticket_assigned_notification, instance)
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
            print(
                f"DEBUG: Status check - hasattr(_old_status): {hasattr(instance, '_old_status')}"
            )
            if hasattr(instance, "_old_status"):
                print(
                    f"DEBUG: Old status: {repr(instance._old_status)}, Current status: {repr(instance.status)}"
                )
                print(
                    f"DEBUG: Status different: {instance._old_status != instance.status}"
                )

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
                print(
                    f"DEBUG: Status change detected! changed_fields: {changed_fields}"
                )
            else:
                print("DEBUG: No status change detected")

            # Check for assignment change (only if we haven't already processed this instance)
            if hasattr(instance, "_old_assigned_to"):
                old_assigned = getattr(instance, "_old_assigned_to", None)
                logger.debug(
                    f"Assignment check - old: {old_assigned}, new: {instance.assigned_to}, created: {created}"
                )

                if old_assigned != instance.assigned_to:
                    if instance.assigned_to:
                        # Ticket was assigned
                        logger.info(
                            f"Ticket {instance.id} assigned to {instance.assigned_to}"
                        )
                        # Send assignment notification asynchronously
                        send_email_async(send_ticket_assigned_notification, instance)
                    else:
                        logger.debug(f"No assigned_to user for ticket {instance.id}")
                else:
                    logger.debug(
                        f"No assignment change detected for ticket {instance.id}"
                    )
            else:
                print(
                    f"DEBUG: Skipping assignment check for ticket {instance.id} (already processed)"
                )

            # Note: Assignment changes are handled by their own notification above,
            # so we don't include them in the general ticket update notification

            # Send update notification if there were significant changes
            if changed_fields:
                logger.info(
                    f"Ticket {instance.id} updated with changes: {list(changed_fields.keys())}"
                )
                # Get the user who made the change (if available from request)
                updated_by = getattr(instance, "_updated_by", None)
                if updated_by:
                    # Send ticket update notification asynchronously
                    send_email_async(
                        send_ticket_updated_notification,
                        instance,
                        changed_fields,
                        updated_by,
                    )
                else:
                    logger.warning(f"No updated_by user found for ticket {instance.id}")

            # Clear old values to prevent duplicate notifications on subsequent saves
            # This must be done AFTER all change detection to avoid false positives
            if hasattr(instance, "_old_status"):
                delattr(instance, "_old_status")
            if hasattr(instance, "_old_priority"):
                delattr(instance, "_old_priority")
            if hasattr(instance, "_old_assigned_to"):
                delattr(instance, "_old_assigned_to")
            if hasattr(instance, "_old_cc_admins"):
                delattr(instance, "_old_cc_admins")
            if hasattr(instance, "_old_cc_non_admins"):
                delattr(instance, "_old_cc_non_admins")
            print(
                f"DEBUG: Cleared old values after all checks for ticket {instance.id}"
            )

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
            # Send comment notification asynchronously
            send_email_async(send_comment_notification, instance, instance.ticket)
        except Exception as e:
            logger.error(f"Error in comment_saved signal: {e}")


@receiver(m2m_changed, sender=Ticket.cc_admins.through)
def cc_admins_changed(sender, instance, action, pk_set, **kwargs):
    """Handle changes to cc_admins field."""
    if action == "post_add":
        try:
            new_cc_admins = User.objects.filter(id__in=pk_set)
            if new_cc_admins.exists():
                logger.info(f"CC Admins added to ticket {instance.id}: {list(pk_set)}")
                # Use consistent async email queue
                send_email_async(
                    send_ticket_cc_updated_notification, instance, new_cc_admins, []
                )
        except Exception as e:
            logger.error(f"Error in cc_admins_changed signal: {e}")


@receiver(m2m_changed, sender=Ticket.cc_non_admins.through)
def cc_non_admins_changed(sender, instance, action, pk_set, **kwargs):
    """Handle changes to cc_non_admins field."""
    if action == "post_add":
        try:
            new_cc_non_admins = User.objects.filter(id__in=pk_set)
            if new_cc_non_admins.exists():
                logger.info(
                    f"CC Non-Admins added to ticket {instance.id}: {list(pk_set)}"
                )
                # Use consistent async email queue
                send_email_async(
                    send_ticket_cc_updated_notification, instance, [], new_cc_non_admins
                )
        except Exception as e:
            logger.error(f"Error in cc_non_admins_changed signal: {e}")


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
