"""
Management command to test database connections
"""

import pyodbc
import os
from django.core.management.base import BaseCommand
from django.db import connections
from django.conf import settings


class Command(BaseCommand):
    help = 'Test database connections (SQLite and MSSQL)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-mssql-direct',
            action='store_true',
            help='Test direct MSSQL connection using pyodbc',
        )
        parser.add_argument(
            '--test-django-db',
            action='store_true',
            help='Test Django database connections',
        )
        parser.add_argument(
            '--test-all',
            action='store_true',
            help='Test all connection methods',
        )

    def handle(self, *args, **options):
        if options['test_all']:
            options['test_mssql_direct'] = True
            options['test_django_db'] = True

        if options['test_mssql_direct']:
            self.test_mssql_direct()

        if options['test_django_db']:
            self.test_django_connections()

        if not any([options['test_mssql_direct'], options['test_django_db'], options['test_all']]):
            self.stdout.write("Please specify a test option. Use --help for options.")

    def test_mssql_direct(self):
        """Test direct MSSQL connection using pyodbc (your original approach)"""
        self.stdout.write(self.style.SUCCESS("=== Testing Direct MSSQL Connection ==="))
        
        # Read credentials from .env
        db_name = os.environ.get('MSSQL_DB_NAME')
        db_host = os.environ.get('MSSQL_DB_HOST')
        db_port = os.environ.get('MSSQL_DB_PORT', '1433')
        
        # Test read connection
        read_user = os.environ.get('MSSQL_DB_USER_READ')
        read_password = os.environ.get('MSSQL_DB_PASSWORD_READ')
        
        # Test write connection
        write_user = os.environ.get('MSSQL_DB_USER_WRITE')
        write_password = os.environ.get('MSSQL_DB_PASSWORD_WRITE')

        if not all([db_name, db_host, read_user, read_password, write_user, write_password]):
            self.stdout.write(self.style.ERROR("Missing MSSQL environment variables!"))
            return

        # Test read connection
        self.stdout.write("Testing READ connection...")
        if self.test_pyodbc_connection(db_host, db_port, db_name, read_user, read_password):
            self.stdout.write(self.style.SUCCESS("✅ READ connection successful"))
        else:
            self.stdout.write(self.style.ERROR("❌ READ connection failed"))

        # Test write connection
        self.stdout.write("Testing WRITE connection...")
        if self.test_pyodbc_connection(db_host, db_port, db_name, write_user, write_password):
            self.stdout.write(self.style.SUCCESS("✅ WRITE connection successful"))
        else:
            self.stdout.write(self.style.ERROR("❌ WRITE connection failed"))

    def test_pyodbc_connection(self, host, port, database, username, password):
        """Test a pyodbc connection with given parameters"""
        try:
            connection_string = (
                f"Driver={{ODBC Driver 17 for SQL Server}};"
                f"Server={host},{port};"
                f"Database={database};"
                f"UID={username};"
                f"PWD={password};"
                f"TrustServerCertificate=yes;"
            )
            
            connection = pyodbc.connect(connection_string)
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            
            return result is not None
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Connection failed: {str(e)}"))
            return False

    def test_django_connections(self):
        """Test Django database connections"""
        self.stdout.write(self.style.SUCCESS("=== Testing Django Database Connections ==="))
        
        for db_name in settings.DATABASES:
            self.stdout.write(f"Testing database: {db_name}")
            try:
                connection = connections[db_name]
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    
                if result:
                    self.stdout.write(self.style.SUCCESS(f"✅ {db_name} connection successful"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ {db_name} connection failed"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ {db_name} connection failed: {str(e)}"))

    def show_current_config(self):
        """Show current database configuration"""
        self.stdout.write(self.style.SUCCESS("=== Current Database Configuration ==="))
        use_mssql = os.environ.get('USE_MSSQL', 'False').lower() == 'true'
        self.stdout.write(f"USE_MSSQL: {use_mssql}")
        
        for db_name, db_config in settings.DATABASES.items():
            self.stdout.write(f"{db_name}: {db_config['ENGINE']}")
            if 'HOST' in db_config:
                self.stdout.write(f"  Host: {db_config['HOST']}")
                self.stdout.write(f"  Database: {db_config['NAME']}")
                self.stdout.write(f"  User: {db_config['USER']}")
