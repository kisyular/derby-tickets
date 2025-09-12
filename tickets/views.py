from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.core.cache import cache
from django.utils import timezone
from django.http import HttpResponse
from datetime import timedelta
import csv
from .models import Ticket, UserProfile, Comment, Category
from .security import SecurityManager, domain_required, staff_required
from .audit_security import audit_security_manager
from .update_service import TicketUpdateService
from .logging_utils import log_auth_event, log_security_event
from .utils import user_can_access_ticket
from .async_email import send_email_async

# Create your views here.

# Restore proper authentication with User model linked to custom profiles


def get_categories_cached():
    """Get categories with caching for better performance"""
    return cache.get_or_set(
        "categories_list",
        lambda: list(Category.objects.all().order_by("name")),
        300,  # Cache for 5 minutes
    )


@login_required
def ticket_list(request):
    """Display a list of all tickets with filtering"""
    # Users can see tickets they created, are assigned to, or are CC'd on
    # Optimize with select_related to prevent N+1 queries
    tickets = (
        Ticket.objects.select_related("created_by", "assigned_to", "category")
        .filter(
            Q(created_by=request.user)
            | Q(assigned_to=request.user)
            | Q(cc_admins=request.user)
            | Q(cc_non_admins=request.user)
        )
        .distinct()
    )

    # Apply filters
    status_filter = request.GET.get("status")
    priority_filter = request.GET.get("priority")
    search_query = request.GET.get("search")

    if status_filter:
        tickets = tickets.filter(status=status_filter)

    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)

    if search_query:
        tickets = tickets.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Order by most recent first
    tickets = tickets.order_by("-updated_at")

    # Calculate status and priority counts
    open_count = tickets.filter(status="Open").count()
    in_progress_count = tickets.filter(status="In Progress").count()
    closed_count = tickets.filter(status="Closed").count()
    urgent_count = tickets.filter(priority="Urgent").count()

    # For admin/staff users, get all tickets assigned to them (regardless of creator)
    assigned_tickets = []
    assigned_count = 0
    if request.user.is_staff or request.user.is_superuser:
        assigned_tickets = Ticket.objects.filter(assigned_to=request.user)

        # Apply the same filters to assigned tickets
        if status_filter:
            assigned_tickets = assigned_tickets.filter(status=status_filter)

        if priority_filter:
            assigned_tickets = assigned_tickets.filter(priority=priority_filter)

        if search_query:
            assigned_tickets = assigned_tickets.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        # Order by most recent first
        assigned_tickets = assigned_tickets.order_by("-updated_at")
        assigned_count = assigned_tickets.count()

    # Add pagination for better performance
    paginator = Paginator(tickets, 25)  # 25 tickets per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "tickets": page_obj,  # Use paginated tickets
        "page_obj": page_obj,  # For pagination controls in template
        "open_count": open_count,
        "in_progress_count": in_progress_count,
        "closed_count": closed_count,
        "urgent_count": urgent_count,
        "assigned_tickets": assigned_tickets,
        "assigned_count": assigned_count,
    }
    return render(request, "tickets/ticket_list.html", context)


