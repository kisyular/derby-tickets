"""
Simple MSSQL Schema Generator
Creates a clean MSSQL schema without relying on Django's sqlmigrate
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate clean MSSQL schema for IT_Ticketing database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-file',
            type=str,
            default='clean_schema.sql',
            help='Output file to save SQL statements',
        )

    def handle(self, *args, **options):
        output_file = options.get('output_file')
        
        self.stdout.write("Generating clean MSSQL schema...")
        
        schema_sql = self.get_complete_schema()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(schema_sql)
            
        self.stdout.write(f"Clean SQL schema saved to: {output_file}")
        self.stdout.write(self.style.SUCCESS("Schema generation complete!"))
        self.stdout.write("Give this file to your DBA to create the database structure.")

    def get_complete_schema(self):
        """Get complete MSSQL schema"""
        return """-- Django IT_Ticketing Database Schema for MSSQL
-- Generated for DBA deployment
-- ============================================================

USE [IT_Ticketing];
GO

-- Drop existing tables if they exist (in reverse dependency order)
IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[tickets_ticketattachment]') AND type in (N'U'))
    DROP TABLE [tickets_ticketattachment];

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[tickets_comment]') AND type in (N'U'))
    DROP TABLE [tickets_comment];

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[tickets_ticket]') AND type in (N'U'))
    DROP TABLE [tickets_ticket];

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[tickets_category]') AND type in (N'U'))
    DROP TABLE [tickets_category];

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[tickets_apitoken]') AND type in (N'U'))
    DROP TABLE [tickets_apitoken];

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[tickets_securityevent]') AND type in (N'U'))
    DROP TABLE [tickets_securityevent];

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[tickets_loginattempt]') AND type in (N'U'))
    DROP TABLE [tickets_loginattempt];

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[tickets_usersession]') AND type in (N'U'))
    DROP TABLE [tickets_usersession];

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[tickets_auditlog]') AND type in (N'U'))
    DROP TABLE [tickets_auditlog];

IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[user_profiles]') AND type in (N'U'))
    DROP TABLE [user_profiles];

-- ============================================================
-- DJANGO CORE TABLES (created manually to avoid dependency issues)
-- ============================================================

-- Content Types table
CREATE TABLE [django_content_type] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [app_label] nvarchar(100) NOT NULL,
    [model] nvarchar(100) NOT NULL,
    CONSTRAINT [django_content_type_app_label_model_uniq] UNIQUE ([app_label], [model])
);

-- Auth Groups table
CREATE TABLE [auth_group] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [name] nvarchar(150) NOT NULL UNIQUE
);

-- Auth Permissions table
CREATE TABLE [auth_permission] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [name] nvarchar(255) NOT NULL,
    [content_type_id] bigint NOT NULL,
    [codename] nvarchar(100) NOT NULL,
    CONSTRAINT [FK_auth_permission_content_type_id] FOREIGN KEY ([content_type_id]) REFERENCES [django_content_type] ([id]),
    CONSTRAINT [auth_permission_content_type_id_codename_uniq] UNIQUE ([content_type_id], [codename])
);

-- Auth Users table
CREATE TABLE [auth_user] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [password] nvarchar(128) NOT NULL,
    [last_login] datetime2 NULL,
    [is_superuser] bit NOT NULL DEFAULT 0,
    [username] nvarchar(150) NOT NULL UNIQUE,
    [first_name] nvarchar(150) NOT NULL DEFAULT '',
    [last_name] nvarchar(150) NOT NULL DEFAULT '',
    [email] nvarchar(254) NOT NULL DEFAULT '',
    [is_staff] bit NOT NULL DEFAULT 0,
    [is_active] bit NOT NULL DEFAULT 1,
    [date_joined] datetime2 NOT NULL DEFAULT GETDATE()
);

