from django.core.management.base import BaseCommand
import pandas as pd
from datetime import datetime
import pytz
from django.db import transaction
from django.contrib.auth.models import User
from tickets.models import Ticket, UserProfile, Category
from django.db.models.signals import post_save
from tickets.signals import ticket_saved
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

# clean the created by and assigned to columns
"""
Jeffrey Land -> Jeff Land
Jason Carr -> Jason Carrier
"""


class Command(BaseCommand):
    # Name cleaning map for known corrections
    NAME_CLEAN_MAP = {
        "Jeffrey Land": "Jeff Land",
        "Jason Carr": "Jason Carrier",
    }
    help = "Load ticket data from CSV file using pandas"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to the CSV file")
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Clean existing tickets before loading",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing tickets instead of skipping them",
        )
        parser.add_argument(
            "--send-one-email",
            action="store_true",
            help="Send a single summary email to admin after loading",
        )
        parser.add_argument(
            "--send-all-emails",
            action="store_true",
            help="Send individual emails for each ticket created (default is no emails)",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        clean_first = options["clean"]
        update_existing = options["update_existing"]
        send_one_email = options["send_one_email"]
        send_all_emails = options["send_all_emails"]

        # Track results for summary
        results = {
            "success_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "errors": [],
            "warnings": [],
        }

        # Disconnect email signals unless explicitly requested
        if not send_all_emails:
            self.stdout.write("Disabling email notifications during bulk loading...")
            post_save.disconnect(ticket_saved, sender=Ticket)

        if clean_first:
            self.stdout.write("Cleaning existing tickets...")
            with transaction.atomic():
                ticket_count = Ticket.objects.count()
                Ticket.objects.all().delete()
                self.stdout.write(f"Deleted {ticket_count} existing tickets")

        self.stdout.write(f"Loading tickets from {csv_file}...")

        try:
            success_count, updated_count, skipped_count = self.load_tickets_from_csv(
                csv_file, results, update_existing
            )
            results["success_count"] = success_count
            results["updated_count"] = updated_count
            results["skipped_count"] = skipped_count

            # Send summary email if requested
            if send_one_email:
                self.send_summary_email(results)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully processed {success_count + updated_count + skipped_count} tickets: "
                    f"{success_count} created, {updated_count} updated, {skipped_count} skipped"
                )
            )

            if results["errors"]:
                self.stdout.write(
                    self.style.WARNING(
                        f'Encountered {len(results["errors"])} errors during loading'
                    )
                )

        except Exception as e:
            results["errors"].append(f"Critical error: {str(e)}")
            self.stdout.write(self.style.ERROR(f"Error loading tickets: {str(e)}"))
        finally:
            # Reconnect signals
            if not send_all_emails:
                self.stdout.write("Re-enabling email notifications...")
                post_save.connect(ticket_saved, sender=Ticket)

    def parse_datetime(self, date_str):
        """Parse datetime strings from the CSV with various formats."""
        if pd.isna(date_str) or not date_str or date_str.strip() == "":
            return None

        # Clean the date string
        date_str = str(date_str).strip()

        # Common formats in the CSV
        formats = [
            "%m/%d/%Y %I:%M %p UTC",  # 11/3/2022 1:37 pm UTC
            "%m/%d/%Y %I:%M:%S %p UTC",  # 11/3/2022 1:37:45 pm UTC
            "%m/%d/%Y %H:%M UTC",  # 11/3/2022 13:37 UTC
            "%m/%d/%Y %H:%M:%S UTC",  # 11/3/2022 13:37:45 UTC
            "%m/%d/%Y",  # 11/3/2022
            "%Y-%m-%d %H:%M:%S",  # Standard format
            "%Y-%m-%d",  # Date only
        ]

        for fmt in formats:
            try:
                # Handle timezone
                if "UTC" in date_str:
                    dt = datetime.strptime(date_str, fmt)
                    dt = pytz.UTC.localize(dt) if dt.tzinfo is None else dt
                else:
                    dt = datetime.strptime(date_str, fmt)
                    # Assume UTC if no timezone specified
                    dt = pytz.UTC.localize(dt) if dt.tzinfo is None else dt
                return dt
            except ValueError:
                continue

        self.stdout.write(f"Warning: Could not parse date: {date_str}")
        return None

    def find_or_create_category(self, category_name, results):
        """Find an existing category by name or create 'Other' as fallback."""
        if not category_name or pd.isna(category_name):
            # Return 'Other' category as default
            try:
                return Category.objects.get(name="Other")
            except Category.DoesNotExist:
                results["warnings"].append("'Other' category not found, creating it...")
                other_category = Category(name="Other")
                other_category.save(use_auto_now=False)  # Use current timestamp
                return other_category

        category_name = str(category_name).strip()

        # Try to find exact match first
        try:
            return Category.objects.get(name=category_name)
        except Category.DoesNotExist:
            # Try case-insensitive match
            try:
                return Category.objects.get(name__iexact=category_name)
            except Category.DoesNotExist:
                # If not found, return 'Other' category
                results["warnings"].append(
                    f"Category '{category_name}' not found, using 'Other'"
                )
                try:
                    return Category.objects.get(name="Other")
                except Category.DoesNotExist:
                    results["warnings"].append(
                        "'Other' category not found, creating it..."
                    )
                    other_category = Category(name="Other")
                    other_category.save(use_auto_now=False)
                    return other_category

    def find_or_create_user(
        self, name, department=None, location=None, results=None, make_staff=False
    ):
        """Find or create a user by name, handling various name formats."""
        if pd.isna(name) or not name or str(name).strip() == "":
            return None

        name = str(name).strip()

        # Handle email addresses first
        if "@" in name:
            email = name.lower()
            username = email.split("@")[0]

            # Try to find user by email
            try:
                user = User.objects.get(email=email)
                # If user exists but needs to be staff and isn't, update them
                if make_staff and not user.is_staff:
                    user.is_staff = True
                    user.save()
                return user
            except User.DoesNotExist:
                # Try to find by username
                try:
                    user = User.objects.get(username=username)
                    # If user exists but needs to be staff and isn't, update them
                    if make_staff and not user.is_staff:
                        user.is_staff = True
                        user.save()
                    return user
                except User.DoesNotExist:
                    # Create new user
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        first_name=username.title(),
                        last_name="",
                        is_staff=make_staff,  # Set staff status based on parameter
                    )

                    # Create UserProfile using get_or_create to avoid duplicates
                    UserProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            "department": department or "",
                            "location": location or "",
                        },
                    )

                    return user

        # Handle regular names
        # Try to find existing user by first/last name combination
        name_parts = name.split()
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:])

            try:
                # If multiple users found, return the first one
                users = User.objects.filter(
                    first_name__iexact=first_name, last_name__iexact=last_name
                )
                if users.exists():
                    if users.count() > 1:
                        warning_msg = f"Multiple users found for '{name}', using first match: {users.first().username}"
                        if results:
                            results["warnings"].append(warning_msg)
                        else:
                            self.stdout.write(f"Warning: {warning_msg}")
                    user = users.first()
                    # If user exists but needs to be staff and isn't, update them
                    if make_staff and not user.is_staff:
                        user.is_staff = True
                        user.save()
                    return user
            except User.DoesNotExist:
                pass

        # Try to find by username (first initial + last name @derbyfab.com)
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = name_parts[-1]
            base = (first_name[0] + last_name).lower()
            username = f"{base}@derbyfab.com"
            email = username
        else:
            # Fallback: use name as base
            base = name.replace(" ", "").lower()
            username = f"{base}@derbyfab.com"
            email = username
        try:
            user = User.objects.get(username=username)
            if make_staff and not user.is_staff:
                user.is_staff = True
                user.save()
            return user
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=name_parts[0] if name_parts else name,
                last_name=" ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                is_staff=make_staff,
            )
            UserProfile.objects.get_or_create(
                user=user,
                defaults={"department": department or "", "location": location or ""},
            )
            return user

    def load_tickets_from_csv(self, csv_file, results, update_existing=False):
        """Load tickets from CSV file."""
        # Read CSV with pandas
        df = pd.read_csv(csv_file)

        success_count = 0
        updated_count = 0
        skipped_count = 0

        # Process each row individually with its own transaction

        for index, row in df.iterrows():
            try:
                with transaction.atomic():  # Individual transaction per row
                    # Extract data from row
                    ticket_number = (
                        row.get("Ticket Number")
                        or row.get("Ticket ID")
                        or row.get("ID")
                    )
                    title = (
                        row.get("Summary") or row.get("Subject") or row.get("Title", "")
                    )
                    description = row.get("Description", "")
                    priority = (
                        row.get("Priority", "Medium").lower().capitalize()
                    )  # Normalize case
                    status = (
                        row.get("Status", "Open").lower().capitalize()
                    )  # Normalize case
                    category_name = row.get("Category")
                    created_by_name = row.get("Created By") or row.get("Reporter")
                    assigned_to_name = row.get("Assigned To")
                    # Clean names if needed
                    if created_by_name in self.NAME_CLEAN_MAP:
                        created_by_name = self.NAME_CLEAN_MAP[created_by_name]
                    if assigned_to_name in self.NAME_CLEAN_MAP:
                        assigned_to_name = self.NAME_CLEAN_MAP[assigned_to_name]
                    created_at_str = (
                        row.get("Created On")
                        or row.get("Created At")
                        or row.get("Created")
                    )
                    closed_at_str = (
                        row.get("Closed On")
                        or row.get("Closed At")
                        or row.get("Closed")
                    )
                    department = row.get("Department", "")
                    location = row.get("Location", "")

                    # Check if ticket already exists (skip duplicates)
                    existing_ticket = None
                    if ticket_number:
                        ticket_number = str(ticket_number).strip()
                        try:
                            existing_ticket = Ticket.objects.get(
                                ticket_number=ticket_number
                            )
                            if update_existing:
                                self.stdout.write(
                                    f"Updating existing ticket #{ticket_number}..."
                                )
                            else:
                                results["warnings"].append(
                                    f"Row {index}: Ticket #{ticket_number} already exists, skipping"
                                )
                                skipped_count += 1
                                continue
                        except Ticket.DoesNotExist:
                            pass  # Ticket doesn't exist, we can create it

                    # Parse dates
                    created_at = self.parse_datetime(created_at_str)
                    closed_at = (
                        self.parse_datetime(closed_at_str) if closed_at_str else None
                    )

                    # Find or create users
                    created_by = self.find_or_create_user(
                        created_by_name, department, location, results, make_staff=False
                    )
                    assigned_to = self.find_or_create_user(
                        assigned_to_name, department, location, results, make_staff=True
                    )

                    # Find or create category
                    category = self.find_or_create_category(category_name, results)

                    # Validate priority and status
                    valid_priorities = ["Low", "Medium", "High", "Urgent"]
                    if priority not in valid_priorities:
                        results["warnings"].append(
                            f"Row {index}: Invalid priority '{priority}', using 'Medium'"
                        )
                        priority = "Medium"

                    valid_statuses = ["Open", "In Progress", "Closed"]
                    if status not in valid_statuses:
                        results["warnings"].append(
                            f"Row {index}: Invalid status '{status}', using 'Open'"
                        )
                        status = "Open"

                    # Create or update ticket
                    if existing_ticket:
                        # Update existing ticket
                        ticket = existing_ticket
                        ticket.title = title[:200]
                        ticket.description = description
                        ticket.priority = priority
                        ticket.status = status
                        ticket.category = category
                        ticket.assigned_to = assigned_to
                        ticket.department = department
                        ticket.location = location
                        ticket.closed_on = closed_at

                        # Update created_at if available and not already set
                        if created_at and not ticket.created_at:
                            ticket.created_at = created_at

                        ticket.save(use_auto_now=False)
                        updated_count += 1
                    else:
                        # Create new ticket
                        ticket = Ticket(
                            ticket_number=ticket_number,  # Use CSV ticket number
                            title=title[:200],  # Limit title length
                            description=description,
                            priority=priority,
                            status=status,
                            category=category,
                            created_by=created_by,
                            assigned_to=assigned_to,
                            department=department,
                            location=location,
                            closed_on=closed_at,
                        )

                        # Set created_at if available
                        if created_at:
                            ticket.created_at = created_at

                        ticket.save(use_auto_now=False)
                        success_count += 1

                    if (success_count + updated_count) % 100 == 0:
                        self.stdout.write(
                            f"Processed {success_count + updated_count} tickets..."
                        )

            except Exception as e:
                error_msg = f"Row {index}: {str(e)}"
                results["errors"].append(error_msg)
                self.stdout.write(f"Error processing row {index}: {str(e)}")
                continue

        return success_count, updated_count, skipped_count

    def send_summary_email(self, results):
        """Send summary email to admin about the bulk ticket loading."""
        try:
            admin_email = getattr(settings, "DJANGO_ADMIN_EMAIL", None)
            if not admin_email:
                admin_email = getattr(
                    settings, "DEFAULT_FROM_EMAIL", "derfabit@derbyfab.com"
                )

            total_processed = (
                results["success_count"]
                + results.get("updated_count", 0)
                + results.get("skipped_count", 0)
            )
            subject = (
                f"Bulk Ticket Import Summary - {total_processed} tickets processed"
            )

            # Create email content
            message = f"""
                        Bulk Ticket Import Summary
                        ==========================
                        
                        Total processed: {total_processed} tickets
                        - Created: {results['success_count']} tickets
                        - Updated: {results.get('updated_count', 0)} tickets  
                        - Skipped: {results.get('skipped_count', 0)} tickets
                        """

            if results["warnings"]:
                message += f"""
                            Warnings ({len(results['warnings'])}):
                            {chr(10).join([f"- {warning}" for warning in results['warnings']])}
                            """

            if results["errors"]:
                message += f"""
                            Errors ({len(results['errors'])}):
                            {chr(10).join([f"- {error}" for error in results['errors']])}
                            """

            message += """
                        Import completed successfully.
                        
                        This is an automated message from the Django Ticket System.
                        """

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_email],
                fail_silently=False,
            )

            self.stdout.write(f"Summary email sent to: {admin_email}")

        except Exception as e:
            self.stdout.write(f"Failed to send summary email: {str(e)}")
