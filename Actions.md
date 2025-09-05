tickets = Ticket.objects.select_related(
    'created_by', 'assigned_to', 'category'
).filter(...)


from django.core.cache import cache
categories = cache.get_or_set('categories', 
    lambda: Category.objects.all().order_by('name'), 300)

from django.core.paginator import Paginator
paginator = Paginator(tickets, 25)  # 25 tickets per page


# settings.py
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Prevent XSS attacks
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")