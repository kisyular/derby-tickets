"""
Service for managing ticket updates and timeline entries.
Converts audit logs into user-friendly timeline updates.
"""

from django.db import transaction
from .models import TicketUpdate, Ticket
from .audit_models import AuditLog
from django.contrib.auth.models import User


class TicketUpdateService:
    """Service for creating and managing ticket timeline updates"""

    @staticmethod
    def create_update(ticket, update_type, user, description, change_data=None):
        """
        Create a new ticket update entry

        Args:
            ticket: Ticket instance
            update_type: One of TicketUpdate.UPDATE_TYPES
            user: User who made the change
            description: Human-readable description
            change_data: Dictionary of change details
        """
        return TicketUpdate.objects.create(
            ticket=ticket,
            update_type=update_type,
            user=user,
            description=description,
            change_data=change_data or {},
        )

    @staticmethod
    def create_assignment_update(ticket, user, old_assignee, new_assignee):
        """Create update for ticket assignment changes"""
        if old_assignee and not new_assignee:
            # Unassigned
            return TicketUpdateService.create_update(
                ticket=ticket,
                update_type="UNASSIGNED",
                user=user,
                description=f"unassigned this ticket from {old_assignee.get_full_name() or old_assignee.username}",
                change_data={"old_assignee": old_assignee.username},
            )
        elif new_assignee:
            # Assigned (could be reassignment)
            if old_assignee:
                description = f"reassigned this ticket from {old_assignee.get_full_name() or old_assignee.username} to {new_assignee.get_full_name() or new_assignee.username}"
            else:
                description = f"assigned this ticket to {new_assignee.get_full_name() or new_assignee.username}"

            return TicketUpdateService.create_update(
                ticket=ticket,
                update_type="ASSIGNED",
                user=user,
                description=description,
                change_data={
                    "old_assignee": old_assignee.username if old_assignee else None,
                    "new_assignee": new_assignee.username,
                },
            )

    @staticmethod
    def create_status_update(ticket, user, old_status, new_status):
        """Create update for status changes"""
        return TicketUpdateService.create_update(
            ticket=ticket,
            update_type="STATUS_CHANGED",
            user=user,
            description=f"changed status from {old_status} to {new_status}",
            change_data={"old_status": old_status, "new_status": new_status},
        )

    @staticmethod
    def create_priority_update(ticket, user, old_priority, new_priority):
        """Create update for priority changes"""
        return TicketUpdateService.create_update(
            ticket=ticket,
            update_type="PRIORITY_CHANGED",
            user=user,
            description=f"changed priority from {old_priority} to {new_priority}",
            change_data={"old_priority": old_priority, "new_priority": new_priority},
        )

    @staticmethod
    def create_cc_update(ticket, user, added_users, removed_users, is_admin=True):
        """Create updates for CC changes"""
        updates = []
        user_type = "CC Admins" if is_admin else "CC Users"
        update_type_add = "CC_ADMIN_ADDED" if is_admin else "CC_USER_ADDED"
        update_type_remove = "CC_ADMIN_REMOVED" if is_admin else "CC_USER_REMOVED"

        # Handle added users
        for added_user in added_users:
            update = TicketUpdateService.create_update(
                ticket=ticket,
                update_type=update_type_add,
                user=user,
                description=f"added {added_user.get_full_name() or added_user.username} to {user_type}",
                change_data={"added_user": added_user.username},
            )
            updates.append(update)

        # Handle removed users
        for removed_user in removed_users:
            update = TicketUpdateService.create_update(
                ticket=ticket,
                update_type=update_type_remove,
                user=user,
                description=f"removed {removed_user.get_full_name() or removed_user.username} from {user_type}",
                change_data={"removed_user": removed_user.username},
            )
            updates.append(update)

        return updates

    @staticmethod
    def create_edit_update(
        ticket, user, title_changed=False, description_changed=False
    ):
        """Create updates for title/description changes"""
        updates = []

        if title_changed:
            update = TicketUpdateService.create_update(
                ticket=ticket,
                update_type="TITLE_CHANGED",
                user=user,
                description="updated the title",
            )
            updates.append(update)

        if description_changed:
            update = TicketUpdateService.create_update(
                ticket=ticket,
                update_type="DESCRIPTION_CHANGED",
                user=user,
                description="updated the description",
            )
            updates.append(update)

        return updates

    @staticmethod
    def get_timeline_entries(ticket):
        """
        Get all timeline entries for a ticket (comments + updates) sorted by date.
        Returns a list of dictionaries with consistent structure for template rendering.
        """
        timeline_entries = []

        # Get comments
        comments = ticket.comments.all().order_by("created_at")
        for comment in comments:
            timeline_entries.append(
                {
                    "type": "comment",
                    "timestamp": comment.created_at,
                    "content": comment,
                    "is_internal": comment.is_internal,
                    "sort_key": comment.created_at,
                }
            )

        # Get updates
        updates = ticket.updates.all().order_by("created_at")
        for update in updates:
            timeline_entries.append(
                {
                    "type": "update",
                    "timestamp": update.created_at,
                    "content": update,
                    "is_internal": False,  # Updates are not internal
                    "sort_key": update.created_at,
                }
            )

        # Add ticket creation entry
        timeline_entries.append(
            {
                "type": "creation",
                "timestamp": ticket.created_at,
                "content": ticket,
                "is_internal": False,
                "sort_key": ticket.created_at,
            }
        )

        # Sort by timestamp (newest first for display)
        timeline_entries.sort(key=lambda x: x["sort_key"], reverse=True)

        return timeline_entries

    @staticmethod
    def process_ticket_changes(ticket, changes, user):
        """
        Process changes from form submission and create appropriate updates.
        This should be called after saving ticket changes.

        Args:
            ticket: Ticket instance
            changes: Dictionary of changes from audit system
            user: User who made the changes
        """
        if not changes:
            return

        # Handle assignment changes
        if "assigned_to" in changes:
            change = changes["assigned_to"]
            old_assignee = (
                User.objects.filter(username=change.get("old")).first()
                if change.get("old")
                else None
            )
            new_assignee = (
                User.objects.filter(username=change.get("new")).first()
                if change.get("new")
                else None
            )

            if old_assignee != new_assignee:
                TicketUpdateService.create_assignment_update(
                    ticket, user, old_assignee, new_assignee
                )

        # Handle status changes
        if "status" in changes:
            change = changes["status"]
            TicketUpdateService.create_status_update(
                ticket, user, change.get("old"), change.get("new")
            )

        # Handle priority changes
        if "priority" in changes:
            change = changes["priority"]
            TicketUpdateService.create_priority_update(
                ticket, user, change.get("old"), change.get("new")
            )

        # Handle title/description changes
        title_changed = "title" in changes
        description_changed = "description" in changes
        if title_changed or description_changed:
            TicketUpdateService.create_edit_update(
                ticket, user, title_changed, description_changed
            )
