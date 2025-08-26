"""
Authentication decorators for API endpoints.
Provides token-based authentication for API access.
"""
from functools import wraps
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
import hashlib
import hmac
import os


def require_api_token(view_func):
    """
    Decorator to require API token authentication.
    
    The token should be passed in the Authorization header as:
    Authorization: Bearer <token>
    
    Or as a query parameter:
    ?token=<token>
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get token from Authorization header or query parameter
        token = None
        
        # Check Authorization header first
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # If not in header, check query parameter
        if not token:
            token = request.GET.get('token')
        
        # If still no token, return error
        if not token:
            return JsonResponse({
                'success': False,
                'error': 'API token required. Include token in Authorization header as "Bearer <token>" or as query parameter "?token=<token>"',
                'timestamp': timezone.now().isoformat(),
            }, status=401)
        
        # Validate token
        if not validate_api_token(token):
            return JsonResponse({
                'success': False,
                'error': 'Invalid API token',
                'timestamp': timezone.now().isoformat(),
            }, status=403)
        
        # Token is valid, proceed with the view
        return view_func(request, *args, **kwargs)
    
    return wrapper


def validate_api_token(token):
    """
    Validate the provided API token.
    
    Args:
        token: The token to validate
        
    Returns:
        bool: True if token is valid, False otherwise
    """
    # Get the expected token from settings or environment
    expected_token = getattr(settings, 'API_TOKEN', None) or os.environ.get('API_TOKEN')
    
    if not expected_token:
        # If no token is configured, generate a warning
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("No API_TOKEN configured in settings or environment variables")
        return False
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(token, expected_token)


def generate_api_token():
    """
    Generate a secure API token.
    
    Returns:
        str: A secure random token
    """
    return os.urandom(32).hex()

