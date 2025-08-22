"""
Enhanced Security Features for Derby Tickets System.
Implements domain restrictions, brute force protection, and security monitoring.
"""
import re
import time
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpRequest
from django.contrib.auth.signals import user_login_failed, user_logged_in
from django.dispatch import receiver
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from typing import Optional, Dict, List, TYPE_CHECKING
from .logging_utils import log_security_event, log_auth_event

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

User = get_user_model()

# Security Configuration
ALLOWED_DOMAINS = getattr(settings, 'ALLOWED_EMAIL_DOMAINS', ['derbyfab.com'])
MAX_LOGIN_ATTEMPTS = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
LOGIN_LOCKOUT_TIME = getattr(settings, 'LOGIN_LOCKOUT_TIME', 300)  # 5 minutes
SUSPICIOUS_ACTIVITY_THRESHOLD = getattr(settings, 'SUSPICIOUS_ACTIVITY_THRESHOLD', 10)


class SecurityManager:
    """Centralized security management for the tickets system."""
    
    @staticmethod
    def is_domain_allowed(email: str) -> bool:
        """Check if email domain is in the allowed domains list."""
        if not email or '@' not in email:
            return False
        
        domain = email.split('@')[1].lower()
        return domain in [d.lower() for d in ALLOWED_DOMAINS]
    
    @staticmethod
    def get_lockout_key(identifier: str, attempt_type: str = 'login') -> str:
        """Generate cache key for lockout tracking."""
        return f"security_lockout_{attempt_type}_{identifier}"
    
    @staticmethod
    def get_attempt_key(identifier: str, attempt_type: str = 'login') -> str:
        """Generate cache key for attempt counting."""
        return f"security_attempts_{attempt_type}_{identifier}"
    
    @staticmethod
    def is_locked_out(identifier: str, attempt_type: str = 'login') -> bool:
        """Check if an identifier is currently locked out."""
        lockout_key = SecurityManager.get_lockout_key(identifier, attempt_type)
        return cache.get(lockout_key, False)
    
    @staticmethod
    def get_attempt_count(identifier: str, attempt_type: str = 'login') -> int:
        """Get current attempt count for an identifier."""
        attempt_key = SecurityManager.get_attempt_key(identifier, attempt_type)
        return cache.get(attempt_key, 0)
    
    @staticmethod
    def record_failed_attempt(identifier: str, request: HttpRequest = None, 
                            attempt_type: str = 'login') -> Dict[str, any]:
        """Record a failed attempt and check if lockout should be triggered."""
        attempt_key = SecurityManager.get_attempt_key(identifier, attempt_type)
        lockout_key = SecurityManager.get_lockout_key(identifier, attempt_type)
        
        # Increment attempt count
        attempts = cache.get(attempt_key, 0) + 1
        cache.set(attempt_key, attempts, LOGIN_LOCKOUT_TIME)
        
        result = {
            'attempts': attempts,
            'locked_out': False,
            'lockout_remaining': 0
        }
        
        # Check if lockout threshold reached
        if attempts >= MAX_LOGIN_ATTEMPTS:
            cache.set(lockout_key, True, LOGIN_LOCKOUT_TIME)
            result['locked_out'] = True
            result['lockout_remaining'] = LOGIN_LOCKOUT_TIME
            
            # Log security event
            log_security_event(
                'ACCOUNT_LOCKED',
                f'Account locked due to {attempts} failed {attempt_type} attempts',
                request,
                'WARNING',
                identifier
            )
        
        return result
    
    @staticmethod
    def clear_attempts(identifier: str, attempt_type: str = 'login'):
        """Clear attempt count for successful authentication."""
        attempt_key = SecurityManager.get_attempt_key(identifier, attempt_type)
        lockout_key = SecurityManager.get_lockout_key(identifier, attempt_type)
        cache.delete(attempt_key)
        cache.delete(lockout_key)
    
    @staticmethod
    def validate_login_attempt(username: str, request: HttpRequest = None) -> Dict[str, any]:
        """Validate login attempt against security policies."""
        result = {
            'allowed': True,
            'reason': '',
            'domain_valid': True,
            'locked_out': False,
            'attempts_remaining': MAX_LOGIN_ATTEMPTS
        }
        
        # Check domain restriction
        if '@' in username:  # Email-based username
            if not SecurityManager.is_domain_allowed(username):
                result['allowed'] = False
                result['domain_valid'] = False
                result['reason'] = f'Domain not authorized. Allowed domains: {", ".join(ALLOWED_DOMAINS)}'
                
                # Log unauthorized domain attempt
                log_security_event(
                    'UNAUTHORIZED_DOMAIN',
                    f'Login attempt from unauthorized domain: {username}',
                    request,
                    'WARNING',
                    username
                )
                
                return result
        
        # Check lockout status
        client_ip = request.META.get('REMOTE_ADDR', 'unknown') if request else 'unknown'
        
        # Check both username and IP-based lockouts
        for identifier in [username, client_ip]:
            if SecurityManager.is_locked_out(identifier):
                result['allowed'] = False
                result['locked_out'] = True
                result['reason'] = f'Account temporarily locked due to multiple failed attempts. Try again later.'
                break
            
            attempts = SecurityManager.get_attempt_count(identifier)
            result['attempts_remaining'] = min(result['attempts_remaining'], MAX_LOGIN_ATTEMPTS - attempts)
        
        return result
    
    @staticmethod
    def detect_suspicious_patterns(request: HttpRequest, user=None) -> List[str]:
        """Detect suspicious activity patterns."""
        suspicious_indicators = []
        
        if not request:
            return suspicious_indicators
        
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        
        # Check for common bot patterns
        bot_patterns = [
            r'bot', r'crawler', r'spider', r'scraper', r'curl', r'wget',
            r'automated', r'script', r'python-requests'
        ]
        
        for pattern in bot_patterns:
            if re.search(pattern, user_agent):
                suspicious_indicators.append(f'Automated tool detected: {pattern}')
        
        # Check for rapid requests (basic rate limiting)
        rate_key = f"rate_limit_{client_ip}"
        request_count = cache.get(rate_key, 0) + 1
        cache.set(rate_key, request_count, 60)  # 1 minute window
        
        if request_count > 30:  # More than 30 requests per minute
            suspicious_indicators.append(f'High request rate: {request_count} requests/minute')
        
        # Check for unusual access patterns
        if user and not user.is_active:
            suspicious_indicators.append('Inactive user account access attempt')
        
        return suspicious_indicators


