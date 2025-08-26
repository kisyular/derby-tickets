from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from .models import Ticket, UserProfile, Comment, Category
from .security import SecurityManager, domain_required, staff_required
from .audit_security import audit_security_manager
from .logging_utils import log_auth_event, log_security_event

# Create your views here.

# Restore proper authentication with User model linked to custom profiles

@login_required
def ticket_list(request):
    """Display a list of all tickets with filtering"""
    # Users can see all tickets they created
    tickets = Ticket.objects.filter(
        Q(created_by=request.user)
    ).distinct()
    
    # Apply filters
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    search_query = request.GET.get('search')
    
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    
    if search_query:
        tickets = tickets.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
    
    # Order by most recent first
    tickets = tickets.order_by('-updated_at')

    # Calculate status and priority counts
    open_count = tickets.filter(status='Open').count()
    in_progress_count = tickets.filter(status='In Progress').count()
    closed_count = tickets.filter(status='Closed').count()
    urgent_count = tickets.filter(priority='Urgent').count()

    # For admin/staff users, get all tickets assigned to them (regardless of creator)
    assigned_tickets = []
    assigned_count = 0
    if request.user.is_staff or request.user.is_superuser:
        assigned_tickets = Ticket.objects.filter(assigned_to=request.user)
        
        # Apply the same filters to assigned tickets
        if status_filter:
            assigned_tickets = assigned_tickets.filter(status=status_filter)
        
        if priority_filter:
            assigned_tickets = assigned_tickets.filter(priority=priority_filter)
        
        if search_query:
            assigned_tickets = assigned_tickets.filter(
                Q(title__icontains=search_query) | Q(description__icontains=search_query)
            )
        
        # Order by most recent first
        assigned_tickets = assigned_tickets.order_by('-updated_at')
        assigned_count = assigned_tickets.count()

    context = {
        'tickets': tickets,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'closed_count': closed_count,
        'urgent_count': urgent_count,
        'assigned_tickets': assigned_tickets,
        'assigned_count': assigned_count,
    }
    return render(request, 'tickets/ticket_list.html', context)

