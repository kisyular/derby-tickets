import smtplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Any, List
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.conf import settings
from .logging_utils import log_email_sent, log_system_event, performance_monitor


def send_email(
    subject: str,
    html_body: str,
    recipients: List[str] = None,
    in_test: bool = True,
    attachment_file: str = None,
) -> bool:
    """
    Send an HTML email to recipients.

    Args:
        subject: Email subject
        html_body: HTML email body
        recipients: List of email addresses to send to
        in_test: If True, send to test email only
        attachment_file: Optional file to attach

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    start_time = time.time()

    try:
        # Set up the SMTP server
        smtp_server = os.environ.get("DJANGO_EMAIL_HOST")
        smtp_port = int(os.environ.get("DJANGO_EMAIL_PORT", 587))
        email_send_as = os.environ.get("DJANGO_EMAIL_HOST_USER")
        email_sender = os.environ.get("DJANGO_EMAIL_HOST_USER")
        sender_pw = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD")

        # Priority order: in_test > custom_recipients
        if in_test:
            # Test mode: always send to test email only
            to_emails = [os.environ.get("DJANGO_TEST_EMAIL")]
            print(f"[TEST MODE] Sending email to: {to_emails}")
        elif recipients:
            # Use provided recipient list
            to_emails = recipients
            print(f"[PRODUCTION MODE] Sending email to: {to_emails}")
        else:
            print("No recipients provided")
            return False

        # Create a multipart email message
        msg = MIMEMultipart()
        msg["To"] = ", ".join(to_emails)
        msg["From"] = email_send_as
        msg["Subject"] = subject

        # Attach the email body
        msg.attach(MIMEText(html_body, "html"))

        # Attach a file if provided
        if attachment_file and os.path.exists(attachment_file):
            file_name = os.path.basename(attachment_file)
            with open(attachment_file, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition", f"attachment; filename={file_name}"
                )
                msg.attach(part)

        # Send the email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_sender, sender_pw)
            server.sendmail(email_sender, to_emails, msg.as_string())

            duration = time.time() - start_time
            print(f"Email sent successfully! Duration: {duration:.2f}s")
            print(f"Subject: {subject}")
            print(f'Recipients: {", ".join(to_emails)}')

            # Log successful email sending
            for recipient in to_emails:
                log_email_sent(recipient, subject, success=True)

            return True

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        print(f"Failed to send email after {duration:.2f}s: {e}")
        print(f"Subject: {subject}")
        print(
            f'Attempted recipients: {recipients if not in_test else [os.environ.get("DJANGO_TEST_EMAIL")]}'
        )

        # Log failed email sending
        for recipient in to_emails:
            log_email_sent(recipient, subject, success=False, error=error_msg)

        log_system_event("EMAIL_ERROR", f"Failed to send email: {error_msg}", "ERROR")
        return False


def get_admin_emails() -> List[str]:
    """Get email addresses of all staff users."""
    admin_users = User.objects.filter(is_staff=True, email__isnull=False).exclude(
        email=""
    )
    return [user.email for user in admin_users if user.email]


def prepare_user_context(user):
    """Prepare user context with fallback values."""
    if not user:
        return {
            "name": "Unknown User",
            "username": "unknown",
            "greeting_name": "Unknown User",
            "email": "",
        }

    full_name = user.get_full_name().strip() if user.get_full_name() else ""
    first_name = user.first_name.strip() if user.first_name else ""

    return {
        "name": full_name if full_name else user.username,
        "username": user.username,
        "email": user.email or "",
        "greeting_name": (
            first_name if first_name else (full_name if full_name else user.username)
        ),
    }


def prepare_ticket_context(ticket):
    """Prepare ticket context with fallback values."""
    return {
        "id": ticket.id,
        "ticket_number": (
            ticket.ticket_number if ticket.ticket_number else str(ticket.id)
        ),
        "title": ticket.title,
        "description": (
            ticket.description if ticket.description else "No description provided"
        ),
        "priority": ticket.priority,
        "priority_display": ticket.get_priority_display(),
        "priority_lower": ticket.priority.lower() if ticket.priority else "medium",
        "status": ticket.status,
        "status_display": ticket.get_status_display(),
        "category_name": ticket.category.name if ticket.category else "Uncategorized",
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "raw_ticket": ticket,  # Keep the original for any other needs
    }


def send_ticket_created_notification(ticket):
    """Send notification when a new ticket is created."""
    admin_emails = get_admin_emails()

    if not admin_emails:
        print("No admin emails found for ticket creation notification")
        return False

    # Prepare context with fallback values
    context = {
        "ticket": prepare_ticket_context(ticket),
        "creator": prepare_user_context(ticket.created_by),
        "site_url": os.environ.get("DJANGO_SITE_URL", "http://127.0.0.1:8000"),
    }

    # Render HTML email template
    html_body = render_to_string("emails/ticket_created.html", context)

    subject = (
        f"New Ticket Created: #{context['ticket']['ticket_number']} - {ticket.title}"
    )

    return send_email(
        subject=subject,
        html_body=html_body,
        recipients=admin_emails,
        in_test=True,  # Change to False in production
    )


def send_ticket_assigned_notification(ticket):
    """Send notification when a ticket is assigned to an admin."""
    if not ticket.assigned_to or not ticket.assigned_to.email:
        print("No assigned user or email for ticket assignment notification")
        return False

    # Prepare context with fallback values
    context = {
        "ticket": prepare_ticket_context(ticket),
        "assigned_user": prepare_user_context(ticket.assigned_to),
        "creator": prepare_user_context(ticket.created_by),
        "site_url": os.environ.get("DJANGO_SITE_URL", "http://127.0.0.1:8000"),
    }

    # Render HTML email template
    html_body = render_to_string("emails/ticket_assigned.html", context)

    subject = f"Ticket Assigned to You: #{context['ticket']['ticket_number']} - {ticket.title}"

    return send_email(
        subject=subject,
        html_body=html_body,
        recipients=[ticket.assigned_to.email],
        in_test=True,  # Change to False in production
    )


def send_comment_notification(comment, ticket):
    """Send notification when a comment is added to a ticket."""
    # Prepare context with fallback values
    context = {
        "ticket": prepare_ticket_context(ticket),
        "comment": {
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at,
        },
        "author": prepare_user_context(comment.author),
        "ticket_creator": prepare_user_context(ticket.created_by),
        "ticket_assigned": prepare_user_context(ticket.assigned_to),
        "site_url": os.environ.get("DJANGO_SITE_URL", "http://127.0.0.1:8000"),
    }

    print("This ticket was commented on by:", comment.author)
    print("This ticket was created by:", ticket.created_by)
    print("This ticket is assigned to:", ticket.assigned_to)

    # Determine who should receive the notification
    if comment.author == ticket.created_by:
        # Creator commented - notify assigned admin if exists
        if ticket.assigned_to and ticket.assigned_to.email:
            recipients = [ticket.assigned_to.email]
        else:
            print("No assigned admin to notify for creator's comment")
            return False
    elif comment.author == ticket.assigned_to:
        # Admin commented - notify creator
        if ticket.created_by.email:
            recipients = [ticket.created_by.email]
        else:
            print("No creator email to notify for admin's comment")
            return False
    else:
        # Other user commented - notify both creator and assigned admin if different
        recipients = []
        if ticket.created_by.email and comment.author != ticket.created_by:
            recipients.append(ticket.created_by.email)
        if (
            ticket.assigned_to
            and ticket.assigned_to.email
            and comment.author != ticket.assigned_to
        ):
            recipients.append(ticket.assigned_to.email)

        if not recipients:
            print("No recipients for comment notification")
            return False

    # Render HTML email template
    html_body = render_to_string("emails/comment_added.html", context)
    subject = (
        f"New Comment on Ticket #{context['ticket']['ticket_number']} - {ticket.title}"
    )

    return send_email(
        subject=subject,
        html_body=html_body,
        recipients=recipients,
        in_test=True,  # Change to False in production
    )


def send_ticket_updated_notification(ticket, changed_fields, updated_by):
    """Send notification when ticket priority or status is updated."""
    # Determine recipients based on who made the change
    recipients = []

    if updated_by.is_staff:
        # Admin made the change - notify creator
        if ticket.created_by.email and updated_by != ticket.created_by:
            recipients.append(ticket.created_by.email)
    else:
        # Creator made the change - notify assigned admin
        if (
            ticket.assigned_to
            and ticket.assigned_to.email
            and updated_by != ticket.assigned_to
        ):
            recipients.append(ticket.assigned_to.email)

    if not recipients:
        print("No recipients for ticket update notification")
        return False

    # Prepare context with fallback values
    context = {
        "ticket": prepare_ticket_context(ticket),
        "changed_fields": changed_fields,
        "updated_by": prepare_user_context(updated_by),
        "site_url": os.environ.get("DJANGO_SITE_URL", "http://127.0.0.1:8000"),
    }

    # Render HTML email template
    html_body = render_to_string("emails/ticket_updated.html", context)
    subject = f"Ticket Updated: #{context['ticket']['ticket_number']} - {ticket.title}"

    return send_email(
        subject=subject,
        html_body=html_body,
        recipients=recipients,
        in_test=True,  # Change to False in production
    )
