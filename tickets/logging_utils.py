"""
Logging utilities for the Derby Tickets System.
Provides standardized logging functions for different types of events.
"""
import logging
import time
from functools import wraps
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from typing import Optional, Dict, Any, Union

User = get_user_model()

# Get loggers for different categories
app_logger = logging.getLogger('tickets')
security_logger = logging.getLogger('tickets.security')
auth_logger = logging.getLogger('tickets.auth')
email_logger = logging.getLogger('tickets.email')
performance_logger = logging.getLogger('tickets.performance')


def get_client_info(request):
    """Extract client information from request for logging."""
    if not request:
        return {
            'ip': 'Unknown',
            'user_agent': 'Unknown',
            'user': 'System'
        }
    
    # Get client IP (handles proxy headers)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'Unknown')
    
    return {
        'ip': ip,
        'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown')[:200],
        'user': str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'
    }


def log_ticket_event(event_type, ticket_id, user=None, request=None, extra_data=None):
    """Log ticket-related events."""
    client_info = get_client_info(request)
    user_str = str(user) if user else client_info['user']
    
    extra_data = extra_data or {}
    
    app_logger.info(
        f"Ticket {event_type} | Ticket ID: {ticket_id} | User: {user_str} | "
        f"IP: {client_info['ip']} | Extra: {extra_data}",
        extra={
            'event_type': event_type,
            'ticket_id': ticket_id,
            'user': user_str,
            'remote_addr': client_info['ip'],
            'user_agent': client_info['user_agent'],
            **extra_data
        }
    )


def log_auth_event(event_type, username="", request=None, success=True, reason=""):
    """Log authentication events."""
    client_info = get_client_info(request)
    level = auth_logger.info if success else auth_logger.warning
    
    level(
        f"Auth {event_type} | User: {username} | Success: {success} | "
        f"IP: {client_info['ip']} | Reason: {reason}",
        extra={
            'event_type': event_type,
            'username': username,
            'success': success,
            'reason': reason,
            'remote_addr': client_info['ip'],
            'user_agent': client_info['user_agent'],
            'user': username or 'Unknown'
        }
    )


def log_security_event(event_type, description, request=None, severity="WARNING", user=None):
    """Log security-related events."""
    client_info = get_client_info(request)
    user_str = str(user) if user else client_info['user']
    
    log_func = {
        'INFO': security_logger.info,
        'WARNING': security_logger.warning,
        'ERROR': security_logger.error,
        'CRITICAL': security_logger.critical
    }.get(severity, security_logger.warning)
    
    log_func(
        f"Security {event_type} | {description} | User: {user_str} | IP: {client_info['ip']}",
        extra={
            'event_type': event_type,
            'description': description,
            'severity': severity,
            'user': user_str,
            'remote_addr': client_info['ip'],
            'user_agent': client_info['user_agent']
        }
    )


def log_email_event(event_type, recipient, subject="", success=True, error=""):
    """Log email-related events."""
    level = email_logger.info if success else email_logger.error
    
    level(
        f"Email {event_type} | To: {recipient} | Subject: {subject[:100]} | "
        f"Success: {success} | Error: {error}",
        extra={
            'event_type': event_type,
            'recipient': recipient,
            'subject': subject[:100],
            'success': success,
            'error': error
        }
    )


def log_performance_event(operation, duration, details=None):
    """Log performance metrics."""
    details = details or {}
    
    performance_logger.info(
        f"Performance | Operation: {operation} | Duration: {duration:.3f}s | Details: {details}",
        extra={
            'operation': operation,
            'duration': duration,
            'details': details
        }
    )


def performance_monitor(operation_name=None):
    """Decorator to monitor function performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                log_performance_event(
                    operation=op_name,
                    duration=duration,
                    details={
                        'status': 'success',
                        'args_count': len(args),
                        'kwargs_count': len(kwargs)
                    }
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                log_performance_event(
                    operation=op_name,
                    duration=duration,
                    details={
                        'status': 'error',
                        'error': str(e),
                        'args_count': len(args),
                        'kwargs_count': len(kwargs)
                    }
                )
                
                app_logger.error(
                    f"Function {op_name} failed after {duration:.3f}s: {str(e)}",
                    exc_info=True
                )
                raise
                
        return wrapper
    return decorator


def log_user_action(action, user, target="", request=None, extra_data=None):
    """Log user actions for audit trail."""
    client_info = get_client_info(request)
    extra_data = extra_data or {}
    
    app_logger.info(
        f"User Action | Action: {action} | User: {user} | Target: {target} | "
        f"IP: {client_info['ip']} | Extra: {extra_data}",
        extra={
            'action': action,
            'user': str(user),
            'target': target,
            'remote_addr': client_info['ip'],
            'user_agent': client_info['user_agent'],
            **extra_data
        }
    )


def log_system_event(event_type, description, level="INFO", extra_data=None):
    """Log system-level events."""
    extra_data = extra_data or {}
    
    log_func = {
        'DEBUG': app_logger.debug,
        'INFO': app_logger.info,
        'WARNING': app_logger.warning,
        'ERROR': app_logger.error,
        'CRITICAL': app_logger.critical
    }.get(level.upper(), app_logger.info)
    
    log_func(
        f"System {event_type} | {description}",
        extra={
            'event_type': event_type,
            'description': description,
            **extra_data
        }
    )


# Convenience functions for common events
def log_ticket_created(ticket_id, user, request=None):
    """Log ticket creation."""
    log_ticket_event('CREATED', ticket_id, user, request)


def log_ticket_updated(ticket_id, user, changes, request=None):
    """Log ticket updates."""
    log_ticket_event('UPDATED', ticket_id, user, request, {'changes': changes})


def log_ticket_assigned(ticket_id, assigned_to, assigned_by, request=None):
    """Log ticket assignment."""
    log_ticket_event('ASSIGNED', ticket_id, assigned_by, request, 
                    {'assigned_to': str(assigned_to)})


def log_comment_added(ticket_id, comment_id, user, request=None):
    """Log comment addition."""
    log_ticket_event('COMMENT_ADDED', ticket_id, user, request, {'comment_id': comment_id})


def log_login_attempt(username, success, request=None, reason=""):
    """Log login attempts."""
    log_auth_event('LOGIN_ATTEMPT', username, request, success, reason)


def log_suspicious_activity(description, request=None, user=None):
    """Log suspicious activities."""
    log_security_event('SUSPICIOUS_ACTIVITY', description, request, 'WARNING', user)


def log_email_sent(recipient, subject, success=True, error=""):
    """Log email sending."""
    log_email_event('SENT', recipient, subject, success, error)
