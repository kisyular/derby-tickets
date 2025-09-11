"""
Management command to clean up unused Celery tables
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Clean up unused Celery tables from the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force deletion without confirmation",
        )

    def handle(self, *args, **options):
        celery_tables = [
            "django_celery_beat_clockedschedule",
            "django_celery_beat_crontabschedule",
            "django_celery_beat_intervalschedule",
            "django_celery_beat_periodictask",
            "django_celery_beat_periodictasks",
            "django_celery_beat_solarschedule",
            "django_celery_results_chordcounter",
            "django_celery_results_groupresult",
            "django_celery_results_taskresult",
        ]

        with connection.cursor() as cursor:
            # Check which tables actually exist
            if connection.vendor == "microsoft":
                cursor.execute(
                    """
                    SELECT TABLE_NAME 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_TYPE = 'BASE TABLE' 
                    AND TABLE_NAME IN ({})
                """.format(
                        ",".join("'%s'" % table for table in celery_tables)
                    )
                )
            else:
                cursor.execute(
                    """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ({})
                """.format(
                        ",".join("'%s'" % table for table in celery_tables)
                    )
                )

            existing_tables = [row[0] for row in cursor.fetchall()]

            if not existing_tables:
                self.stdout.write(
                    self.style.SUCCESS("✅ No Celery tables found - already clean!")
                )
                return

            self.stdout.write(f"\n🔍 Found {len(existing_tables)} Celery tables:")

            # Check row counts for each table
            tables_with_data = []
            for table in existing_tables:
                try:
                    table_query = (
                        f"[{table}]" if connection.vendor == "microsoft" else table
                    )
                    cursor.execute(f"SELECT COUNT(*) FROM {table_query}")
                    row_count = cursor.fetchone()[0]

                    if row_count > 0:
                        tables_with_data.append((table, row_count))
                        self.stdout.write(f"  📊 {table}: {row_count} rows")
                    else:
                        self.stdout.write(f"  📄 {table}: empty")

                except Exception as e:
                    self.stdout.write(f"  ❌ {table}: Error checking - {e}")

            # Warn about tables with data
            if tables_with_data:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n⚠️  WARNING: {len(tables_with_data)} tables contain data:"
                    )
                )
                for table, count in tables_with_data:
                    self.stdout.write(f"  - {table}: {count} rows")

                if not options["force"]:
                    self.stdout.write(
                        self.style.ERROR(
                            "\n❌ Aborting: Some tables contain data. Use --force to delete anyway."
                        )
                    )
                    return

            # Show what will be deleted
            if options["dry_run"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n🔍 DRY RUN - Would delete {len(existing_tables)} tables:"
                    )
                )
                for table in existing_tables:
                    self.stdout.write(f"  - DROP TABLE {table}")
                return

            # Confirm deletion
            if not options["force"]:
                self.stdout.write(
                    f"\n❓ This will permanently delete {len(existing_tables)} Celery tables."
                )
                confirm = input("Type 'yes' to confirm: ")
                if confirm.lower() != "yes":
                    self.stdout.write(self.style.ERROR("❌ Cancelled"))
                    return

            # Delete tables
            self.stdout.write(f"\n🗑️  Deleting {len(existing_tables)} Celery tables...")
            deleted_count = 0

            for table in existing_tables:
                try:
                    table_query = (
                        f"[{table}]" if connection.vendor == "microsoft" else table
                    )
                    cursor.execute(f"DROP TABLE {table_query}")
                    self.stdout.write(f"  ✅ Deleted {table}")
                    deleted_count += 1
                except Exception as e:
                    self.stdout.write(f"  ❌ Failed to delete {table}: {e}")

            if deleted_count == len(existing_tables):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n🎉 Successfully deleted all {deleted_count} Celery tables!"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n⚠️  Deleted {deleted_count}/{len(existing_tables)} tables. "
                        f"{len(existing_tables) - deleted_count} failed."
                    )
                )

            # Show final status
            self.stdout.write("\n📋 Cleanup complete. You may want to:")
            self.stdout.write(
                "  1. Remove celery/django-celery-beat from requirements.txt"
            )
            self.stdout.write("  2. Remove any Celery configuration from settings.py")
            self.stdout.write(
                "  3. Run migrations if you have custom migration files referencing these tables"
            )