@login_required
def ticket_detail(request, ticket_id):
    """Display details of a specific ticket with edit functionality and comments"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Check if user has permission to view this ticket
    if ticket.created_by != request.user and ticket.assigned_to != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this ticket.")
        return redirect('tickets:ticket_list')
    
    # Log the ticket view for audit trail
    audit_security_manager.log_audit_event(
        request=request,
        action='READ',
        user=request.user,
        object_type='Ticket',
        object_id=str(ticket.id),
        object_repr=str(ticket),
        description=f'Viewed Ticket #{ticket.id}: {ticket.title}',
        risk_level='LOW'
    )
    
    # Handle POST requests
    if request.method == 'POST':
        action = request.POST.get('action', 'edit_ticket')
        
        if action == 'edit_ticket' and (ticket.created_by == request.user or request.user.is_staff):
            # Handle ticket editing
            title = request.POST.get('title')
            description = request.POST.get('description')
            priority = request.POST.get('priority')
            status = request.POST.get('status')
            
            if title and priority and status:
                # Capture changes for audit trail
                changes = {}
                if ticket.title != title:
                    changes['title'] = {'old': ticket.title, 'new': title}
                if ticket.description != description:
                    changes['description'] = {'old': ticket.description, 'new': description}
                if ticket.priority != priority:
                    changes['priority'] = {'old': ticket.priority, 'new': priority}
                if ticket.status != status:
                    changes['status'] = {'old': ticket.status, 'new': status}
                
                ticket.title = title
                ticket.description = description
                ticket.priority = priority
                ticket.status = status
                # Set the user who made the changes for email notifications
                ticket._updated_by = request.user
                ticket.save()
                
                # Log the ticket update for audit trail
                audit_security_manager.log_audit_event(
                    request=request,
                    action='UPDATE',
                    user=request.user,
                    object_type='Ticket',
                    object_id=str(ticket.id),
                    object_repr=str(ticket),
                    changes=changes,
                    description=f'Updated Ticket #{ticket.id}: {ticket.title}',
                    risk_level='LOW'
                )
                
                messages.success(request, 'Ticket updated successfully!')
                return redirect('tickets:ticket_detail', ticket_id=ticket.id)
            else:
                messages.error(request, 'Please fill in all required fields.')
        
        elif action == 'add_comment':
            # Handle comment adding
            comment_content = request.POST.get('comment_content', '').strip()
            is_internal = request.POST.get('is_internal') == 'on'
            
            if comment_content:
                comment = Comment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=comment_content,
                    is_internal=is_internal and request.user.is_staff  # Only staff can create internal comments
                )
                
                # Log the comment creation for audit trail
                audit_security_manager.log_audit_event(
                    request=request,
                    action='CREATE',
                    user=request.user,
                    object_type='Comment',
                    object_id=str(comment.id),
                    object_repr=f'Comment on Ticket #{ticket.id}',
                    description=f'Added comment to Ticket #{ticket.id}: {ticket.title}',
                    risk_level='LOW',
                    changes={'ticket_id': ticket.id, 'is_internal': is_internal}
                )
                
                messages.success(request, 'Comment added successfully!')
                return redirect('tickets:ticket_detail', ticket_id=ticket.id)
            else:
                messages.error(request, 'Comment content is required.')
    
    # Get comments for the ticket (newest first)
    comments = ticket.comments.all().order_by('-created_at')
    
    # Filter out internal comments for non-staff users
    if not request.user.is_staff:
        comments = comments.filter(is_internal=False)
    
    # Get related tickets using basic rule-based approach
    try:
        from .related_tickets import get_related_tickets_for_display
        related_tickets = get_related_tickets_for_display(ticket)
    except ImportError:
        related_tickets = []
    
    context = {
        'ticket': ticket,
        'comments': comments,
        'related_tickets': related_tickets,
        'can_add_internal_comments': request.user.is_staff
    }
    return render(request, 'tickets/ticket_detail.html', context)

@login_required
def create_ticket(request):
    """Create a new ticket with optional file attachments"""
    from .forms import TicketWithAttachmentsForm
    from .models import TicketAttachment
    
    if request.method == 'POST':
        form = TicketWithAttachmentsForm(request.POST, request.FILES)
        
        if form.is_valid():
            # Create the ticket
            ticket = Ticket.objects.create(
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                category=form.cleaned_data['category'],
                priority=form.cleaned_data['priority'],
                location=form.cleaned_data['location'],
                department=form.cleaned_data['department'],
                created_by=request.user
            )
            
            # Handle file attachments
            attachments = request.FILES.getlist('attachments')
            for attachment in attachments:
                if attachment:
                    TicketAttachment.objects.create(
                        ticket=ticket,
                        file=attachment,
                        original_filename=attachment.name,
                        uploaded_by=request.user
                    )
            
            attachment_count = len([f for f in attachments if f])
            success_msg = f'Ticket #{ticket.id} created successfully!'
            if attachment_count > 0:
                success_msg += f' ({attachment_count} file{"s" if attachment_count > 1 else ""} attached)'
            
            messages.success(request, success_msg)
            return redirect('tickets:ticket_detail', ticket_id=ticket.id)
        else:
            # Form has errors
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TicketWithAttachmentsForm()
    
    # Get categories for the form
    categories = Category.objects.all().order_by('name')
    assignable_users = User.objects.filter(is_staff=True) if (request.user.is_staff or request.user.is_superuser) else []
    
    context = {
        'form': form,
        'admin_users': assignable_users, 
        'categories': categories
    }
    return render(request, 'tickets/create_ticket.html', context)

def home(request):
    """Home page view with enhanced dashboard"""
    if request.user.is_authenticated:
        # Get comprehensive ticket statistics
        user_tickets = Ticket.objects.filter(
            Q(created_by=request.user) | Q(assigned_to=request.user)
        ).distinct()
        
        # Recent tickets (last 5)
        recent_tickets = user_tickets.order_by('-updated_at')[:5]
        
        # Ticket counts by status
        total_tickets = user_tickets.count()
        open_tickets = user_tickets.filter(status='Open').count()
        in_progress_tickets = user_tickets.filter(status='In Progress').count()
        closed_tickets = user_tickets.filter(status='Closed').count()
        
        # Get user profile info
        profile_info = {}
        if hasattr(request.user, 'userprofile'):
            profile = request.user.userprofile
            profile_info = {
                'type': 'Admin User' if request.user.is_staff else 'Regular User',
                'role': profile.role or 'Not Set',
                'location': profile.location or 'Not Set',
                'department': profile.department or 'Not Set'
            }
        else:
            profile_info = {
                'type': 'Admin User' if request.user.is_staff else 'Regular User',
                'role': 'Not Set',
                'location': 'Not Set',
                'department': 'Not Set'
            }
        
        context = {
            'recent_tickets': recent_tickets,
            'profile_info': profile_info,
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'in_progress_tickets': in_progress_tickets,
            'closed_tickets': closed_tickets,
            'total_users': User.objects.count(),
            'total_staff': User.objects.filter(is_staff=True).count()
        }
    else:
        context = {}
    
    return render(request, 'tickets/home.html', context)

def user_login(request):
    """Enhanced user login view with comprehensive audit trail"""
    if request.user.is_authenticated:
        return redirect('tickets:home')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            messages.error(request, 'Please provide both username and password.')
            return render(request, 'tickets/login.html')
        
        # Enhanced security validation with audit trail
        validation_result = audit_security_manager.validate_login_with_audit(
            request, username, password
        )
        
        if validation_result['success']:
            # Get the user and log them in
            user = authenticate(request, username=username, password=password)
            
            if user is not None and user.is_active:
                # Final security checks
                if '@' in username and not audit_security_manager.is_domain_allowed(username):
                    audit_security_manager.log_security_event(
                        event_type='UNAUTHORIZED_DOMAIN',
                        request=request,
                        user=user,
                        description=f'Login blocked: unauthorized domain {username}',
                        severity='HIGH',
                        success=False,
                        reason='Domain not authorized'
                    )
                    messages.error(request, 'Domain not authorized for access.')
                    return render(request, 'tickets/login.html')
                
                # Successful login
                login(request, user)
                
                # Log successful session creation (session created by signal)
                audit_security_manager.log_audit_event(
                    request=request,
                    action='LOGIN',
                    user=user,
                    description=f'User {username} logged in successfully',
                    risk_level='LOW'
                )
                
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                
                # Security notification for suspicious login
                if validation_result.get('is_suspicious'):
                    messages.warning(request, 'This login has been flagged for security review.')
                
                next_url = request.GET.get('next', 'tickets:home')
                return redirect(next_url)
            
            elif user and not user.is_active:
                audit_security_manager.log_security_event(
                    event_type='LOGIN_BLOCKED',
                    request=request,
                    user=user,
                    description=f'Login blocked: inactive user {username}',
                    severity='MEDIUM',
                    success=False,
                    reason='Account is disabled'
                )
                messages.error(request, 'Account is disabled. Contact administrator.')
        
        else:
            # Handle failed login
            error_message = validation_result.get('message', 'Invalid username or password.')
            
            # Add additional context for user
            if validation_result.get('locked'):
                error_message += f" Account locked for {validation_result.get('lockout_duration', 30)} minutes."
            elif validation_result.get('attempts_remaining', 0) > 0:
                attempts_left = validation_result.get('attempts_remaining', 0)
                if attempts_left <= 2:
                    error_message += f" {attempts_left} attempts remaining."
            
            messages.error(request, error_message)
    
    return render(request, 'tickets/login.html')

def user_logout(request):
    """Enhanced user logout view with audit trail"""
    if request.user.is_authenticated:
        # Log the logout
        audit_security_manager.end_user_session(request, request.user)
        audit_security_manager.log_audit_event(
            request=request,
            action='LOGOUT',
            user=request.user,
            description=f'User {request.user.username} logged out',
            risk_level='LOW'
        )
        
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
    
    return redirect('tickets:login')
