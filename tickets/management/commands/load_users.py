from django.core.management.base import BaseCommand
import pandas as pd
from django.db import transaction
from django.contrib.auth.models import User
from tickets.models import UserProfile
from django.contrib.auth.hashers import make_password


class Command(BaseCommand):
    help = "Load user data from CSV file using pandas"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to the CSV file")
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Clean existing users before loading (WARNING: This will delete all users except superusers)",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing users instead of skipping them",
        )
        parser.add_argument(
            "--use-passwords",
            action="store_true",
            help="Use passwords from CSV (default: set all passwords to 'password123')",
        )
        parser.add_argument(
            "--superusers",
            nargs="*",
            default=[],
            help="Email addresses of users who should be superusers (e.g. --superusers rkisyula@derbyfab.com jland@derbyfab.com)",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        clean_first = options["clean"]
        update_existing = options["update_existing"]
        use_passwords = options["use_passwords"]
        # Support comma-separated or space-separated emails for --superusers
        superuser_emails = []
        for entry in options["superusers"]:
            if "," in entry:
                superuser_emails.extend(
                    [e.strip().lower() for e in entry.split(",") if e.strip()]
                )
            else:
                superuser_emails.append(entry.strip().lower())

        # Track results for summary
        results = {
            "success_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "admin_count": 0,
            "superuser_count": 0,
            "errors": [],
            "warnings": [],
        }

        if clean_first:
            self.stdout.write("WARNING: Cleaning existing users (except superusers)...")
            with transaction.atomic():
                # Don't delete superusers
                user_count = User.objects.filter(is_superuser=False).count()
                User.objects.filter(is_superuser=False).delete()
                self.stdout.write(f"Deleted {user_count} existing users")

        self.stdout.write(f"Loading users from {csv_file}...")

        try:
            (
                success_count,
                updated_count,
                skipped_count,
                admin_count,
                superuser_count,
            ) = self.load_users_from_csv(
                csv_file, results, update_existing, use_passwords, superuser_emails
            )
            results["success_count"] = success_count
            results["updated_count"] = updated_count
            results["skipped_count"] = skipped_count
            results["admin_count"] = admin_count
            results["superuser_count"] = superuser_count

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully processed {success_count + updated_count + skipped_count} users: "
                    f"{success_count} created, {updated_count} updated, {skipped_count} skipped"
                )
            )

            if admin_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"Set {admin_count} users as staff/admin")
                )

            if superuser_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"Set {superuser_count} users as superusers")
                )

            if results["errors"]:
                self.stdout.write(
                    self.style.WARNING(
                        f'Encountered {len(results["errors"])} errors during loading'
                    )
                )

            if results["warnings"]:
                self.stdout.write(
                    self.style.WARNING(
                        f'Encountered {len(results["warnings"])} warnings during loading'
                    )
                )

        except Exception as e:
            results["errors"].append(f"Critical error: {str(e)}")
            self.stdout.write(self.style.ERROR(f"Error loading users: {str(e)}"))

    def load_users_from_csv(
        self,
        csv_file,
        results,
        update_existing=False,
        use_passwords=False,
        superuser_emails=None,
    ):
        """Load users from CSV file."""
        # Read CSV with pandas, handling potential parsing issues
        try:
            df = pd.read_csv(csv_file)
        except pd.errors.ParserError as e:
            # Try reading with more flexible options
            self.stdout.write(f"CSV parsing issue: {e}")
            self.stdout.write("Attempting to read with flexible parsing...")
            df = pd.read_csv(csv_file, on_bad_lines="skip")

        success_count = 0
        updated_count = 0
        skipped_count = 0
        admin_count = 0
        superuser_count = 0

        # Process each row individually with its own transaction
        for index, row in df.iterrows():
            try:
                with transaction.atomic():  # Individual transaction per row
                    # Extract data from row (handle NaN values)
                    end_user_id = row.get("end_user_id")
                    first_name = (
                        str(row.get("first_name", "")).strip()
                        if pd.notna(row.get("first_name"))
                        else ""
                    )
                    last_name = (
                        str(row.get("last_name", "")).strip()
                        if pd.notna(row.get("last_name"))
                        else ""
                    )
                    email = (
                        str(row.get("email", "")).strip().lower()
                        if pd.notna(row.get("email"))
                        else ""
                    )
                    role = (
                        str(row.get("role", "user")).strip()
                        if pd.notna(row.get("role"))
                        else "user"
                    )
                    location = (
                        str(row.get("location", "")).strip()
                        if pd.notna(row.get("location"))
                        else ""
                    )
                    department = (
                        str(row.get("department", "")).strip()
                        if pd.notna(row.get("department"))
                        else ""
                    )
                    password = (
                        str(row.get("password", "")).strip()
                        if pd.notna(row.get("password"))
                        else ""
                    )

                    # Skip rows with missing essential data
                    if not email or pd.isna(email):
                        results["errors"].append(
                            f"Row {index + 2}: Missing email address"
                        )
                        continue

                    # Validate email domain - only allow @derbyfab.com
                    if not email.endswith("@derbyfab.com"):
                        results["errors"].append(
                            f"Row {index + 2}: Invalid email domain '{email}'. Only @derbyfab.com emails are allowed."
                        )
                        continue

                    if not first_name and not last_name:
                        results["warnings"].append(
                            f"Row {index + 2}: Missing both first and last name for {email}"
                        )

                    # Use email as username for better security and login control
                    username = email

                    # Check if user already exists (by username/email since they're the same now)
                    existing_user = None
                    try:
                        existing_user = User.objects.get(username=username)
                        if update_existing:
                            self.stdout.write(f"Updating existing user: {email}...")
                        else:
                            results["warnings"].append(
                                f"Row {index + 2}: User {email} already exists, skipping"
                            )
                            skipped_count += 1
                            continue
                    except User.DoesNotExist:
                        pass  # User doesn't exist, we can create it

                    # Set password
                    if use_passwords and password:
                        # Use password from CSV (hash it properly)
                        user_password = make_password(password)
                    else:
                        # Use default password
                        user_password = make_password("password123")
                        if index < 5:  # Only show warning for first few rows
                            results["warnings"].append(
                                f"Using default password 'password123' for {email}"
                            )

                    # Set admin and superuser status
                    is_staff = role.lower() == "admin"
                    is_superuser = superuser_emails and email in superuser_emails

                    if is_staff:
                        admin_count += 1
                    if is_superuser:
                        superuser_count += 1

                    # Create or update user
                    if existing_user:
                        # Update existing user
                        user = existing_user
                        user.username = username
                        user.email = email
                        user.first_name = first_name
                        user.last_name = last_name
                        user.is_staff = is_staff
                        user.is_superuser = is_superuser
                        user.is_active = True
                        # Only update password if requested or if user doesn't have a usable password
                        if use_passwords or not user.has_usable_password():
                            user.password = user_password

                        user.save()
                        updated_count += 1
                    else:
                        # Create new user
                        user = User.objects.create(
                            username=username,
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            password=user_password,
                            is_staff=is_staff,
                            is_superuser=is_superuser,
                            is_active=True,
                        )
                        success_count += 1

                    # Create or update UserProfile
                    user_profile, profile_created = UserProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            "department": department,
                            "location": location,
                        },
                    )

                    # Update profile if it already exists
                    if not profile_created:
                        user_profile.department = department
                        user_profile.location = location
                        user_profile.save()

                    if (success_count + updated_count) % 50 == 0:
                        self.stdout.write(
                            f"Processed {success_count + updated_count} users..."
                        )

            except Exception as e:
                error_msg = f"Row {index + 2}: {str(e)}"
                results["errors"].append(error_msg)
                self.stdout.write(f"Error processing row {index + 2}: {str(e)}")
                continue

        return success_count, updated_count, skipped_count, admin_count, superuser_count
