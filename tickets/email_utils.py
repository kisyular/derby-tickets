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


sending_email_in_test = True  # Set to True to always send to test email


def send_email(
    subject: str,
    html_body: str,
    recipients: List[str] = None,
    in_test: bool = True,
    attachment_files: list = None,
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
            print(f"If it was not a test email, it would be sent to: {recipients}")
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

        # Attach files if provided
        import tempfile, shutil

        temp_files = []
        if attachment_files:
            print(f"Attaching files: {attachment_files}")
            for attach in attachment_files:
                file_name = None
                file_path = None
                # attach can be a tuple (file_path, file_name) or just a path
                if isinstance(attach, tuple):
                    file_path, file_name = attach
                else:
                    file_path = attach
                    file_name = os.path.basename(file_path)
                # If file_path exists locally, attach directly
                if os.path.exists(file_path):
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition", f"attachment; filename={file_name}"
                        )
                        msg.attach(part)
                else:
                    # Try to download remote file to temp and attach
                    try:
                        from django.core.files.storage import default_storage

                        with default_storage.open(file_path, "rb") as remote_file:
                            tmp = tempfile.NamedTemporaryFile(delete=False)
                            shutil.copyfileobj(remote_file, tmp)
                            tmp.close()
                            temp_files.append(tmp.name)
                            with open(tmp.name, "rb") as attachment:
                                part = MIMEBase("application", "octet-stream")
                                part.set_payload(attachment.read())
                                encoders.encode_base64(part)
                                part.add_header(
                                    "Content-Disposition",
                                    f"attachment; filename={file_name}",
                                )
                                msg.attach(part)
                    except Exception as e:
                        print(f"Failed to attach remote file: {file_path} ({e})")

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
            # Clean up temp files
            for tmpf in temp_files:
                try:
                    os.remove(tmpf)
                except Exception:
                    pass
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
        "greeting_name": first_name if first_name else user.username,
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

    # Attach all files if any attachments exist
    attachment_files = []
    if hasattr(ticket, "attachments"):
        all_attachments = list(ticket.attachments.all())
        print(f"Ticket {ticket.id} attachments found: {len(all_attachments)}")
        for att in all_attachments:
            print(
                f"Attachment id={att.id}, file={att.file}, file.name={getattr(att.file, 'name', None)}, file.path={getattr(att.file, 'path', None)}, original_filename={att.original_filename}"
            )
            if att.file:
                # Use (file_path, original_filename) for correct naming
                if hasattr(att.file, "path") and os.path.exists(att.file.path):
                    attachment_files.append((att.file.path, att.original_filename))
                else:
                    # For remote storage, use att.file.name (storage path)
                    attachment_files.append((att.file.name, att.original_filename))
    print(f"attachment_files to send: {attachment_files}")

    return send_email(
        subject=subject,
        html_body=html_body,
        recipients=admin_emails,
        in_test=sending_email_in_test,
        attachment_files=attachment_files,
    )


def send_ticket_assigned_notification(ticket):
    """Send notification when a ticket is assigned to an admin and CCs."""
    recipients = []
    # Assigned user
    if ticket.assigned_to and ticket.assigned_to.email:
        recipients.append(ticket.assigned_to.email)
    # CC Admins
    cc_admins = ticket.cc_admins.all()
    recipients += [u.email for u in cc_admins if u.email]
    # CC Non-Admins
    cc_non_admins = ticket.cc_non_admins.all()
    recipients += [u.email for u in cc_non_admins if u.email]
    # Remove duplicates
    recipients = list(set(recipients))
    if not recipients:
        print("No recipients for ticket assignment notification")
        return False

    # Prepare context with fallback values
    context = {
        "ticket": prepare_ticket_context(ticket),
        "assigned_user": prepare_user_context(ticket.assigned_to),
        "ticket_creator": prepare_user_context(ticket.created_by),
        "site_url": os.environ.get("DJANGO_SITE_URL", "http://127.0.0.1:8000"),
    }

    # Render HTML email template
    html_body = render_to_string("emails/ticket_assigned.html", context)

    subject = f"Ticket Assigned: #{context['ticket']['ticket_number']} - {ticket.title}"

    return send_email(
        subject=subject,
        html_body=html_body,
        recipients=recipients,
        in_test=sending_email_in_test,
    )