-- Auth User Groups table (many-to-many)
CREATE TABLE [auth_user_groups] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [user_id] bigint NOT NULL,
    [group_id] bigint NOT NULL,
    CONSTRAINT [FK_auth_user_groups_user_id] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_auth_user_groups_group_id] FOREIGN KEY ([group_id]) REFERENCES [auth_group] ([id]) ON DELETE CASCADE,
    CONSTRAINT [auth_user_groups_user_id_group_id_uniq] UNIQUE ([user_id], [group_id])
);

-- Auth User Permissions table (many-to-many)
CREATE TABLE [auth_user_user_permissions] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [user_id] bigint NOT NULL,
    [permission_id] bigint NOT NULL,
    CONSTRAINT [FK_auth_user_user_permissions_user_id] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_auth_user_user_permissions_permission_id] FOREIGN KEY ([permission_id]) REFERENCES [auth_permission] ([id]) ON DELETE CASCADE,
    CONSTRAINT [auth_user_user_permissions_user_id_permission_id_uniq] UNIQUE ([user_id], [permission_id])
);

-- Django Admin Log table
CREATE TABLE [django_admin_log] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [action_time] datetime2 NOT NULL DEFAULT GETDATE(),
    [object_id] nvarchar(max) NULL,
    [object_repr] nvarchar(200) NOT NULL,
    [action_flag] smallint NOT NULL,
    [change_message] nvarchar(max) NOT NULL,
    [content_type_id] bigint NULL,
    [user_id] bigint NOT NULL,
    CONSTRAINT [FK_django_admin_log_content_type_id] FOREIGN KEY ([content_type_id]) REFERENCES [django_content_type] ([id]) ON DELETE SET NULL,
    CONSTRAINT [FK_django_admin_log_user_id] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE CASCADE
);

-- Django Sessions table
CREATE TABLE [django_session] (
    [session_key] nvarchar(40) NOT NULL PRIMARY KEY,
    [session_data] nvarchar(max) NOT NULL,
    [expire_date] datetime2 NOT NULL
);

-- Django Migrations table
CREATE TABLE [django_migrations] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [app] nvarchar(255) NOT NULL,
    [name] nvarchar(255) NOT NULL,
    [applied] datetime2 NOT NULL DEFAULT GETDATE()
);

-- ============================================================
-- TICKETS APP SCHEMA
-- ============================================================

-- Categories table
CREATE TABLE [tickets_category] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [name] nvarchar(100) NOT NULL,
    [description] nvarchar(500) NOT NULL DEFAULT '',
    [color] nvarchar(7) NOT NULL DEFAULT '#007bff',
    [is_active] bit NOT NULL DEFAULT 1,
    [created_at] datetime2 NOT NULL DEFAULT GETDATE(),
    [updated_at] datetime2 NOT NULL DEFAULT GETDATE()
);

-- User Profiles table
CREATE TABLE [user_profiles] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [user_id] bigint NOT NULL,
    [location] nvarchar(100) NOT NULL DEFAULT '',
    [department] nvarchar(100) NOT NULL DEFAULT '',
    [phone] nvarchar(20) NOT NULL DEFAULT '',
    [created_at] datetime2 NOT NULL DEFAULT GETDATE(),
    [updated_at] datetime2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [FK_user_profiles_user_id] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE CASCADE
);

-- Tickets table
CREATE TABLE [tickets_ticket] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [title] nvarchar(200) NOT NULL,
    [description] nvarchar(max) NOT NULL,
    [status] nvarchar(20) NOT NULL DEFAULT 'Open',
    [priority] nvarchar(20) NOT NULL DEFAULT 'Medium',
    [created_by_id] bigint NOT NULL,
    [assigned_to_id] bigint NULL,
    [category_id] bigint NULL,
    [department] nvarchar(100) NOT NULL DEFAULT '',
    [location] nvarchar(100) NOT NULL DEFAULT '',
    [created_at] datetime2 NOT NULL DEFAULT GETDATE(),
    [updated_at] datetime2 NOT NULL DEFAULT GETDATE(),
    [closed_on] datetime2 NULL,
    CONSTRAINT [FK_tickets_ticket_created_by_id] FOREIGN KEY ([created_by_id]) REFERENCES [auth_user] ([id]),
    CONSTRAINT [FK_tickets_ticket_assigned_to_id] FOREIGN KEY ([assigned_to_id]) REFERENCES [auth_user] ([id]) ON DELETE SET NULL,
    CONSTRAINT [FK_tickets_ticket_category_id] FOREIGN KEY ([category_id]) REFERENCES [tickets_category] ([id]) ON DELETE SET NULL
);