def domain_required(allowed_domains: List[str] = None):
    """Decorator to restrict access to users with allowed email domains."""
    if allowed_domains is None:
        allowed_domains = ALLOWED_DOMAINS
    
    def check_domain(user):
        if not user.is_authenticated:
            return False
        
        # Superusers bypass domain restrictions
        if user.is_superuser:
            return True
        
        return SecurityManager.is_domain_allowed(user.email or user.username)
    
    return user_passes_test(check_domain)


def staff_required(view_func):
    """Decorator to require staff status for access."""
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required")
        
        if not request.user.is_staff:
            log_security_event(
                'UNAUTHORIZED_ACCESS',
                f'Non-staff user attempted to access staff-only view: {view_func.__name__}',
                request,
                'WARNING',
                request.user
            )
            raise PermissionDenied("Staff privileges required")
        
        return view_func(request, *args, **kwargs)
    
    return wrapped_view


class SecurityMiddleware:
    """Custom middleware for enhanced security monitoring."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Pre-request security checks
        self.process_request(request)
        
        response = self.get_response(request)
        
        # Post-request security monitoring
        self.process_response(request, response)
        
        return response
    
    def process_request(self, request):
        """Process incoming request for security monitoring."""
        # Detect suspicious patterns
        suspicious_indicators = SecurityManager.detect_suspicious_patterns(request)
        
        if suspicious_indicators:
            log_security_event(
                'SUSPICIOUS_REQUEST',
                f'Suspicious activity detected: {", ".join(suspicious_indicators)}',
                request,
                'WARNING'
            )
            
            # Rate limit suspicious requests
            client_ip = request.META.get('REMOTE_ADDR', 'unknown')
            suspicious_key = f"suspicious_{client_ip}"
            suspicious_count = cache.get(suspicious_key, 0) + 1
            cache.set(suspicious_key, suspicious_count, 3600)  # 1 hour
            
            if suspicious_count > SUSPICIOUS_ACTIVITY_THRESHOLD:
                log_security_event(
                    'POTENTIAL_ATTACK',
                    f'High suspicious activity count ({suspicious_count}) from IP: {client_ip}',
                    request,
                    'ERROR'
                )
    
    def process_response(self, request, response):
        """Process response for security monitoring."""
        # Monitor for error responses that might indicate attacks
        if response.status_code in [400, 401, 403, 404, 500]:
            client_ip = request.META.get('REMOTE_ADDR', 'unknown')
            error_key = f"errors_{client_ip}"
            error_count = cache.get(error_key, 0) + 1
            cache.set(error_key, error_count, 3600)  # 1 hour
            
            if error_count > 20:  # More than 20 errors per hour
                log_security_event(
                    'HIGH_ERROR_RATE',
                    f'High error rate ({error_count}) from IP: {client_ip}, Status: {response.status_code}',
                    request,
                    'WARNING'
                )


# Signal handlers for authentication events
@receiver(user_login_failed)
def handle_failed_login(sender, credentials, request, **kwargs):
    """Handle failed login attempts."""
    username = credentials.get('username', 'unknown')
    client_ip = request.META.get('REMOTE_ADDR', 'unknown') if request else 'unknown'
    
    # Record failed attempt for both username and IP
    for identifier in [username, client_ip]:
        result = SecurityManager.record_failed_attempt(identifier, request)
        
        if result['locked_out']:
            log_auth_event(
                'LOGIN_FAILED_LOCKOUT',
                username,
                request,
                False,
                f'Account locked after {result["attempts"]} attempts'
            )
        else:
            log_auth_event(
                'LOGIN_FAILED',
                username,
                request,
                False,
                f'Attempt {result["attempts"]}/{MAX_LOGIN_ATTEMPTS}'
            )


@receiver(user_logged_in)
def handle_successful_login(sender, request, user, **kwargs):
    """Handle successful login."""
    # Clear attempt counters
    client_ip = request.META.get('REMOTE_ADDR', 'unknown') if request else 'unknown'
    
    for identifier in [user.username, client_ip]:
        SecurityManager.clear_attempts(identifier)
    
    # Log successful login
    log_auth_event('LOGIN_SUCCESS', user.username, request, True)
    
    # Check for suspicious login patterns
    suspicious_indicators = SecurityManager.detect_suspicious_patterns(request, user)
    if suspicious_indicators:
        log_security_event(
            'SUSPICIOUS_LOGIN',
            f'Successful login with suspicious indicators: {", ".join(suspicious_indicators)}',
            request,
            'WARNING',
            user
        )


def check_password_strength(password: str) -> Dict[str, any]:
    """Check password strength and provide recommendations."""
    result = {
        'score': 0,
        'strength': 'Very Weak',
        'recommendations': []
    }
    
    if len(password) >= 8:
        result['score'] += 1
    else:
        result['recommendations'].append('Use at least 8 characters')
    
    if re.search(r'[a-z]', password):
        result['score'] += 1
    else:
        result['recommendations'].append('Include lowercase letters')
    
    if re.search(r'[A-Z]', password):
        result['score'] += 1
    else:
        result['recommendations'].append('Include uppercase letters')
    
    if re.search(r'\d', password):
        result['score'] += 1
    else:
        result['recommendations'].append('Include numbers')
    
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        result['score'] += 1
    else:
        result['recommendations'].append('Include special characters')
    
    # Determine strength level
    strength_levels = {
        0: 'Very Weak',
        1: 'Weak',
        2: 'Fair',
        3: 'Good',
        4: 'Strong',
        5: 'Very Strong'
    }
    
    result['strength'] = strength_levels.get(result['score'], 'Very Weak')
    
    return result
