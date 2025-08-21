"""
Simple view to display email notification system status in admin.
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
import os
from tickets.email_utils import get_admin_emails


@staff_member_required
def email_system_status(request):
    """Display email system status and configuration."""
    
    # Check email configuration
    email_config = {
        'host': os.environ.get('DJANGO_EMAIL_HOST', 'Not set'),
        'port': os.environ.get('DJANGO_EMAIL_PORT', 'Not set'),
        'user': os.environ.get('DJANGO_EMAIL_HOST_USER', 'Not set'),
        'test_email': os.environ.get('DJANGO_TEST_EMAIL', 'Not set'),
        'site_url': os.environ.get('DJANGO_SITE_URL', 'Not set'),
    }
    
    # Check current mode
    email_utils_path = os.path.join('tickets', 'email_utils.py')
    current_mode = 'Unknown'
    if os.path.exists(email_utils_path):
        with open(email_utils_path, 'r') as f:
            content = f.read()
            current_mode = 'Test' if 'in_test=True' in content else 'Production'
    
    # Get admin emails
    admin_emails = get_admin_emails()
    
    context = {
        'title': 'Email Notification System Status',
        'email_config': email_config,
        'current_mode': current_mode,
        'admin_emails': admin_emails,
        'admin_count': len(admin_emails),
    }
    
    return render(request, 'admin/email_system_status.html', context)