@login_required
def ticket_detail(request, ticket_id):
    """Display details of a specific ticket with edit functionality and comments"""
    # Optimize with select_related to prevent N+1 queries
    ticket = get_object_or_404(
        Ticket.objects.select_related(
            "created_by", "assigned_to", "category"
        ).prefetch_related("comments__author", "attachments"),
        id=ticket_id,
    )

    # Check if user has permission to view this ticket
    if not user_can_access_ticket(request.user, ticket):
        messages.error(request, "You don't have permission to view this ticket.")
        return redirect("tickets:ticket_list")

    # Log the ticket view for audit trail
    audit_security_manager.log_audit_event(
        request=request,
        action="READ",
        user=request.user,
        object_type="Ticket",
        object_id=str(ticket.id),
        object_repr=str(ticket),
        description=f"Viewed Ticket #{ticket.id}: {ticket.title}",
        risk_level="LOW",
    )

    # Handle POST requests
    if request.method == "POST":
        action = request.POST.get("action", "edit_ticket")

        if action == "edit_ticket" and (
            (ticket.created_by == request.user or request.user.is_staff)
            and (request.user.is_staff or ticket.status.lower() != "closed")
        ):
            # Handle ticket editing
            title = request.POST.get("title")
            description = request.POST.get("description")
            priority = request.POST.get("priority")
            status = request.POST.get("status")
            assigned_to_id = request.POST.get("assigned_to")
            cc_admin_ids = request.POST.getlist("cc_admins")
            cc_non_admin_ids = request.POST.getlist("cc_non_admins")

            if title and priority and status:
                # Check if admin is editing a closed ticket
                is_reopening_closed_ticket = (
                    request.user.is_staff
                    and ticket.status.lower() == "closed"
                    and (
                        title != ticket.title
                        or description != ticket.description
                        or priority != ticket.priority
                        or status != ticket.status
                        or assigned_to_id
                        != (ticket.assigned_to.id if ticket.assigned_to else None)
                    )
                )

                # Capture changes for audit trail
                changes = {}
                if ticket.title != title:
                    changes["title"] = {"old": ticket.title, "new": title}
                if ticket.description != description:
                    changes["description"] = {
                        "old": ticket.description,
                        "new": description,
                    }
                if ticket.priority != priority:
                    changes["priority"] = {"old": ticket.priority, "new": priority}
                if ticket.status != status:
                    changes["status"] = {"old": ticket.status, "new": status}

                # Handle assignment changes
                if request.user.is_staff:
                    old_assigned_to = ticket.assigned_to
                    new_assigned_to = None
                    if assigned_to_id:
                        try:
                            new_assigned_to = User.objects.get(
                                id=assigned_to_id, is_staff=True
                            )
                        except User.DoesNotExist:
                            pass

                    if old_assigned_to != new_assigned_to:
                        changes["assigned_to"] = {
                            "old": (
                                old_assigned_to.username if old_assigned_to else None
                            ),
                            "new": (
                                new_assigned_to.username if new_assigned_to else None
                            ),
                        }
                        ticket.assigned_to = new_assigned_to

                ticket.title = title
                ticket.description = description
                ticket.priority = priority

                # If admin is reopening a closed ticket, automatically set status to "Open"
                if is_reopening_closed_ticket:
                    old_status = ticket.status
                    ticket.status = "Open"
                    # Update the changes to reflect the reopening
                    changes["status"] = {"old": old_status, "new": "Open"}
                    changes["admin_reopened"] = True
                else:
                    ticket.status = status

                # Set the user who made the changes for email notifications
                ticket._updated_by = request.user
                ticket.save()

                # Handle CC changes for staff users
                if request.user.is_staff:
                    # Track CC admin changes
                    old_cc_admins = set(ticket.cc_admins.all())
                    new_cc_admins = set()
                    if cc_admin_ids:
                        new_cc_admins = set(
                            User.objects.filter(id__in=cc_admin_ids, is_staff=True)
                        )

                    # Update CC admins
                    ticket.cc_admins.set(new_cc_admins)

                    # Track changes for updates
                    added_cc_admins = new_cc_admins - old_cc_admins
                    removed_cc_admins = old_cc_admins - new_cc_admins

                    if added_cc_admins or removed_cc_admins:
                        TicketUpdateService.create_cc_update(
                            ticket,
                            request.user,
                            added_cc_admins,
                            removed_cc_admins,
                            is_admin=True,
                        )
                        changes["cc_admins"] = {
                            "new": [u.username for u in new_cc_admins]
                        }

                    # Track CC non-admin changes
                    old_cc_non_admins = set(ticket.cc_non_admins.all())
                    new_cc_non_admins = set()
                    if cc_non_admin_ids:
                        new_cc_non_admins = set(
                            User.objects.filter(id__in=cc_non_admin_ids, is_staff=False)
                        )

                    # Update CC non-admins
                    ticket.cc_non_admins.set(new_cc_non_admins)

                    # Track changes for updates
                    added_cc_non_admins = new_cc_non_admins - old_cc_non_admins
                    removed_cc_non_admins = old_cc_non_admins - new_cc_non_admins

                    if added_cc_non_admins or removed_cc_non_admins:
                        TicketUpdateService.create_cc_update(
                            ticket,
                            request.user,
                            added_cc_non_admins,
                            removed_cc_non_admins,
                            is_admin=False,
                        )
                        changes["cc_non_admins"] = {
                            "new": [u.username for u in new_cc_non_admins]
                        }

                # Create timeline updates for other changes
                TicketUpdateService.process_ticket_changes(
                    ticket, changes, request.user
                )

                # Handle notifications based on whether ticket was reopened
                if is_reopening_closed_ticket:
                    # Send reopened notification instead of regular update notification
                    from .email_utils import send_ticket_reopened_notification

                    send_email_async(
                        send_ticket_reopened_notification,
                        ticket,
                        changes,
                        request.user,
                    )

                    # Log as a reopening action
                    audit_security_manager.log_audit_event(
                        request=request,
                        action="REOPEN",
                        user=request.user,
                        object_type="Ticket",
                        object_id=str(ticket.id),
                        object_repr=str(ticket),
                        changes=changes,
                        description=f"Admin reopened and updated Ticket #{ticket.id}: {ticket.title}",
                        risk_level="MEDIUM",
                    )

                    messages.success(
                        request, "Ticket has been reopened and updated successfully!"
                    )
                else:
                    # Log the regular ticket update for audit trail
                    audit_security_manager.log_audit_event(
                        request=request,
                        action="UPDATE",
                        user=request.user,
                        object_type="Ticket",
                        object_id=str(ticket.id),
                        object_repr=str(ticket),
                        changes=changes,
                        description=f"Updated Ticket #{ticket.id}: {ticket.title}",
                        risk_level="LOW",
                    )

                    messages.success(request, "Ticket updated successfully!")
                return redirect("tickets:ticket_detail", ticket_id=ticket.id)
            else:
                messages.error(request, "Please fill in all required fields.")

        elif action == "add_comment":
            # Handle comment adding
            comment_content = request.POST.get("comment_content", "").strip()
            is_internal = request.POST.get("is_internal") == "on"

            if comment_content:
                # Check if this is the first comment on an open ticket
                existing_comments_count = ticket.comments.count()
                should_update_status = (
                    ticket.status == "Open"
                    and existing_comments_count == 0
                    and request.user
                    != ticket.created_by  # Don't update status if ticket creator is commenting
                )

                comment = Comment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=comment_content,
                    is_internal=is_internal
                    and request.user.is_staff,  # Only staff can create internal comments
                )

                # If this was the first comment on an open ticket, change status to "In Progress"
                if should_update_status:
                    old_status = ticket.status
                    ticket.status = "In Progress"
                    ticket._updated_by = (
                        request.user
                    )  # Set the user who made the change
                    ticket.save()

                    # Log the automatic status change
                    audit_security_manager.log_audit_event(
                        request=request,
                        action="UPDATE",
                        user=request.user,
                        object_type="Ticket",
                        object_id=str(ticket.id),
                        object_repr=str(ticket),
                        description=f"Auto-updated ticket status from '{old_status}' to 'In Progress' due to first comment",
                        risk_level="LOW",
                        changes={"status": {"old": old_status, "new": "In Progress"}},
                    )

                    messages.info(
                        request,
                        f"Ticket status automatically changed to 'In Progress' since this is the first comment.",
                    )

                # Log the comment creation for audit trail
                audit_security_manager.log_audit_event(
                    request=request,
                    action="CREATE",
                    user=request.user,
                    object_type="Comment",
                    object_id=str(comment.id),
                    object_repr=f"Comment on Ticket #{ticket.id}",
                    description=f"Added comment to Ticket #{ticket.id}: {ticket.title}",
                    risk_level="LOW",
                    changes={"ticket_id": ticket.id, "is_internal": is_internal},
                )

                messages.success(request, "Comment added successfully!")
                return redirect("tickets:ticket_detail", ticket_id=ticket.id)
            else:
                messages.error(request, "Comment content is required.")

        elif action == "edit_comment":
            # Handle comment editing
            comment_id = request.POST.get("comment_id")
            new_content = request.POST.get("comment_content", "").strip()
            is_internal = request.POST.get("is_internal") == "on"

            if comment_id and new_content:
                try:
                    comment = Comment.objects.get(id=comment_id, ticket=ticket)

                    # Check permissions: user can edit their own comments, admin can edit any
                    if comment.author == request.user or request.user.is_staff:
                        old_content = comment.content
                        old_is_internal = comment.is_internal

                        comment.content = new_content
                        # Only staff can set internal status
                        if request.user.is_staff:
                            comment.is_internal = is_internal
                        comment.save()

                        # Log the comment edit for audit trail
                        audit_security_manager.log_audit_event(
                            request=request,
                            action="UPDATE",
                            user=request.user,
                            object_type="Comment",
                            object_id=str(comment.id),
                            object_repr=f"Comment on Ticket #{ticket.id}",
                            description=f"Edited comment on Ticket #{ticket.id}: {ticket.title}",
                            risk_level="LOW",
                            changes={
                                "content": {"old": old_content, "new": new_content},
                                "is_internal": {
                                    "old": old_is_internal,
                                    "new": comment.is_internal,
                                },
                            },
                        )

                        messages.success(request, "Comment updated successfully!")
                    else:
                        messages.error(
                            request, "You don't have permission to edit this comment."
                        )
                except Comment.DoesNotExist:
                    messages.error(request, "Comment not found.")
                return redirect("tickets:ticket_detail", ticket_id=ticket.id)
            else:
                messages.error(request, "Comment content is required.")

        elif action == "delete_comment":
            # Handle comment deletion
            comment_id = request.POST.get("comment_id")

            if comment_id:
                try:
                    comment = Comment.objects.get(id=comment_id, ticket=ticket)

                    # Check permissions: user can delete their own comments, admin can delete any
                    if comment.author == request.user or request.user.is_staff:
                        comment_content = comment.content  # Save for audit log
                        comment_author = comment.author.username

                        # Log the comment deletion for audit trail
                        audit_security_manager.log_audit_event(
                            request=request,
                            action="DELETE",
                            user=request.user,
                            object_type="Comment",
                            object_id=str(comment.id),
                            object_repr=f"Comment on Ticket #{ticket.id}",
                            description=f"Deleted comment by {comment_author} on Ticket #{ticket.id}: {ticket.title}",
                            risk_level="MEDIUM",
                            changes={"deleted_content": comment_content},
                        )

                        comment.delete()
                        messages.success(request, "Comment deleted successfully!")
                    else:
                        messages.error(
                            request, "You don't have permission to delete this comment."
                        )
                except Comment.DoesNotExist:
                    messages.error(request, "Comment not found.")
                return redirect("tickets:ticket_detail", ticket_id=ticket.id)

        elif action == "reopen_ticket":
            # Handle ticket reopening
            reopen_reason = request.POST.get("reopen_reason", "").strip()

            if reopen_reason:
                # Check if ticket is actually closed
                if ticket.status.lower() != "closed":
                    messages.error(
                        request, "This ticket is not closed and cannot be reopened."
                    )
                    return redirect("tickets:ticket_detail", ticket_id=ticket.id)

                # Create a comment with the reopening reason
                comment = Comment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=f"**Ticket Reopened**\n\nReason: {reopen_reason}",
                    is_internal=False,
                )

                # Change ticket status to Open
                old_status = ticket.status
                ticket.status = "Open"
                ticket._updated_by = request.user
                ticket.save()

                # Log the ticket reopening for audit trail
                audit_security_manager.log_audit_event(
                    request=request,
                    action="UPDATE",
                    user=request.user,
                    object_type="Ticket",
                    object_id=str(ticket.id),
                    object_repr=str(ticket),
                    description=f"Reopened Ticket #{ticket.id}: {ticket.title}",
                    risk_level="MEDIUM",
                    changes={
                        "status": {"old": old_status, "new": "Open"},
                        "reopen_reason": reopen_reason,
                    },
                )

                # Send reopened notification asynchronously
                from .email_utils import send_ticket_reopened_notification

                send_email_async(
                    send_ticket_reopened_notification,
                    ticket,
                    {
                        "status": {"old": old_status, "new": "Open"},
                        "reopen_reason": reopen_reason,
                    },
                    request.user,
                )

                messages.success(request, "Ticket has been reopened successfully!")
                return redirect("tickets:ticket_detail", ticket_id=ticket.id)
            else:
                messages.error(
                    request, "Please provide a reason for reopening the ticket."
                )

    # Get timeline entries (comments + updates) for the ticket
    timeline_entries = TicketUpdateService.get_timeline_entries(ticket)

    # Filter out internal comments for non-staff users
    if not request.user.is_staff:
        timeline_entries = [
            entry
            for entry in timeline_entries
            if entry["type"] != "comment" or not entry["content"].is_internal
        ]

    # Get related tickets using basic rule-based approach
    try:
        from .related_tickets import get_related_tickets_for_display

        related_tickets = get_related_tickets_for_display(ticket, request.user)
    except ImportError:
        related_tickets = []

    # Get user lists for admin controls
    staff_users = []
    admin_users = []
    regular_users = []

    if request.user.is_staff:
        staff_users = User.objects.filter(is_staff=True, is_active=True).order_by(
            "first_name", "last_name", "username"
        )
        admin_users = User.objects.filter(is_staff=True, is_active=True).order_by(
            "first_name", "last_name", "username"
        )
        regular_users = User.objects.filter(is_staff=False, is_active=True).order_by(
            "first_name", "last_name", "username"
        )

    context = {
        "ticket": ticket,
        "timeline_entries": timeline_entries,
        "related_tickets": related_tickets,
        "can_add_internal_comments": request.user.is_staff,
        "can_edit_ticket": (
            (ticket.created_by == request.user or request.user.is_staff)
            and (request.user.is_staff or ticket.status.lower() != "closed")
        ),
        "staff_users": staff_users,
        "admin_users": admin_users,
        "regular_users": regular_users,
    }
    return render(request, "tickets/ticket_detail.html", context)


