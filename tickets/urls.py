from django.urls import path
from . import views, security_views, upload_views

app_name = 'tickets'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/create/', views.create_ticket, name='create_ticket'),
    
    # Security Dashboard URLs
    path('security/', security_views.security_dashboard, name='security_dashboard'),
    path('security/events/', security_views.security_events, name='security_events'),
    path('security/logins/', security_views.login_attempts, name='login_attempts'),
    path('security/sessions/', security_views.active_sessions, name='active_sessions'),
    path('security/actions/', security_views.security_actions, name='security_actions'),
    path('security/api/', security_views.security_api, name='security_api'),
    
    # Data Upload Dashboard URLs
    path('data-admin/upload-dashboard/', upload_views.data_upload_dashboard, name='data_upload_dashboard'),
    path('data-admin/upload-tickets/', upload_views.upload_tickets, name='upload_tickets'),
    path('data-admin/upload-categories/', upload_views.upload_categories, name='upload_categories'),
    path('data-admin/process-upload/', upload_views.process_upload, name='process_upload'),
    path('data-admin/scan-database/', upload_views.scan_database, name='scan_database'),
    path('data-admin/download-sample/<str:sample_type>/', upload_views.download_sample_csv, name='download_sample_csv'),
]