-- Comments table
CREATE TABLE [tickets_comment] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [ticket_id] bigint NOT NULL,
    [author_id] bigint NOT NULL,
    [content] nvarchar(max) NOT NULL,
    [is_internal] bit NOT NULL DEFAULT 0,
    [created_at] datetime2 NOT NULL DEFAULT GETDATE(),
    [updated_at] datetime2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT [FK_tickets_comment_ticket_id] FOREIGN KEY ([ticket_id]) REFERENCES [tickets_ticket] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_tickets_comment_author_id] FOREIGN KEY ([author_id]) REFERENCES [auth_user] ([id])
);

-- Ticket Attachments table
CREATE TABLE [tickets_ticketattachment] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [ticket_id] bigint NOT NULL,
    [file] nvarchar(100) NOT NULL,
    [original_filename] nvarchar(255) NOT NULL,
    [file_type] nvarchar(20) NOT NULL,
    [file_size] bigint NOT NULL,
    [uploaded_by_id] bigint NOT NULL,
    [uploaded_at] datetime2 NOT NULL DEFAULT GETDATE(),
    [description] nvarchar(200) NOT NULL DEFAULT '',
    CONSTRAINT [FK_tickets_ticketattachment_ticket_id] FOREIGN KEY ([ticket_id]) REFERENCES [tickets_ticket] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_tickets_ticketattachment_uploaded_by_id] FOREIGN KEY ([uploaded_by_id]) REFERENCES [auth_user] ([id])
);

-- API Tokens table
CREATE TABLE [tickets_apitoken] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [name] nvarchar(100) NOT NULL,
    [token] nvarchar(64) NOT NULL UNIQUE,
    [user_id] bigint NOT NULL,
    [is_active] bit NOT NULL DEFAULT 1,
    [created_at] datetime2 NOT NULL DEFAULT GETDATE(),
    [last_used] datetime2 NULL,
    [expires_at] datetime2 NULL,
    CONSTRAINT [FK_tickets_apitoken_user_id] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE CASCADE
);

-- Security Events table
CREATE TABLE [tickets_securityevent] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [event_type] nvarchar(50) NOT NULL,
    [severity] nvarchar(10) NOT NULL,
    [timestamp] datetime2 NOT NULL DEFAULT GETDATE(),
    [user_id] bigint NULL,
    [username_attempted] nvarchar(150) NOT NULL DEFAULT '',
    [ip_address] nvarchar(45) NOT NULL DEFAULT '',
    [user_agent] nvarchar(max) NOT NULL DEFAULT '',
    [session_key] nvarchar(40) NOT NULL DEFAULT '',
    [description] nvarchar(max) NOT NULL,
    [success] bit NOT NULL DEFAULT 0,
    [reason] nvarchar(max) NOT NULL DEFAULT '',
    [metadata] nvarchar(max) NOT NULL DEFAULT '{}',
    [resolved] bit NOT NULL DEFAULT 0,
    [resolved_by_id] bigint NULL,
    [resolved_at] datetime2 NULL,
    [notes] nvarchar(max) NOT NULL DEFAULT '',
    CONSTRAINT [FK_tickets_securityevent_user_id] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE SET NULL,
    CONSTRAINT [FK_tickets_securityevent_resolved_by_id] FOREIGN KEY ([resolved_by_id]) REFERENCES [auth_user] ([id]) ON DELETE SET NULL
);