@login_required
def create_ticket(request):
    """Create a new ticket with optional file attachments"""
    from .forms import TicketWithAttachmentsForm
    from .models import TicketAttachment
    from .async_email import send_email_async  # Use consistent async approach
    from .email_utils import send_ticket_created_notification

    if request.method == "POST":
        form = TicketWithAttachmentsForm(request.POST, request.FILES)

        if form.is_valid():
            # Create the ticket
            assigned_to = form.cleaned_data.get("assigned_to")
            ticket = Ticket.objects.create(
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                category=form.cleaned_data["category"],
                priority=form.cleaned_data["priority"],
                location=form.cleaned_data["location"],
                department=form.cleaned_data["department"],
                created_by=request.user,
                assigned_to=assigned_to if assigned_to else None,
            )

            # Link computer information to the ticket
            from .computer_utils import link_ticket_to_computer_info

            link_ticket_to_computer_info(ticket, request)

            # Save CC Admins and CC Non-Admins
            cc_admins = form.cleaned_data.get("cc_admins")
            cc_non_admins = form.cleaned_data.get("cc_non_admins")
            if cc_admins:
                ticket.cc_admins.set(cc_admins)
            if cc_non_admins:
                ticket.cc_non_admins.set(cc_non_admins)

            # Handle file attachments
            attachments = request.FILES.getlist("attachments")
            for attachment in attachments:
                if attachment:
                    TicketAttachment.objects.create(
                        ticket=ticket,
                        file=attachment,
                        original_filename=attachment.name,
                        uploaded_by=request.user,
                    )

            attachment_count = len([f for f in attachments if f])
            success_msg = f"Ticket #{ticket.id} created successfully!"
            if attachment_count > 0:
                success_msg += f' ({attachment_count} file{"s" if attachment_count > 1 else ""} attached)'

            # Send email notification asynchronously using threading
            # Send email notification asynchronously via queue
            send_email_async(send_ticket_created_notification, ticket)

            messages.success(request, success_msg)
            return redirect("tickets:ticket_detail", ticket_id=ticket.id)
        else:
            # Form has errors
            messages.error(request, "Please correct the errors below.")
    else:
        form = TicketWithAttachmentsForm()

    # Get categories for the form (cached for performance)
    categories = get_categories_cached()
    assignable_users = (
        User.objects.filter(is_staff=True)
        if (request.user.is_staff or request.user.is_superuser)
        else []
    )

    # Get admin and regular users for CC fields
    admin_users = (
        User.objects.filter(is_staff=True, is_active=True).order_by(
            "first_name", "last_name", "username"
        )
        if (request.user.is_staff or request.user.is_superuser)
        else []
    )
    regular_users = (
        User.objects.filter(is_staff=False, is_active=True).order_by(
            "first_name", "last_name", "username"
        )
        if (request.user.is_staff or request.user.is_superuser)
        else []
    )

    context = {
        "form": form,
        "admin_users": admin_users,
        "regular_users": regular_users,
        "categories": categories,
    }
    return render(request, "tickets/create_ticket.html", context)


