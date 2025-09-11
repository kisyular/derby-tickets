"""
Management command to analyze all databases and their structure
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connections
from django.apps import apps


class Command(BaseCommand):
    help = "Analyze all databases, tables, row counts, and Django model mappings"

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            "-d",
            type=str,
            help="Analyze only a specific database (e.g., default, computers)",
        )
        parser.add_argument(
            "--no-models",
            action="store_true",
            help="Skip Django models analysis",
        )
        parser.add_argument(
            "--summary-only",
            action="store_true",
            help="Show only summary statistics, not detailed table lists",
        )
        parser.add_argument(
            "--format",
            choices=["table", "json", "csv"],
            default="table",
            help="Output format (default: table)",
        )

    def handle(self, *args, **options):
        if options["format"] == "json":
            self.analyze_json(options)
        elif options["format"] == "csv":
            self.analyze_csv(options)
        else:
            self.analyze_table(options)

    def analyze_table(self, options):
        """Analyze databases in table format (default)"""
        self.stdout.write("🗄️  COMPREHENSIVE DATABASE ANALYSIS")
        self.stdout.write("=" * 80)

        databases = list(settings.DATABASES.keys())
        if options["database"]:
            if options["database"] in databases:
                databases = [options["database"]]
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Database '{options['database']}' not found!")
                )
                self.stdout.write(f"Available databases: {', '.join(databases)}")
                return

        self.stdout.write(f"\n📊 Found {len(databases)} configured database(s)")

        db_results = []
        for db_alias in databases:
            result = self.analyze_database(db_alias, options["summary_only"])
            db_results.append(result)

        if not options["no_models"]:
            self.analyze_django_models()

        # Final summary
        total_tables = sum(len(db["tables"]) for db in db_results)
        total_rows = sum(db["total_rows"] for db in db_results)
        connected_dbs = sum(1 for db in db_results if db["connected"])

        self.stdout.write(
            "\n========================= FINAL SUMMARY ========================="
        )
        self.stdout.write(
            f"🗄️  Total Databases: {len(databases)} ({connected_dbs} connected)"
        )
        self.stdout.write(f"📋 Total Tables: {total_tables}")
        self.stdout.write(f"📊 Total Rows: {total_rows:,}")
        if not options["no_models"]:
            self.stdout.write(f"📱 Django Apps: {len(apps.get_app_configs())}")
            self.stdout.write(f"🏷️  Django Models: {len(apps.get_models())}")
        self.stdout.write("=" * 80)

    def analyze_json(self, options):
        """Analyze databases in JSON format"""
        import json

        databases = list(settings.DATABASES.keys())
        if options["database"]:
            if options["database"] in databases:
                databases = [options["database"]]
            else:
                self.stdout.write(
                    json.dumps({"error": f"Database '{options['database']}' not found"})
                )
                return

        result = {"databases": [], "summary": {}, "django_models": {}}

        db_results = []
        for db_alias in databases:
            db_info = self.analyze_database_data(db_alias)
            db_results.append(db_info)
            result["databases"].append(db_info)

        if not options["no_models"]:
            result["django_models"] = self.get_django_models_data()

        # Summary
        total_tables = sum(len(db["tables"]) for db in db_results)
        total_rows = sum(db["total_rows"] for db in db_results)
        connected_dbs = sum(1 for db in db_results if db["connected"])

        result["summary"] = {
            "total_databases": len(databases),
            "connected_databases": connected_dbs,
            "total_tables": total_tables,
            "total_rows": total_rows,
            "django_apps": (
                len(apps.get_app_configs()) if not options["no_models"] else None
            ),
            "django_models": (
                len(apps.get_models()) if not options["no_models"] else None
            ),
        }

        self.stdout.write(json.dumps(result, indent=2))

    def analyze_csv(self, options):
        """Analyze databases in CSV format"""
        import csv
        import sys

        databases = list(settings.DATABASES.keys())
        if options["database"]:
            if options["database"] in databases:
                databases = [options["database"]]
            else:
                self.stdout.write(f"Error: Database '{options['database']}' not found")
                return

        # Output table information
        writer = csv.writer(sys.stdout)
        writer.writerow(["Database", "Table", "Row_Count", "Engine", "Connected"])

        for db_alias in databases:
            db_info = self.analyze_database_data(db_alias)
            engine = db_info["engine"]
            connected = db_info["connected"]

            for table_info in db_info["tables"]:
                writer.writerow(
                    [
                        db_alias,
                        table_info["name"],
                        table_info["row_count"],
                        engine,
                        connected,
                    ]
                )

    def analyze_database(self, alias, summary_only=False):
        """Analyze a single database and return its info"""
        connection = connections[alias]
        config = settings.DATABASES[alias]

        self.stdout.write(
            f"\n==================== DATABASE: {alias.upper()} ===================="
        )
        self.stdout.write(f"🔧 Engine: {config['ENGINE'].split('.')[-1]}")
        self.stdout.write(f"📁 Name: {config['NAME']}")
        self.stdout.write(
            f"🌐 Host: {config.get('HOST', 'localhost')}:{config.get('PORT', 'default')}"
        )

        try:
            # Test connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                self.stdout.write(f"✅ Status: Connected ({connection.vendor})")

                # Get table names
                if connection.vendor == "microsoft":
                    cursor.execute(
                        """
                        SELECT TABLE_NAME 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_TYPE = 'BASE TABLE' 
                        ORDER BY TABLE_NAME
                    """
                    )
                elif connection.vendor == "sqlite":
                    cursor.execute(
                        """
                        SELECT name 
                        FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%' 
                        ORDER BY name
                    """
                    )
                else:
                    cursor.execute(
                        """
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        ORDER BY table_name
                    """
                    )

                tables = [row[0] for row in cursor.fetchall()]

                if not summary_only:
                    self.stdout.write(f"\n📋 TABLES ({len(tables)} total):")
                    self.stdout.write("-" * 70)

                total_rows = 0
                for table in tables:
                    try:
                        # Use quoted table names for SQL Server
                        table_query = (
                            f"[{table}]" if connection.vendor == "microsoft" else table
                        )
                        cursor.execute(f"SELECT COUNT(*) FROM {table_query}")
                        row_count = cursor.fetchone()[0]
                        total_rows += row_count
                        if not summary_only:
                            self.stdout.write(f"📄 {table:<35} | Rows: {row_count:>8,}")
                    except Exception as e:
                        if not summary_only:
                            self.stdout.write(
                                f"📄 {table:<35} | Rows: ERROR - {str(e)[:30]}..."
                            )

                self.stdout.write(f"\n📊 {alias.upper()} SUMMARY:")
                self.stdout.write(f"   • Total Tables: {len(tables)}")
                self.stdout.write(f"   • Total Rows: {total_rows:,}")

                return {
                    "alias": alias,
                    "tables": tables,
                    "total_rows": total_rows,
                    "connected": True,
                }

        except Exception as e:
            self.stdout.write(f"❌ Status: Connection failed - {e}")
            return {"alias": alias, "tables": [], "total_rows": 0, "connected": False}

    def analyze_database_data(self, alias):
        """Get database info as data (for JSON/CSV output)"""
        connection = connections[alias]
        config = settings.DATABASES[alias]

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

                # Get table names
                if connection.vendor == "microsoft":
                    cursor.execute(
                        """
                        SELECT TABLE_NAME 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_TYPE = 'BASE TABLE' 
                        ORDER BY TABLE_NAME
                    """
                    )
                elif connection.vendor == "sqlite":
                    cursor.execute(
                        """
                        SELECT name 
                        FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%' 
                        ORDER BY name
                    """
                    )
                else:
                    cursor.execute(
                        """
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        ORDER BY table_name
                    """
                    )

                table_names = [row[0] for row in cursor.fetchall()]
                tables = []
                total_rows = 0

                for table in table_names:
                    try:
                        table_query = (
                            f"[{table}]" if connection.vendor == "microsoft" else table
                        )
                        cursor.execute(f"SELECT COUNT(*) FROM {table_query}")
                        row_count = cursor.fetchone()[0]
                        total_rows += row_count
                        tables.append({"name": table, "row_count": row_count})
                    except Exception as e:
                        tables.append({"name": table, "row_count": f"ERROR: {str(e)}"})

                return {
                    "alias": alias,
                    "engine": config["ENGINE"].split(".")[-1],
                    "name": config["NAME"],
                    "host": f"{config.get('HOST', 'localhost')}:{config.get('PORT', 'default')}",
                    "tables": tables,
                    "total_rows": total_rows,
                    "connected": True,
                }

        except Exception as e:
            return {
                "alias": alias,
                "engine": config["ENGINE"].split(".")[-1],
                "name": config["NAME"],
                "host": f"{config.get('HOST', 'localhost')}:{config.get('PORT', 'default')}",
                "tables": [],
                "total_rows": 0,
                "connected": False,
                "error": str(e),
            }

    def analyze_django_models(self):
        """Analyze Django models and their database mappings"""
        self.stdout.write(
            "\n========================= DJANGO MODELS =========================\n"
        )

        all_models = apps.get_models()
        apps_data = {}

        for model in all_models:
            app_label = model._meta.app_label
            if app_label not in apps_data:
                apps_data[app_label] = []

            # Get database alias for this model
            using = getattr(model._meta, "app_label", "default")
            if hasattr(model, "_state"):
                using = model._state.db or "default"
            else:
                using = "default"

            # Get actual row count
            try:
                row_count = model.objects.count()
            except Exception:
                row_count = "Error"

            apps_data[app_label].append(
                {
                    "name": model._meta.model_name,
                    "table": model._meta.db_table,
                    "database": using,
                    "row_count": row_count,
                }
            )

        self.stdout.write(f"📱 Django Apps: {len(apps_data)}")
        self.stdout.write(f"🏷️  Django Models: {len(all_models)}")

        for app_label, models in apps_data.items():
            self.stdout.write(f"\n📦 {app_label} ({len(models)} models):")
            for model in models:
                row_text = (
                    f"{model['row_count']} rows"
                    if isinstance(model["row_count"], int)
                    else model["row_count"]
                )
                self.stdout.write(
                    f"   🏷️  {model['name']:<15} → {model['table']:<25} [{model['database']}] ({row_text})"
                )

    def get_django_models_data(self):
        """Get Django models data (for JSON output)"""
        all_models = apps.get_models()
        apps_data = {}

        for model in all_models:
            app_label = model._meta.app_label
            if app_label not in apps_data:
                apps_data[app_label] = []

            # Get database alias for this model
            using = getattr(model._meta, "app_label", "default")
            if hasattr(model, "_state"):
                using = model._state.db or "default"
            else:
                using = "default"

            # Get actual row count
            try:
                row_count = model.objects.count()
            except Exception:
                row_count = "Error"

            apps_data[app_label].append(
                {
                    "name": model._meta.model_name,
                    "table": model._meta.db_table,
                    "database": using,
                    "row_count": row_count,
                }
            )

        return {
            "apps_count": len(apps_data),
            "models_count": len(all_models),
            "apps": apps_data,
        }
