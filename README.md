# Django Ticket Management System

A modern ticket management system built with Django.

## Features

- **User Authentication**: Secure login system with admin-controlled user creation
- **Role-based System**: Two user roles - Admin (can be assigned tickets) and User (can create tickets)
- **Permission-based Access**: Users can only view their own tickets or assigned tickets
- **Admin Assignment**: Tickets can only be assigned to users with Admin role
- Create, view, and manage tickets
- Priority levels (Low, Medium, High, Urgent)
- Status tracking (Open, In Progress, Closed)
- User assignment and ownership tracking
- Clean and responsive Bootstrap UI
- Django Admin interface with enhanced user management
- Search and filter capabilities

## Installation

1. Make sure you have Python and Django installed
2. Install requirements:

   ```
   pip install -r requirements.txt
   ```

3. Run migrations:

   ```
   python manage.py makemigrations
   python manage.py migrate
   ```

4. Create a superuser (admin account):

   ```
   python manage.py create_admin
   ```

   or manually:

   ```
   python manage.py createsuperuser
   ```

5. Run the development server:

   ```
   python manage.py runserver
   ```

6. Visit http://127.0.0.1:8000/ to access the application

## Project Structure

```
ticket_project/
├── manage.py
├── requirements.txt
├── ticket_project/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── tickets/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── models.py
    ├── views.py
    ├── urls.py
    ├── tests.py
    └── templates/
        └── tickets/
            ├── base.html
            ├── home.html
            ├── ticket_list.html
            ├── ticket_detail.html
            └── create_ticket.html
```

## Usage

1. **Login**: Users must sign in with admin-provided credentials
2. **Home Page**: Dashboard showing user's tickets, role, and quick actions
3. **My Tickets**: View tickets created by or assigned to the current user
4. **Create Ticket**: Form to create new tickets with optional admin assignment
5. **Ticket Details**: View detailed information about a specific ticket
6. **Django Admin**: Admins can manage users, roles, and tickets at /admin/

## User Roles

- **Admin Users**:

  - Can be assigned to tickets
  - Can create tickets
  - Can view tickets they created or are assigned to
  - Have full admin privileges if they are also staff/superuser

- **Regular Users**:
  - Can create tickets
  - Can view tickets they created
  - Cannot be assigned to tickets

6. **Django Admin**: Admins can manage users and tickets at /admin/

## User Management

- **Admin Only**: Only administrators can create user accounts
- **No Self-Registration**: Users cannot create their own accounts
- **Secure Access**: Users can only access tickets they created or are assigned to
- **Role-based Permissions**: Staff users have additional privileges

## Models

### Ticket

- `title`: CharField (max 200 characters)
- `description`: TextField
- `created_by`: ForeignKey to User (who created the ticket)
- `assigned_to`: ForeignKey to User (optional, who is assigned to work on it)
- `status`: Choice field (open, in_progress, closed)
- `priority`: Choice field (low, medium, high, urgent)
- `created_at`: DateTimeField (auto)
- `updated_at`: DateTimeField (auto)

## URLs

- `/` - Home page
- `/login/` - User login page
- `/logout/` - User logout
- `/tickets/` - List user's tickets
- `/tickets/<id>/` - Ticket detail view
- `/tickets/create/` - Create new ticket
- `/admin/` - Django admin interface

## Next Steps

You can extend this application by adding:

- Comments on tickets
- File attachments
- Email notifications
- API endpoints
- More advanced filtering and search
