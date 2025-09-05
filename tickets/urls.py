from django.urls import path
from . import views, security_views, api_views

app_name = "tickets"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),
    path("tickets/", views.ticket_list, name="ticket_list"),
    path("tickets/<int:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path("tickets/create/", views.create_ticket, name="create_ticket"),
    # Security Dashboard URLs
    path("security/", security_views.security_dashboard, name="security_dashboard"),
    path("security/events/", security_views.security_events, name="security_events"),
    path(
        "security/login-attempts/", security_views.login_attempts, name="login_attempts"
    ),
    path(
        "security/active-sessions/",
        security_views.active_sessions,
        name="active_sessions",
    ),
    path("security/audit-logs/", security_views.audit_logs, name="audit_logs"),
    path("security/actions/", security_views.security_actions, name="security_actions"),
    path("security/api/", security_views.security_api, name="security_api"),
    # Secure file serving - protected attachments
    path(
        "secure/tickets/<int:ticket_id>/<str:filename>/",
        views.serve_protected_file,
        name="secure_file",
    ),
    # API URLs
    path("api/tickets/", api_views.api_tickets_list, name="api_tickets_list"),
    path(
        "api/tickets/<int:ticket_id>/",
        api_views.api_ticket_detail,
        name="api_ticket_detail",
    ),
]
