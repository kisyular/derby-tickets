"""
Security Dashboard Views for Admin Interface
Provides comprehensive security monitoring and management through web interface.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.core.cache import cache
from django.contrib.auth.models import User
from datetime import timedelta
import json

from .audit_models import SecurityEvent, LoginAttempt, UserSession, AuditLog
from .audit_security import audit_security_manager
from .security import SecurityManager


def is_admin(user):
    """Check if user is admin/staff"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@user_passes_test(is_admin)
def security_dashboard(request):
    """Main security dashboard view"""
    hours = int(request.GET.get('hours', 24))
    
    # Get comprehensive security summary
    summary = audit_security_manager.get_security_summary(hours)
    
    # Get recent events for timeline
    cutoff = timezone.now() - timedelta(hours=hours)
    recent_events = SecurityEvent.objects.filter(
        timestamp__gte=cutoff
    ).order_by('-timestamp')[:20]
    
    recent_attempts = LoginAttempt.objects.filter(
        timestamp__gte=cutoff
    ).order_by('-timestamp')[:20]
    
    active_sessions = UserSession.objects.filter(
        is_active=True
    ).order_by('-last_activity')[:20]
    
    # Get critical unresolved events
    critical_events = SecurityEvent.objects.filter(
        severity='CRITICAL',
        resolved=False
    ).order_by('-timestamp')[:10]
    
    # Calculate some additional metrics
    total_users = User.objects.count()
    admin_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).count()
    
    context = {
        'summary': summary,
        'recent_events': recent_events,
        'recent_attempts': recent_attempts,
        'active_sessions': active_sessions,
        'critical_events': critical_events,
        'hours': hours,
        'total_users': total_users,
        'admin_users': admin_users,
        'time_ranges': [1, 6, 12, 24, 48, 168],  # 1h, 6h, 12h, 1d, 2d, 1w
    }
    
    return render(request, 'tickets/admin/security_dashboard.html', context)


@user_passes_test(is_admin)
def security_events(request):
    """Security events management view"""
    events = SecurityEvent.objects.all().order_by('-timestamp')
    
    # Filtering
    event_type = request.GET.get('event_type')
    severity = request.GET.get('severity')
    resolved = request.GET.get('resolved')
    hours = int(request.GET.get('hours', 24))
    is_ajax = request.GET.get('ajax') == '1'
    
    if hours:
        cutoff = timezone.now() - timedelta(hours=hours)
        events = events.filter(timestamp__gte=cutoff)
    
    if event_type:
        events = events.filter(event_type=event_type)
    
    if severity:
        events = events.filter(severity=severity)
    
    if resolved == 'true':
        events = events.filter(resolved=True)
    elif resolved == 'false':
        events = events.filter(resolved=False)
    
    # Pagination
    events = events[:100]  # Limit for performance
    
    context = {
        'events': events,
        'event_types': SecurityEvent.EVENT_TYPES,
        'severity_levels': SecurityEvent.SEVERITY_LEVELS,
        'current_filters': {
            'event_type': event_type,
            'severity': severity,
            'resolved': resolved,
            'hours': hours
        },
        'is_ajax': is_ajax
    }
    
    # Use different template for AJAX requests
    template = 'tickets/admin/security_events_ajax.html' if is_ajax else 'tickets/admin/security_events_ajax.html'
    return render(request, template, context)


@user_passes_test(is_admin)
def login_attempts(request):
    """Login attempts monitoring view"""
    attempts = LoginAttempt.objects.all().order_by('-timestamp')
    
    # Filtering
    status = request.GET.get('status')
    suspicious = request.GET.get('suspicious')
    hours = int(request.GET.get('hours', 24))
    is_ajax = request.GET.get('ajax') == '1'
    
    if hours:
        cutoff = timezone.now() - timedelta(hours=hours)
        attempts = attempts.filter(timestamp__gte=cutoff)
    
    if status:
        attempts = attempts.filter(status=status)
    
    if suspicious == 'true':
        attempts = attempts.filter(is_suspicious=True)
    elif suspicious == 'false':
        attempts = attempts.filter(is_suspicious=False)
    
    # Pagination
    attempts = attempts[:100]  # Limit for performance
    
    context = {
        'attempts': attempts,
        'status_choices': LoginAttempt.STATUS_CHOICES,
        'current_filters': {
            'status': status,
            'suspicious': suspicious,
            'hours': hours
        },
        'is_ajax': is_ajax
    }
    
    # Use different template for AJAX requests
    template = 'tickets/admin/login_attempts_ajax.html' if is_ajax else 'tickets/admin/login_attempts_ajax.html'
    return render(request, template, context)


@user_passes_test(is_admin)
def active_sessions(request):
    """Active sessions monitoring view"""
    sessions = UserSession.objects.filter(is_active=True).order_by('-last_activity')
    is_ajax = request.GET.get('ajax') == '1'
    
    context = {
        'sessions': sessions,
        'is_ajax': is_ajax
    }
    
    # Use different template for AJAX requests
    template = 'tickets/admin/active_sessions_ajax.html' if is_ajax else 'tickets/admin/active_sessions_ajax.html'
    return render(request, template, context)


@user_passes_test(is_admin)
def audit_logs(request):
    """Audit logs view"""
    logs = AuditLog.objects.all().order_by('-timestamp')
    
    # Filtering
    action = request.GET.get('action')
    risk_level = request.GET.get('risk_level')
    hours = int(request.GET.get('hours', 24))
    
    if hours:
        cutoff = timezone.now() - timedelta(hours=hours)
        logs = logs.filter(timestamp__gte=cutoff)
    
    if action:
        logs = logs.filter(action=action)
    
    if risk_level:
        logs = logs.filter(risk_level=risk_level)
    
    # Pagination
    logs = logs[:100]  # Limit for performance
    
    context = {
        'logs': logs,
        'action_types': AuditLog.ACTION_TYPES,
        'risk_levels': [('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')],
        'current_filters': {
            'action': action,
            'risk_level': risk_level,
            'hours': hours
        }
    }
    
    return render(request, 'tickets/admin/audit_logs.html', context)


