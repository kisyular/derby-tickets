"""
API authentication decorators and utilities.
"""
import secrets
from functools import wraps
from django.http import JsonResponse
from django.utils import timezone
from .models import APIToken


def generate_api_token():
    """Generate a secure random API token."""
    return secrets.token_urlsafe(48)  # 64-character URL-safe token


def require_api_token(view_func):
    """
    Decorator to require a valid API token for accessing an endpoint.
    
    Token can be provided in:
    1. Authorization header: "Bearer <token>"
    2. X-API-Token header: "<token>"
    3. Query parameter: "?token=<token>"
    
    Usage:
        @require_api_token
        def my_api_view(request):
            return JsonResponse({'data': 'protected'})
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = None
        
        # Try to get token from Authorization header (Bearer token)
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Try to get token from X-API-Token header
        if not token:
            token = request.META.get('HTTP_X_API_TOKEN', '')
        
        # Try to get token from query parameter
        if not token:
            token = request.GET.get('token', '')
        
        # Check if token was provided
        if not token:
            return JsonResponse({
                'success': False,
                'error': 'API token required',
                'detail': 'Provide token via Authorization header (Bearer <token>), X-API-Token header, or ?token= parameter',
                'timestamp': timezone.now().isoformat(),
            }, status=401)
        
        # Validate token
        try:
            api_token = APIToken.objects.get(token=token)
            
            if not api_token.is_valid():
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid or expired API token',
                    'timestamp': timezone.now().isoformat(),
                }, status=401)
            
            # Update last used timestamp
            api_token.update_last_used()
            
            # Add token info to request for potential use in view
            request.api_token = api_token
            
            # Call the original view
            return view_func(request, *args, **kwargs)
            
        except APIToken.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid API token',
                'timestamp': timezone.now().isoformat(),
            }, status=401)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Authentication error',
                'detail': str(e),
                'timestamp': timezone.now().isoformat(),
            }, status=500)
    
    return wrapper


def api_rate_limit(max_requests=100, window_minutes=60):
    """
    Decorator to add rate limiting to API endpoints.
    
    Args:
        max_requests: Maximum number of requests allowed
        window_minutes: Time window in minutes
    
    Usage:
        @require_api_token
        @api_rate_limit(max_requests=50, window_minutes=30)
        def my_api_view(request):
            return JsonResponse({'data': 'rate-limited'})
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Simple rate limiting implementation
            # In production, consider using Redis or Django cache framework
            
            if hasattr(request, 'api_token'):
                # Rate limiting logic could be implemented here
                # For now, just pass through
                pass
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