def home(request):
    """Home page view with enhanced dashboard"""
    if request.user.is_authenticated:
        # Get comprehensive ticket statistics
        user_tickets = Ticket.objects.filter(
            Q(created_by=request.user)
            | Q(assigned_to=request.user)
            | Q(cc_admins=request.user)
            | Q(cc_non_admins=request.user)
        ).distinct()

        # Recent tickets (last 5)
        recent_tickets = user_tickets.order_by("-updated_at")[:5]

        # Ticket counts by status
        total_tickets = user_tickets.count()
        open_tickets = user_tickets.filter(status="Open").count()
        in_progress_tickets = user_tickets.filter(status="In Progress").count()
        closed_tickets = user_tickets.filter(status="Closed").count()

        # Get user profile info
        profile_info = {}
        if hasattr(request.user, "userprofile"):
            profile = request.user.userprofile
            profile_info = {
                "type": "Admin User" if request.user.is_staff else "Regular User",
                "role": profile.role or "Not Set",
                "location": profile.location or "Not Set",
                "department": profile.department or "Not Set",
            }
        else:
            profile_info = {
                "type": "Admin User" if request.user.is_staff else "Regular User",
                "role": "Not Set",
                "location": "Not Set",
                "department": "Not Set",
            }

        # Priority distribution for charts
        priority_stats = (
            Ticket.objects.values("priority")
            .annotate(count=Count("id"))
            .order_by("priority")
        )

        # Recent activity (this week - Monday to current day)
        today = timezone.now().date()
        # Get Monday of this week (0 = Monday, 6 = Sunday)
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)

        # Debug: week_start should be Monday of current week
        # Example: if today is Wednesday Sep 9, 2025, week_start should be Monday Sep 7, 2025

        new_this_week = Ticket.objects.filter(created_at__date__gte=week_start).count()
        closed_this_week = Ticket.objects.filter(
            status="Closed", closed_on__date__gte=week_start
        ).count()  # Add basic analytics calculations
        resolution_rate = (
            round((closed_tickets / total_tickets * 100), 2) if total_tickets > 0 else 0
        )

        # Simple weekly closure rate: closed this week / total tickets
        weekly_closure_rate = (
            round((closed_this_week / total_tickets * 100), 2)
            if total_tickets > 0
            else 0
        )

        # Also calculate same-week creation-to-closure rate for reference
        tickets_created_and_closed_this_week = Ticket.objects.filter(
            created_at__date__gte=week_start,
            status="Closed",
            closed_on__date__gte=week_start,
        ).count()

        # Alternative calculation: Overall closure efficiency this week
        # (tickets closed this week / total open tickets at start of week)
        total_open_before_week = Ticket.objects.filter(
            Q(status="Open") | Q(status="In Progress")
        ).count()

        weekly_activity_rate = (
            round(
                (closed_this_week / (total_open_before_week + new_this_week) * 100), 2
            )
            if (total_open_before_week + new_this_week) > 0
            else 0
        )

        # Simple analytics data structure
        analytics_data = {
            "totals": {
                "resolution_rate": resolution_rate,
            },
            "recent_activity": {
                "weekly_closure_rate": weekly_closure_rate,  # % of total tickets that were closed this week
                "tickets_created_and_closed_this_week": tickets_created_and_closed_this_week,
            },
            "performance": {
                "avg_first_response_hours": None,  # You can calculate this if needed
            },
        }

        # Most Active Users (this week)
        from django.db.models import Case, When, Value
        from django.contrib.auth.models import User

        # Get activity counts for each user in this week (Monday to current day)
        most_active_users = []

        # Count tickets created
        created_counts = (
            Ticket.objects.filter(created_at__date__gte=week_start)
            .values("created_by__email")
            .annotate(created_count=Count("id"))
            .exclude(created_by__email__isnull=True)
            .order_by()  # Clear default ordering to avoid GROUP BY issues
        )

        # Count comments made
        comment_counts = (
            Comment.objects.filter(created_at__date__gte=week_start)
            .values("author__email")
            .annotate(comment_count=Count("id"))
            .exclude(author__email__isnull=True)
            .order_by()  # Clear default ordering to avoid GROUP BY issues
        )

        # Count ticket updates/assignments
        update_counts = (
            Ticket.objects.filter(updated_at__date__gte=week_start)
            .values("assigned_to__email")
            .annotate(update_count=Count("id"))
            .exclude(assigned_to__email__isnull=True)
            .order_by()  # Clear default ordering to avoid GROUP BY issues
        )

        # Combine activity counts
        user_activity = {}

        for item in created_counts:
            email = item["created_by__email"]
            if email:
                user_activity[email] = (
                    user_activity.get(email, 0) + item["created_count"]
                )

        for item in comment_counts:
            email = item["author__email"]
            if email:
                user_activity[email] = (
                    user_activity.get(email, 0) + item["comment_count"]
                )

        for item in update_counts:
            email = item["assigned_to__email"]
            if email:
                user_activity[email] = (
                    user_activity.get(email, 0) + item["update_count"]
                )

        # Sort by activity and get top 5
        sorted_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[
            :4
        ]
        most_active_users = [
            {"email": email, "activity_count": count} for email, count in sorted_users
        ]

        context = {
            "recent_tickets": recent_tickets,
            "profile_info": profile_info,
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "in_progress_tickets": in_progress_tickets,
            "closed_tickets": closed_tickets,
            "total_users": User.objects.count(),
            "total_staff": User.objects.filter(is_staff=True).count(),
            "analytics_data": analytics_data,
            "priority_stats": list(priority_stats),
            "new_this_week": new_this_week,
            "closed_this_week": closed_this_week,
            "most_active_users": most_active_users,
            "week_start": week_start,  # Monday of current week
            "today": today,  # Current date
        }
    else:
        context = {}

    return render(request, "tickets/home.html", context)


