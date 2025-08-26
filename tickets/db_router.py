"""
Database Router for handling read/write operations across multiple databases.

This router provides:
1. Read/Write splitting for MSSQL (readonly user for SELECT, write user for INSERT/UPDATE/DELETE)
2. Intelligent routing based on operation type
3. Fallback to default database when needed
"""

class DatabaseRouter:
    """
    A router to control all database operations on models for different
    databases, especially for read/write splitting in MSSQL setups.
    """

    def db_for_read(self, model, **hints):
        """Suggest the database that should be used for reads of objects of type model."""
        # For MSSQL setups, use readonly database for read operations
        from django.conf import settings
        if hasattr(settings, 'DATABASES') and 'readonly' in settings.DATABASES:
            return 'readonly'
        return None  # Use default database

    def db_for_write(self, model, **hints):
        """Suggest the database that should be used for writes of objects of type model."""
        # Always use default database for write operations
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if models are in the same app."""
        db_set = {'default', 'readonly'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure that certain apps' models get created on the right database."""
        # Only allow migrations on the default database
        if db == 'default':
            return True
        elif db == 'readonly':
            # Never run migrations on the readonly database
            return False
        return None