-- Login Attempts table
CREATE TABLE [tickets_loginattempt] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [username] nvarchar(150) NOT NULL,
    [ip_address] nvarchar(45) NOT NULL,
    [user_agent] nvarchar(max) NOT NULL DEFAULT '',
    [timestamp] datetime2 NOT NULL DEFAULT GETDATE(),
    [success] bit NOT NULL DEFAULT 0,
    [failure_reason] nvarchar(200) NOT NULL DEFAULT '',
    [user_id] bigint NULL,
    CONSTRAINT [FK_tickets_loginattempt_user_id] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE SET NULL
);

-- User Sessions table
CREATE TABLE [tickets_usersession] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [user_id] bigint NOT NULL,
    [session_key] nvarchar(40) NOT NULL UNIQUE,
    [ip_address] nvarchar(45) NOT NULL,
    [user_agent] nvarchar(max) NOT NULL DEFAULT '',
    [login_time] datetime2 NOT NULL DEFAULT GETDATE(),
    [last_activity] datetime2 NOT NULL DEFAULT GETDATE(),
    [logout_time] datetime2 NULL,
    [is_active] bit NOT NULL DEFAULT 1,
    CONSTRAINT [FK_tickets_usersession_user_id] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE CASCADE
);

-- Audit Log table
CREATE TABLE [tickets_auditlog] (
    [id] bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [user_id] bigint NULL,
    [action] nvarchar(50) NOT NULL,
    [model_name] nvarchar(100) NOT NULL DEFAULT '',
    [object_id] nvarchar(255) NOT NULL DEFAULT '',
    [object_repr] nvarchar(200) NOT NULL DEFAULT '',
    [description] nvarchar(max) NOT NULL,
    [timestamp] datetime2 NOT NULL DEFAULT GETDATE(),
    [ip_address] nvarchar(45) NOT NULL DEFAULT '',
    [user_agent] nvarchar(max) NOT NULL DEFAULT '',
    [session_key] nvarchar(40) NOT NULL DEFAULT '',
    [risk_level] nvarchar(10) NOT NULL DEFAULT 'LOW',
    [additional_data] nvarchar(max) NOT NULL DEFAULT '{}',
    CONSTRAINT [FK_tickets_auditlog_user_id] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE SET NULL
);

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================

-- Django core indexes
CREATE INDEX [IX_auth_user_username] ON [auth_user] ([username]);
CREATE INDEX [IX_auth_permission_content_type_id] ON [auth_permission] ([content_type_id]);
CREATE INDEX [IX_django_admin_log_content_type_id] ON [django_admin_log] ([content_type_id]);
CREATE INDEX [IX_django_admin_log_user_id] ON [django_admin_log] ([user_id]);
CREATE INDEX [IX_django_session_expire_date] ON [django_session] ([expire_date]);

-- Tickets indexes
CREATE INDEX [IX_tickets_ticket_status] ON [tickets_ticket] ([status]);
CREATE INDEX [IX_tickets_ticket_priority] ON [tickets_ticket] ([priority]);
CREATE INDEX [IX_tickets_ticket_created_by_id] ON [tickets_ticket] ([created_by_id]);
CREATE INDEX [IX_tickets_ticket_assigned_to_id] ON [tickets_ticket] ([assigned_to_id]);
CREATE INDEX [IX_tickets_ticket_created_at] ON [tickets_ticket] ([created_at]);
CREATE INDEX [IX_tickets_ticket_updated_at] ON [tickets_ticket] ([updated_at]);

-- Comments indexes
CREATE INDEX [IX_tickets_comment_ticket_id] ON [tickets_comment] ([ticket_id]);
CREATE INDEX [IX_tickets_comment_author_id] ON [tickets_comment] ([author_id]);
CREATE INDEX [IX_tickets_comment_created_at] ON [tickets_comment] ([created_at]);

