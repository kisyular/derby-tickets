"""
Enhanced Security Service with Database Audit Trail Integration.
Combines file-based logging with comprehensive database tracking.
"""

import logging
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from django.http import HttpRequest
from django.db import models
from .audit_models import SecurityEvent, LoginAttempt, UserSession, AuditLog
from .security import SecurityManager  # Import our existing security manager
import json
from typing import Optional, Dict, Any


class AuditSecurityManager(SecurityManager):
    """
    Enhanced security manager that extends our existing SecurityManager
    with comprehensive database audit trail capabilities.
    """

    def __init__(self):
        super().__init__()
        self.security_logger = logging.getLogger("security")
        self.auth_logger = logging.getLogger("authentication")

    def get_client_ip(self, request: HttpRequest) -> str:
        """Get the client IP address from the request"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR", "127.0.0.1")
        return ip

    def get_failed_login_count(self, username: str, ip_address: str) -> int:
        """Get the count of recent failed login attempts for username and IP"""
        # Use the parent class method which works with cache
        username_attempts = self.get_attempt_count(username)
        ip_attempts = self.get_attempt_count(ip_address)

        # Return the higher of the two (more restrictive)
        return max(username_attempts, ip_attempts)

    def log_security_event(
        self,
        event_type: str,
        request: HttpRequest,
        user: Optional[User] = None,
        username_attempted: str = "",
        description: str = "",
        severity: str = "MEDIUM",
        success: bool = False,
        reason: str = "",
        metadata: Dict[str, Any] = None,
    ) -> SecurityEvent:
        """
        Log a security event to both file and database.

        Args:
            event_type: Type of security event (from SecurityEvent.EVENT_TYPES)
            request: Django HttpRequest object
            user: User object (if authenticated)
            username_attempted: Username for failed attempts
            description: Human-readable description
            severity: Event severity (LOW, MEDIUM, HIGH, CRITICAL)
            success: Whether the event was successful
            reason: Reason for failure (if applicable)
            metadata: Additional context data

        Returns:
            SecurityEvent: Created database record
        """
        if metadata is None:
            metadata = {}

        # Get request information
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        session_key = request.session.session_key or ""

        # Create database record
        security_event = SecurityEvent.objects.create(
            event_type=event_type,
            severity=severity,
            user=user,
            username_attempted=username_attempted,
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=session_key,
            description=description,
            success=success,
            reason=reason,
            metadata=metadata,
        )

        # Also log to file for redundancy
        log_message = f"{event_type} - {description}"
        if user:
            log_message += f" - User: {user.username}"
        elif username_attempted:
            log_message += f" - Username: {username_attempted}"
        log_message += f" - IP: {ip_address} - Success: {success}"
        if reason:
            log_message += f" - Reason: {reason}"

        if severity == "CRITICAL":
            self.security_logger.critical(log_message)
        elif severity == "HIGH":
            self.security_logger.error(log_message)
        elif severity == "MEDIUM":
            self.security_logger.warning(log_message)
        else:
            self.security_logger.info(log_message)

        return security_event

    def log_login_attempt(
        self,
        request: HttpRequest,
        username: str,
        status: str,
        user: Optional[User] = None,
        failure_reason: str = "",
        is_suspicious: bool = False,
        attempt_count: int = 1,
    ) -> LoginAttempt:
        """
        Log a login attempt to both file and database.

        Args:
            request: Django HttpRequest object
            username: Username being attempted
            status: LOGIN_SUCCESS, LOGIN_FAILED, LOGIN_BLOCKED, ACCOUNT_LOCKED
            user: User object (if successful or if user exists)
            failure_reason: Reason for failure
            is_suspicious: Whether attempt is flagged as suspicious
            attempt_count: Current attempt number in sequence

        Returns:
            LoginAttempt: Created database record
        """
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # Map status to database choices
        status_mapping = {
            "LOGIN_SUCCESS": "SUCCESS",
            "LOGIN_FAILED": "FAILED",
            "LOGIN_BLOCKED": "BLOCKED",
            "ACCOUNT_LOCKED": "LOCKED",
        }
        db_status = status_mapping.get(status, "FAILED")

        # Create database record
        login_attempt = LoginAttempt.objects.create(
            username=username,
            status=db_status,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
            is_suspicious=is_suspicious,
            lockout_triggered=(db_status == "LOCKED"),
            attempt_count=attempt_count,
            user=user,
        )

        # Log to file
        log_message = f"Login attempt - Username: {username} - Status: {status} - IP: {ip_address}"
        if failure_reason:
            log_message += f" - Reason: {failure_reason}"
        if is_suspicious:
            log_message += " - SUSPICIOUS"

        if db_status == "SUCCESS":
            self.auth_logger.info(log_message)
        else:
            self.auth_logger.warning(log_message)

        return login_attempt

    def create_user_session(
        self, request: HttpRequest, user: User, login_method: str = "password"
    ) -> UserSession:
        """
        Create a tracked user session.

        Args:
            request: Django HttpRequest object
            user: Authenticated user
            login_method: Method used for login (password, 2fa, sso, etc.)

        Returns:
            UserSession: Created session record
        """
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        session_key = request.session.session_key

        # Ensure session key exists
        if not session_key:
            request.session.cycle_key()
            session_key = request.session.session_key

        # End any existing active sessions for this user
        UserSession.objects.filter(user=user, is_active=True).update(
            is_active=False, ended_at=timezone.now()
        )

        # Create new session
        user_session = UserSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip_address,
            user_agent=user_agent,
            login_method=login_method,
        )

        self.auth_logger.info(
            f"New session created - User: {user.username} - IP: {ip_address}"
        )
        return user_session

    def end_user_session(
        self, request: HttpRequest, user: User, forced: bool = False
    ) -> None:
        """
        End a user session.

        Args:
            request: Django HttpRequest object
            user: User whose session to end
            forced: Whether logout was forced by admin
        """
        session_key = request.session.session_key

        if session_key:
            UserSession.objects.filter(
                user=user, session_key=session_key, is_active=True
            ).update(is_active=False, ended_at=timezone.now(), forced_logout=forced)

        logout_type = "forced" if forced else "normal"
        self.auth_logger.info(f"Session ended ({logout_type}) - User: {user.username}")

    def log_audit_event(
        self,
        request: HttpRequest,
        action: str,
        user: Optional[User] = None,
        target_user: Optional[User] = None,
        object_type: str = "",
        object_id: str = "",
        object_repr: str = "",
        changes: Dict[str, Any] = None,
        description: str = "",
        risk_level: str = "LOW",
    ) -> AuditLog:
        """
        Log an audit event for user actions.

        Args:
            request: Django HttpRequest object
            action: Action type (from AuditLog.ACTION_TYPES)
            user: User performing the action
            target_user: User being affected (for permission changes, etc.)
            object_type: Type of object being acted upon
            object_id: ID of the object
            object_repr: String representation of the object
            changes: Before/after values for changes
            description: Human-readable description
            risk_level: Risk assessment (LOW, MEDIUM, HIGH)

        Returns:
            AuditLog: Created audit record
        """
        if changes is None:
            changes = {}

        ip_address = self.get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        request_path = request.path

        audit_log = AuditLog.objects.create(
            action=action,
            user=user,
            target_user=target_user,
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            risk_level=risk_level,
        )

        # Log to file based on risk level
        log_message = f"Audit: {action} - {description} - User: {user.username if user else 'Anonymous'} - IP: {ip_address}"

        if risk_level == "HIGH":
            self.security_logger.error(log_message)
        elif risk_level == "MEDIUM":
            self.security_logger.warning(log_message)
        else:
            self.security_logger.info(log_message)

        return audit_log

    def validate_login_with_audit(
        self, request: HttpRequest, username: str, password: str
    ) -> Dict[str, Any]:
        """
        Enhanced login validation with comprehensive audit trail.
        Combines security checks with actual authentication and audit logging.

        Returns:
            Dict containing validation result and audit information
        """
        from django.contrib.auth import authenticate

        # Get current attempt count
        ip_address = self.get_client_ip(request)
        failed_attempts = self.get_failed_login_count(username, ip_address)

        # Call parent security validation first
        security_check = super().validate_login_attempt(username, request)

        # If security check fails, log and return
        if not security_check["allowed"]:
            result = {
                "success": False,
                "blocked": True,
                "locked": security_check.get("locked_out", False),
                "message": security_check.get("reason", "Login blocked"),
                "attempts_remaining": security_check.get("attempts_remaining", 0),
            }

            # Log the blocked attempt
            self.log_login_attempt(
                request=request,
                username=username,
                status="BLOCKED",
                failure_reason=result["message"],
                is_suspicious=True,
                attempt_count=failed_attempts + 1,
            )

            self.log_security_event(
                event_type="LOGIN_BLOCKED",
                request=request,
                username_attempted=username,
                description=f"Login blocked for {username}: {result['message']}",
                severity="HIGH",
                success=False,
                reason=result["message"],
            )

            return result

        # Security check passed, now try authentication
        user = authenticate(request, username=username, password=password)

        # Determine if this is suspicious
        is_suspicious = (
            failed_attempts >= 3  # Multiple failures
            or self.is_suspicious_ip(ip_address)
            or self.is_suspicious_user_agent(request.META.get("HTTP_USER_AGENT", ""))
        )

        if user is not None and user.is_active:
            # Successful authentication
            result = {
                "success": True,
                "user": user,
                "is_suspicious": is_suspicious,
                "message": "Login successful",
            }

            login_attempt = self.log_login_attempt(
                request=request,
                username=username,
                status="SUCCESS",
                user=user,
                is_suspicious=is_suspicious,
                attempt_count=1,  # Reset on success
            )

            self.log_security_event(
                event_type="LOGIN_SUCCESS",
                request=request,
                user=user,
                description=f"Successful login for user {username}",
                severity="LOW",
                success=True,
                metadata={"is_suspicious": is_suspicious},
            )

            result["login_attempt_id"] = login_attempt.id

        else:
            # Failed authentication
            result = {
                "success": False,
                "blocked": False,
                "locked": False,
                "message": "Invalid username or password",
                "attempts_remaining": security_check.get("attempts_remaining", 0) - 1,
                "is_suspicious": is_suspicious,
            }

            # Check if this attempt should trigger lockout
            new_attempt_count = failed_attempts + 1
            if new_attempt_count >= 5:  # MAX_LOGIN_ATTEMPTS
                result["locked"] = True
                result["message"] = "Account locked due to multiple failed attempts"

                # Record the failed attempt to trigger lockout
                self.record_failed_attempt(username, request)
                self.record_failed_attempt(ip_address, request)

            login_attempt = self.log_login_attempt(
                request=request,
                username=username,
                status="LOCKED" if result["locked"] else "FAILED",
                failure_reason=result["message"],
                is_suspicious=is_suspicious,
                attempt_count=new_attempt_count,
            )

            self.log_security_event(
                event_type="ACCOUNT_LOCKED" if result["locked"] else "LOGIN_FAILED",
                request=request,
                username_attempted=username,
                description=f"Failed login attempt for {username}: {result['message']}",
                severity="HIGH" if result["locked"] else "MEDIUM",
                success=False,
                reason=result["message"],
                metadata={
                    "is_suspicious": is_suspicious,
                    "attempt_count": new_attempt_count,
                    "lockout_triggered": result["locked"],
                },
            )

            result["login_attempt_id"] = login_attempt.id

        return result

    def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get a comprehensive security summary for the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Dict containing security metrics and statistics
        """
        cutoff = timezone.now() - timezone.timedelta(hours=hours)

        # Security events summary
        security_events = SecurityEvent.objects.filter(timestamp__gte=cutoff)
        failed_logins = LoginAttempt.objects.filter(
            timestamp__gte=cutoff, status__in=["FAILED", "BLOCKED", "LOCKED"]
        )

        # Active sessions
        active_sessions = UserSession.objects.filter(is_active=True)

        # Critical events
        critical_events = SecurityEvent.objects.filter(
            timestamp__gte=cutoff, severity="CRITICAL", resolved=False
        )

        return {
            "period_hours": hours,
            "security_events": {
                "total": security_events.count(),
                "by_type": {
                    row["event_type"]: row["count"]
                    for row in security_events.order_by()
                    .values("event_type")
                    .annotate(count=models.Count("id"))
                },
                "by_severity": {
                    row["severity"]: row["count"]
                    for row in security_events.order_by()
                    .values("severity")
                    .annotate(count=models.Count("id"))
                },
                "critical_unresolved": critical_events.count(),
            },
            "login_attempts": {
                "total": LoginAttempt.objects.filter(timestamp__gte=cutoff).count(),
                "failed": failed_logins.count(),
                "suspicious": failed_logins.filter(is_suspicious=True).count(),
                "unique_ips": failed_logins.values("ip_address").distinct().count(),
                "unique_usernames": failed_logins.values("username").distinct().count(),
            },
            "sessions": {
                "active": active_sessions.count(),
                "suspicious": active_sessions.filter(is_suspicious=True).count(),
                "long_running": sum(1 for s in active_sessions if s.is_long_running),
            },
            "top_threats": {
                "ips": list(
                    failed_logins.values("ip_address")
                    .annotate(count=models.Count("id"))
                    .order_by("-count")[:10]
                ),
                "usernames": list(
                    failed_logins.values("username")
                    .annotate(count=models.Count("id"))
                    .order_by("-count")[:10]
                ),
            },
        }

    def is_suspicious_ip(self, ip_address: str) -> bool:
        """Check if an IP address has suspicious activity patterns"""
        # Check recent failed attempts from this IP
        recent_failures = LoginAttempt.failed_attempts(
            ip_address=ip_address, hours=1
        ).count()

        return recent_failures >= 5

    def is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check if a user agent string is suspicious"""
        suspicious_patterns = [
            "bot",
            "crawler",
            "spider",
            "scraper",
            "curl",
            "wget",
            "python-requests",
            "automated",
            "script",
        ]

        user_agent_lower = user_agent.lower()
        return any(pattern in user_agent_lower for pattern in suspicious_patterns)

    def cleanup_inactive_sessions(self, hours: int = 24) -> int:
        """
        Clean up sessions that have been inactive for specified hours.

        Args:
            hours: Number of hours of inactivity after which to mark sessions as ended

        Returns:
            int: Number of sessions that were cleaned up
        """
        cutoff_time = timezone.now() - timedelta(hours=hours)

        # Mark sessions as inactive if they haven't been active recently
        updated_count = UserSession.objects.filter(
            is_active=True, last_activity__lt=cutoff_time
        ).update(is_active=False, ended_at=timezone.now())

        if updated_count > 0:
            self.auth_logger.info(
                f"Cleaned up {updated_count} inactive sessions older than {hours} hours"
            )

        return updated_count


# Global instance
audit_security_manager = AuditSecurityManager()