def user_login(request):
    """Enhanced user login view with comprehensive audit trail"""
    if request.user.is_authenticated:
        return redirect("tickets:home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            messages.error(request, "Please provide both username and password.")
            return render(request, "tickets/login.html")

        # Enhanced security validation with audit trail
        validation_result = audit_security_manager.validate_login_with_audit(
            request, username, password
        )

        if validation_result["success"]:
            # Get the user and log them in
            user = authenticate(request, username=username, password=password)

            if user is not None and user.is_active:
                # Final security checks
                if "@" in username and not audit_security_manager.is_domain_allowed(
                    username
                ):
                    audit_security_manager.log_security_event(
                        event_type="UNAUTHORIZED_DOMAIN",
                        request=request,
                        user=user,
                        description=f"Login blocked: unauthorized domain {username}",
                        severity="HIGH",
                        success=False,
                        reason="Domain not authorized",
                    )
                    messages.error(request, "Domain not authorized for access.")
                    return render(request, "tickets/login.html")

                # Successful login
                login(request, user)

                # Log successful session creation (session created by signal)
                audit_security_manager.log_audit_event(
                    request=request,
                    action="LOGIN",
                    user=user,
                    description=f"User {username} logged in successfully",
                    risk_level="LOW",
                )

                messages.success(
                    request, f"Welcome back, {user.first_name or user.username}!"
                )

                # Security notification for suspicious login
                if validation_result.get("is_suspicious"):
                    messages.warning(
                        request, "This login has been flagged for security review."
                    )

                next_url = request.GET.get("next", "tickets:home")
                return redirect(next_url)

            elif user and not user.is_active:
                audit_security_manager.log_security_event(
                    event_type="LOGIN_BLOCKED",
                    request=request,
                    user=user,
                    description=f"Login blocked: inactive user {username}",
                    severity="MEDIUM",
                    success=False,
                    reason="Account is disabled",
                )
                messages.error(request, "Account is disabled. Contact administrator.")

        else:
            # Handle failed login
            error_message = validation_result.get(
                "message", "Invalid username or password."
            )

            # Add additional context for user
            if validation_result.get("locked"):
                error_message += f" Account locked for {validation_result.get('lockout_duration', 30)} minutes."
            elif validation_result.get("attempts_remaining", 0) > 0:
                attempts_left = validation_result.get("attempts_remaining", 0)
                if attempts_left <= 2:
                    error_message += f" {attempts_left} attempts remaining."

            messages.error(request, error_message)

    return render(request, "tickets/login.html")


def user_logout(request):
    """Enhanced user logout view with audit trail"""
    if request.user.is_authenticated:
        # Log the logout
        audit_security_manager.end_user_session(request, request.user)
        audit_security_manager.log_audit_event(
            request=request,
            action="LOGOUT",
            user=request.user,
            description=f"User {request.user.username} logged out",
            risk_level="LOW",
        )

        logout(request)
        messages.success(request, "You have been logged out successfully.")

    return redirect("tickets:login")


# ==================== SECURE FILE SERVING ====================

import os
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from .models import TicketAttachment


@login_required
def serve_protected_file(request, ticket_id, filename):
    """
    Serve protected ticket attachments with authentication and authorization checks.
    Only logged-in users who have access to the ticket can download its attachments.
    """
    try:
        # Get the ticket first to check permissions
        ticket = get_object_or_404(Ticket, id=ticket_id)

        # Check if user has permission to access this ticket
        if not user_can_access_ticket(request.user, ticket):
            # Log security event
            audit_security_manager.log_security_event(
                request=request,
                event_type="UNAUTHORIZED_FILE_ACCESS_ATTEMPT",
                user=request.user,
                description=f"User {request.user.username} attempted to access file {filename} from ticket {ticket_id} without permission",
                risk_level="MEDIUM",
            )
            return HttpResponseForbidden(
                "You don't have permission to access this file."
            )

        # Get the attachment record
        try:
            attachment = TicketAttachment.objects.get(
                ticket=ticket,
                file__icontains=filename,  # Use icontains to handle path variations
            )
        except TicketAttachment.DoesNotExist:
            raise Http404("File not found")

        # Construct the file path
        file_path = os.path.join(settings.MEDIA_ROOT, attachment.file.name)

        # Check if file actually exists
        if not os.path.exists(file_path):
            raise Http404("File not found on disk")

        # Log the file access
        audit_security_manager.log_audit_event(
            request=request,
            action="FILE_ACCESS",
            user=request.user,
            description=f"User {request.user.username} accessed file {filename} from ticket {ticket_id}",
            risk_level="LOW",
        )

        # Determine content type based on file extension
        if attachment.file_type == "PDF":
            content_type = "application/pdf"
        elif attachment.file_type == "IMAGE":
            # Determine image type
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".png":
                content_type = "image/png"
            elif ext == ".jpg" or ext == ".jpeg":
                content_type = "image/jpeg"
            elif ext == ".webp":
                content_type = "image/webp"
            else:
                content_type = "application/octet-stream"
        else:
            content_type = "application/octet-stream"

        # Return the file
        response = FileResponse(
            open(file_path, "rb"),
            content_type=content_type,
            filename=attachment.original_filename,
        )

        # Add headers for better security
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Disposition"] = (
            f'inline; filename="{attachment.original_filename}"'
        )

        return response

    except Exception as e:
        # Log the error
        audit_security_manager.log_security_event(
            request=request,
            event_type="FILE_ACCESS_ERROR",
            user=request.user if request.user.is_authenticated else None,
            description=f"Error accessing file {filename} from ticket {ticket_id}: {str(e)}",
            risk_level="HIGH",
        )
        raise Http404("File not found")