-- Security and audit indexes
CREATE INDEX [IX_tickets_securityevent_timestamp] ON [tickets_securityevent] ([timestamp]);
CREATE INDEX [IX_tickets_securityevent_event_type] ON [tickets_securityevent] ([event_type]);
CREATE INDEX [IX_tickets_securityevent_user_id] ON [tickets_securityevent] ([user_id]);
CREATE INDEX [IX_tickets_loginattempt_timestamp] ON [tickets_loginattempt] ([timestamp]);
CREATE INDEX [IX_tickets_loginattempt_username] ON [tickets_loginattempt] ([username]);
CREATE INDEX [IX_tickets_loginattempt_ip_address] ON [tickets_loginattempt] ([ip_address]);
CREATE INDEX [IX_tickets_usersession_user_id] ON [tickets_usersession] ([user_id]);
CREATE INDEX [IX_tickets_usersession_session_key] ON [tickets_usersession] ([session_key]);
CREATE INDEX [IX_tickets_usersession_is_active] ON [tickets_usersession] ([is_active]);
CREATE INDEX [IX_tickets_auditlog_timestamp] ON [tickets_auditlog] ([timestamp]);
CREATE INDEX [IX_tickets_auditlog_action] ON [tickets_auditlog] ([action]);
CREATE INDEX [IX_tickets_auditlog_user_id] ON [tickets_auditlog] ([user_id]);

-- User profiles indexes
CREATE INDEX [IX_user_profiles_user_id] ON [user_profiles] ([user_id]);
CREATE INDEX [IX_user_profiles_department] ON [user_profiles] ([department]);

-- API tokens indexes
CREATE INDEX [IX_tickets_apitoken_user_id] ON [tickets_apitoken] ([user_id]);
CREATE INDEX [IX_tickets_apitoken_is_active] ON [tickets_apitoken] ([is_active]);
CREATE INDEX [IX_tickets_apitoken_token] ON [tickets_apitoken] ([token]);

-- ============================================================
-- CONSTRAINTS AND BUSINESS RULES
-- ============================================================

-- Check constraints for data integrity
ALTER TABLE [tickets_ticket] ADD CONSTRAINT [CK_tickets_ticket_status] 
    CHECK ([status] IN ('Open', 'In Progress', 'Closed', 'Reopened'));

ALTER TABLE [tickets_ticket] ADD CONSTRAINT [CK_tickets_ticket_priority] 
    CHECK ([priority] IN ('Low', 'Medium', 'High', 'Urgent'));

ALTER TABLE [tickets_ticketattachment] ADD CONSTRAINT [CK_tickets_ticketattachment_file_type] 
    CHECK ([file_type] IN ('IMAGE', 'PDF'));

