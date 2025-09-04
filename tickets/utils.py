"""
Utility functions for ticket access and permissions
"""


def user_can_access_ticket(user, ticket):
    """
    Check if a user has permission to access a ticket.
    Users can access tickets if they are:
    - The creator (created_by)
    - The assignee (assigned_to)
    - A CC Admin (cc_admins)
    - A CC Non-Admin (cc_non_admins)
    - Staff/superuser
    """
    if not user or not ticket:
        return False

    # Check basic permissions
    if (
        ticket.created_by == user
        or ticket.assigned_to == user
        or user.is_staff
        or user.is_superuser
    ):
        return True

    # Check CC permissions
    if (
        ticket.cc_admins.filter(id=user.id).exists()
        or ticket.cc_non_admins.filter(id=user.id).exists()
    ):
        return True

    return False