@login_required
def admin_all_tickets(request):
    """Admin-only view to display all tickets with pagination and CSV export"""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect("ticket_list")

    # Handle CSV export
    if request.GET.get("export") == "csv":
        return export_all_tickets_csv(request)

    # Get all tickets
    tickets = Ticket.objects.select_related(
        "created_by", "assigned_to", "category"
    ).order_by("-created_at")

    # Search functionality
    search_query = request.GET.get("search", "").strip()
    if search_query:
        tickets = tickets.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(created_by__username__icontains=search_query)
            | Q(created_by__email__icontains=search_query)
            | Q(assigned_to__username__icontains=search_query)
            | Q(id__icontains=search_query)
        )

    # Status filter
    status_filter = request.GET.get("status", "")
    if status_filter:
        tickets = tickets.filter(status=status_filter)

    # Priority filter
    priority_filter = request.GET.get("priority", "")
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)

    # Get counts for summary cards
    total_count = Ticket.objects.count()
    open_count = Ticket.objects.filter(status="Open").count()
    in_progress_count = Ticket.objects.filter(status="In Progress").count()
    closed_count = Ticket.objects.filter(status="Closed").count()
    urgent_count = Ticket.objects.filter(priority="Urgent").count()
    high_count = Ticket.objects.filter(priority="High").count()

    # Pagination
    paginator = Paginator(tickets, 25)  # 25 tickets per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "tickets": page_obj,
        "page_obj": page_obj,
        "total_count": total_count,
        "open_count": open_count,
        "in_progress_count": in_progress_count,
        "closed_count": closed_count,
        "urgent_count": urgent_count,
        "high_count": high_count,
        "search_query": search_query,
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "ticket_statuses": Ticket._meta.get_field("status").choices,
        "ticket_priorities": Ticket._meta.get_field("priority").choices,
    }

    return render(request, "tickets/admin_all_tickets.html", context)