ALTER TABLE [tickets_securityevent] ADD CONSTRAINT [CK_tickets_securityevent_severity] 
    CHECK ([severity] IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'));

ALTER TABLE [tickets_auditlog] ADD CONSTRAINT [CK_tickets_auditlog_risk_level] 
    CHECK ([risk_level] IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'));

-- ============================================================
-- DJANGO CONTENT TYPE INITIAL DATA
-- ============================================================

-- Insert Django content types
INSERT INTO [django_content_type] ([app_label], [model]) VALUES
('admin', 'logentry'),
('auth', 'permission'),
('auth', 'group'),
('auth', 'user'),
('contenttypes', 'contenttype'),
('sessions', 'session'),
('tickets', 'userprofile'),
('tickets', 'category'),
('tickets', 'ticket'),
('tickets', 'comment'),
('tickets', 'ticketattachment'),
('tickets', 'apitoken'),
('tickets', 'securityevent'),
('tickets', 'loginattempt'),
('tickets', 'usersession'),
('tickets', 'auditlog');

-- ============================================================
-- DJANGO MIGRATION RECORDS
-- ============================================================

-- Mark all migrations as applied
INSERT INTO [django_migrations] ([app], [name]) VALUES
('contenttypes', '0001_initial'),
('contenttypes', '0002_remove_content_type_name'),
('auth', '0001_initial'),
('auth', '0002_alter_permission_name_max_length'),
('auth', '0003_alter_user_email_max_length'),
('auth', '0004_alter_user_username_opts'),
('auth', '0005_alter_user_last_login_null'),
('auth', '0006_require_contenttypes_0002'),
('auth', '0007_alter_validators_add_error_messages'),
('auth', '0008_alter_user_username_max_length'),
('auth', '0009_alter_user_last_name_max_length'),
('auth', '0010_alter_group_name_max_length'),
('auth', '0011_update_proxy_permissions'),
('auth', '0012_alter_user_first_name_max_length'),
('admin', '0001_initial'),
('admin', '0002_logentry_remove_auto_add'),
('admin', '0003_logentry_add_action_flag_choices'),
('sessions', '0001_initial'),
('tickets', '0001_initial'),
('tickets', '0002_alter_ticket_assigned_to'),
('tickets', '0003_alter_admin_options_alter_enduser_options_and_more'),
('tickets', '0004_fix_ticket_choices'),
('tickets', '0005_fix_userprofile_relation'),
('tickets', '0006_add_comment_model'),
('tickets', '0007_fix_user_deletion_cascade'),
('tickets', '0008_ticket_category_ticket_closed_at_and_more'),
('tickets', '0009_rename_closed_at_ticket_closed_on_and_more'),
('tickets', '0010_alter_ticket_status'),
('tickets', '0011_alter_ticket_created_at'),
('tickets', '0012_ticket_department_ticket_location'),
('tickets', '0013_add_category_model'),
('tickets', '0014_alter_ticket_category'),
('tickets', '0015_add_urgent_priority'),
('tickets', '0016_alter_comment_options_auditlog_loginattempt_and_more'),
('tickets', '0017_apitoken'),
('tickets', '0018_ticketattachment');

-- ============================================================
-- INITIAL DATA (Optional)
-- ============================================================

-- Insert default categories
INSERT INTO [tickets_category] ([name], [description], [color], [is_active]) VALUES
('General', 'General support requests', '#007bff', 1),
('IT Support', 'Information Technology support', '#28a745', 1),
('Hardware', 'Hardware-related issues', '#dc3545', 1),
('Software', 'Software-related issues', '#ffc107', 1),
('Network', 'Network and connectivity issues', '#17a2b8', 1);

-- ============================================================
-- PERMISSIONS (Optional - adjust as needed)
-- ============================================================

-- Grant permissions to the application write user
GRANT SELECT, INSERT, UPDATE, DELETE ON [auth_user] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [auth_group] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [auth_permission] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [auth_user_groups] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [auth_user_user_permissions] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [django_content_type] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [django_admin_log] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [django_session] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [django_migrations] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [tickets_ticket] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [tickets_comment] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [tickets_category] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [tickets_ticketattachment] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [tickets_apitoken] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [tickets_securityevent] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [tickets_loginattempt] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [tickets_usersession] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [tickets_auditlog] TO [myWriteLogin];
GRANT SELECT, INSERT, UPDATE, DELETE ON [user_profiles] TO [myWriteLogin];

-- Grant read-only permissions to the read user (when fixed)
-- GRANT SELECT ON ALL TABLES TO [it_ticket_read];

GO

PRINT 'IT_Ticketing database schema created successfully!';
PRINT 'All tables created: Django core + Tickets app';
PRINT 'All migrations marked as applied';
PRINT 'Next steps:';
PRINT '1. Set USE_MSSQL="True" in .env file';
PRINT '2. Create superuser: python manage.py createsuperuser';
PRINT '3. Test the application!';
"""