@user_passes_test(is_admin)
def security_actions(request):
    """Security actions and management view"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'unlock_user':
            username = request.POST.get('username')
            if username:
                SecurityManager.clear_attempts(username)
                messages.success(request, f'User "{username}" has been unlocked.')
                
                # Log the action
                SecurityEvent.objects.create(
                    event_type='OTHER',
                    severity='MEDIUM',
                    user=request.user,
                    username_attempted=username,
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    description=f'Account manually unlocked by admin {request.user.username}',
                    success=True,
                    metadata={'action': 'manual_unlock', 'admin_action': True}
                )
        
        elif action == 'unlock_ip':
            ip_address = request.POST.get('ip_address')
            if ip_address:
                SecurityManager.clear_attempts(ip_address)
                messages.success(request, f'IP "{ip_address}" has been unlocked.')
                
                # Log the action
                SecurityEvent.objects.create(
                    event_type='OTHER',
                    severity='MEDIUM',
                    user=request.user,
                    ip_address=ip_address,
                    description=f'IP address manually unlocked by admin {request.user.username}',
                    success=True,
                    metadata={'action': 'manual_unlock', 'admin_action': True}
                )
        
        elif action == 'resolve_event':
            event_id = request.POST.get('event_id')
            if event_id:
                try:
                    event = SecurityEvent.objects.get(id=event_id)
                    event.resolved = True
                    event.resolved_by = request.user
                    event.resolved_at = timezone.now()
                    event.notes = request.POST.get('notes', '')
                    event.save()
                    messages.success(request, 'Security event marked as resolved.')
                except SecurityEvent.DoesNotExist:
                    messages.error(request, 'Security event not found.')
        
        elif action == 'force_logout':
            session_id = request.POST.get('session_id')
            if session_id:
                try:
                    session = UserSession.objects.get(id=session_id, is_active=True)
                    session.is_active = False
                    session.ended_at = timezone.now()
                    session.forced_logout = True
                    session.save()
                    messages.success(request, f'User "{session.user.username}" has been logged out.')
                except UserSession.DoesNotExist:
                    messages.error(request, 'Session not found.')
        
        elif action == 'clear_all_lockouts':
            cache.clear()  # Clear all lockouts
            messages.success(request, 'All account lockouts have been cleared.')
            
            # Log the action
            SecurityEvent.objects.create(
                event_type='OTHER',
                severity='HIGH',
                user=request.user,
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                description=f'All lockouts cleared by admin {request.user.username}',
                success=True,
                metadata={'action': 'mass_unlock', 'admin_action': True}
            )
        
        return redirect('tickets:security_actions')
    
    # Get current lockouts
    locked_accounts = []
    locked_ips = []
    
    # Check recent failed attempts to find lockouts
    recent_attempts = LoginAttempt.objects.filter(
        timestamp__gte=timezone.now() - timedelta(minutes=30),
        status__in=['FAILED', 'BLOCKED', 'LOCKED']
    ).values('username', 'ip_address').distinct()
    
    for attempt in recent_attempts:
        username = attempt['username']
        ip_address = attempt['ip_address']
        
        if SecurityManager.is_locked_out(username):
            attempts = SecurityManager.get_attempt_count(username)
            locked_accounts.append({'username': username, 'attempts': attempts})
        
        if SecurityManager.is_locked_out(ip_address):
            attempts = SecurityManager.get_attempt_count(ip_address)
            if not any(ip['ip_address'] == ip_address for ip in locked_ips):
                locked_ips.append({'ip_address': ip_address, 'attempts': attempts})
    
    # Get unresolved critical events
    critical_events = SecurityEvent.objects.filter(
        severity='CRITICAL',
        resolved=False
    ).order_by('-timestamp')[:10]
    
    is_ajax = request.GET.get('ajax') == '1'
    
    context = {
        'locked_accounts': locked_accounts,
        'locked_ips': locked_ips,
        'critical_events': critical_events,
        'is_ajax': is_ajax
    }
    
    # Use different template for AJAX requests
    template = 'tickets/admin/security_actions_ajax.html' if is_ajax else 'tickets/admin/security_actions_ajax.html'
    return render(request, template, context)


@user_passes_test(is_admin)
def security_api(request):
    """API endpoints for security dashboard"""
    endpoint = request.GET.get('endpoint')
    hours = int(request.GET.get('hours', 24))
    
    if endpoint == 'summary':
        summary = audit_security_manager.get_security_summary(hours)
        return JsonResponse(summary)
    
    elif endpoint == 'chart_data':
        # Get data for charts
        cutoff = timezone.now() - timedelta(hours=hours)
        
        # Login attempts over time
        attempts_data = []
        for i in range(hours):
            hour_start = cutoff + timedelta(hours=i)
            hour_end = hour_start + timedelta(hours=1)
            count = LoginAttempt.objects.filter(
                timestamp__gte=hour_start,
                timestamp__lt=hour_end
            ).count()
            attempts_data.append({
                'hour': hour_start.strftime('%H:%M'),
                'count': count
            })
        
        # Event severity distribution
        severity_data = SecurityEvent.objects.filter(
            timestamp__gte=cutoff
        ).values('severity').annotate(count=Count('id'))
        
        return JsonResponse({
            'attempts_over_time': attempts_data,
            'severity_distribution': list(severity_data)
        })
    
    return JsonResponse({'error': 'Invalid endpoint'}, status=400)