def send_comment_notification(comment, ticket):
    """Send notification when a comment is added to a ticket."""
    # Prepare base context with fallback values
    base_context = {
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
    # Determine who should receive the notification and send personalized email
    recipient_users = set()
    if comment.author == ticket.created_by:
        if ticket.assigned_to and ticket.assigned_to.email:
            recipient_users.add(ticket.assigned_to)
    elif comment.author == ticket.assigned_to:
        if ticket.created_by.email:
            recipient_users.add(ticket.created_by)
    else:
        if ticket.created_by.email and comment.author != ticket.created_by:
            recipient_users.add(ticket.created_by)
        if (
            ticket.assigned_to
            and ticket.assigned_to.email
            and comment.author != ticket.assigned_to
        ):
            recipient_users.add(ticket.assigned_to)
    # Add all CC Admins and CC Non-Admins
    recipient_users.update(ticket.cc_admins.all())
    recipient_users.update(ticket.cc_non_admins.all())
    # Remove the author if present
    if comment.author in recipient_users:
        recipient_users.remove(comment.author)
    if not recipient_users:
        print("No recipients for comment notification")
        return False

    success = True
    for recipient in recipient_users:
        context = dict(base_context)
        context["recipient"] = prepare_user_context(recipient)
        html_body = render_to_string("emails/comment_added.html", context)
        subject = f"New Comment on Ticket #{context['ticket']['ticket_number']} - {ticket.title}"
        result = send_email(
            subject=subject,
            html_body=html_body,
            recipients=[recipient.email],
            in_test=sending_email_in_test,
        )
        if not result:
            success = False
    return success


def send_ticket_updated_notification(ticket, changed_fields, updated_by):
    """Send notification when ticket priority or status is updated."""
    if set(changed_fields.keys()) == {"assigned_to"}:
        return False

    recipients = set()
    if updated_by.is_staff:
        if ticket.created_by.email and updated_by != ticket.created_by:
            recipients.add(ticket.created_by.email)
        # Add assigned_to if updated_by is not assigned_to
        if (
            ticket.assigned_to
            and ticket.assigned_to.email
            and updated_by != ticket.assigned_to
        ):
            recipients.add(ticket.assigned_to.email)
    else:
        if (
            ticket.assigned_to
            and ticket.assigned_to.email
            and updated_by != ticket.assigned_to
        ):
            recipients.add(ticket.assigned_to.email)
    # Add all CC Admins and CC Non-Admins
    recipients.update([u.email for u in ticket.cc_admins.all() if u.email])
    recipients.update([u.email for u in ticket.cc_non_admins.all() if u.email])
    if not recipients:
        print("No recipients for ticket update notification")
        return False

    context = {
        "ticket": prepare_ticket_context(ticket),
        "changed_fields": changed_fields,
        "updated_by": prepare_user_context(updated_by),
        "ticket_creator": prepare_user_context(ticket.created_by),
        "site_url": os.environ.get("DJANGO_SITE_URL", "http://127.0.0.1:8000"),
    }

    html_body = render_to_string("emails/ticket_updated.html", context)
    subject = f"Ticket Updated: #{context['ticket']['ticket_number']} - {ticket.title}"

    return send_email(
        subject=subject,
        html_body=html_body,
        recipients=list(recipients),
        in_test=sending_email_in_test,
    )


# if the field cc_admins and cc_non_admin changes, we email the new people
def send_ticket_cc_updated_notification(ticket, new_cc_admins, new_cc_non_admins):
    """Send notification when ticket CC Admins or CC Non-Admins are updated."""
    # Convert QuerySets to lists and get all new users
    all_new_users = list(new_cc_admins) + list(new_cc_non_admins)

    print(f"DEBUG: send_ticket_cc_updated_notification called with:")
    print(f"  new_cc_admins: {new_cc_admins} (type: {type(new_cc_admins)})")
    print(f"  new_cc_non_admins: {new_cc_non_admins} (type: {type(new_cc_non_admins)})")
    print(f"  all_new_users: {[str(u) for u in all_new_users]}")

    if not all_new_users:
        print("No new CC recipients for ticket CC update notification")
        return False

    # Prepare base context
    base_context = {
        "ticket": prepare_ticket_context(ticket),
        "ticket_creator": prepare_user_context(ticket.created_by),
        "assigned_user": prepare_user_context(ticket.assigned_to),
        "site_url": os.environ.get("DJANGO_SITE_URL", "http://127.0.0.1:8000"),
    }

    success = True
    for user in all_new_users:
        # print(f"DEBUG: Processing user {user} (email: {user.email})")
        if user.email:
            # Create personalized context for each recipient
            context = dict(base_context)
            user_context = prepare_user_context(user)
            context["recipient"] = user_context
            # For CC notifications, use the CC user as the "assigned_user" in template
            context["assigned_user"] = user_context

            # print(f"DEBUG: User context for {user}: {user_context}")

            html_body = render_to_string("emails/ticket_assigned.html", context)
            subject = f"Ticket Assigned to You : #{context['ticket']['ticket_number']} - {ticket.title}"

            result = send_email(
                subject=subject,
                html_body=html_body,
                recipients=[user.email],
                in_test=sending_email_in_test,
            )
            if not result:
                success = False
        else:
            # print(f"DEBUG: User {user} has no email address")
            pass

    return success