def export_all_tickets_csv(request):
    """Export all tickets to CSV format"""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect("ticket_list")

    # Create HTTP response with CSV content type
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="all_tickets_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    )

    writer = csv.writer(response)

    # Write CSV header
    writer.writerow(
        [
            "Ticket ID",
            "Title",
            "Status",
            "Priority",
            "Category",
            "Created By",
            "Assignee",
            "Created Date",
            "Updated Date",
            "CC Admins",
            "CC Users",
            "Description",
        ]
    )

    # Get all tickets with related data
    tickets = (
        Ticket.objects.select_related("created_by", "assigned_to", "category")
        .prefetch_related("cc_admins", "cc_users")
        .order_by("-created_at")
    )

    # Apply same filters as the view if any
    search_query = request.GET.get("search", "").strip()
    if search_query:
        tickets = tickets.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(created_by__username__icontains=search_query)
            | Q(created_by__email__icontains=search_query)
            | Q(assigned_to__username__icontains=search_query)
            | Q(id__icontains=search_query)
        )

    status_filter = request.GET.get("status", "")
    if status_filter:
        tickets = tickets.filter(status=status_filter)

    priority_filter = request.GET.get("priority", "")
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)

    # Write ticket data
    for ticket in tickets:
        cc_admins = ", ".join([admin.username for admin in ticket.cc_admins.all()])
        cc_users = ", ".join([user.username for user in ticket.cc_users.all()])

        writer.writerow(
            [
                ticket.id,
                ticket.title,
                ticket.get_status_display(),
                ticket.get_priority_display(),
                ticket.category.name if ticket.category else "",
                ticket.created_by.username,
                ticket.assigned_to.username if ticket.assigned_to else "",
                ticket.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                ticket.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                cc_admins,
                cc_users,
                ticket.description[:500]
                + (
                    "..." if len(ticket.description) > 500 else ""
                ),  # Truncate long descriptions
            ]
        )

    return response
