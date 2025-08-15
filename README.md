# Django Ticket Management System

A modern ticket management system built with Django.

## Features

- Create, view, and manage tickets
- Priority levels (Low, Medium, High, Urgent)
- Status tracking (Open, In Progress, Closed)
- Clean and responsive Bootstrap UI
- Django Admin interface
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

4. Create a superuser:

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

1. **Home Page**: Welcome page with navigation
2. **All Tickets**: View all tickets with status and priority
3. **Create Ticket**: Form to create new tickets
4. **Ticket Details**: View detailed information about a specific ticket
5. **Django Admin**: Manage tickets through the admin interface at /admin/

## Models

### Ticket

- `title`: CharField (max 200 characters)
- `description`: TextField
- `status`: Choice field (open, in_progress, closed)
- `priority`: Choice field (low, medium, high, urgent)
- `created_at`: DateTimeField (auto)
- `updated_at`: DateTimeField (auto)

## URLs

- `/` - Home page
- `/tickets/` - List all tickets
- `/tickets/<id>/` - Ticket detail view
- `/tickets/create/` - Create new ticket
- `/admin/` - Django admin interface

## Next Steps

You can extend this application by adding:

- User authentication and permissions
- Comments on tickets
- File attachments
- Email notifications
- API endpoints
- More advanced filtering and search
