"""
Session tracking middleware for security monitoring.
Updates user session activity automatically.
"""
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from .audit_models import UserSession


class SessionTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to automatically update user session activity.
    """
    
    def process_request(self, request):
        """Update last_activity for authenticated users."""
        if request.user.is_authenticated and hasattr(request, 'session'):
            session_key = request.session.session_key
            
            if session_key:
                # Update last activity for the current session
                UserSession.objects.filter(
                    user=request.user,
                    session_key=session_key,
                    is_active=True
                ).update(last_activity=timezone.now())
        
        return None
