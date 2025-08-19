from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from .models import Ticket, UserProfile, Comment, Category

# Create your views here.

# Restore proper authentication with User model linked to custom profiles

@login_required
def ticket_list(request):
    """Display a list of all tickets with filtering"""
    # Users can see all tickets they created or are assigned to
    tickets = Ticket.objects.filter(
        Q(created_by=request.user) | Q(assigned_to=request.user)
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
    
    context = {'tickets': tickets}
    return render(request, 'tickets/ticket_list.html', context)

@login_required
def ticket_detail(request, ticket_id):
    """Display details of a specific ticket with edit functionality and comments"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Check if user has permission to view this ticket
    if ticket.created_by != request.user and ticket.assigned_to != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this ticket.")
        return redirect('tickets:ticket_list')
    
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
                ticket.title = title
                ticket.description = description
                ticket.priority = priority
                ticket.status = status
                ticket.save()
                messages.success(request, 'Ticket updated successfully!')
                return redirect('tickets:ticket_detail', ticket_id=ticket.id)
            else:
                messages.error(request, 'Please fill in all required fields.')
        
        elif action == 'add_comment':
            # Handle comment adding
            comment_content = request.POST.get('comment_content', '').strip()
            is_internal = request.POST.get('is_internal') == 'on'
            
            if comment_content:
                Comment.objects.create(
                    ticket=ticket,
                    author=request.user,
                    content=comment_content,
                    is_internal=is_internal and request.user.is_staff  # Only staff can create internal comments
                )
                messages.success(request, 'Comment added successfully!')
                return redirect('tickets:ticket_detail', ticket_id=ticket.id)
            else:
                messages.error(request, 'Comment content is required.')
    
    # Get comments for the ticket
    comments = ticket.comments.all()
    
    # Filter out internal comments for non-staff users
    if not request.user.is_staff:
        comments = comments.filter(is_internal=False)
    
    context = {
        'ticket': ticket,
        'comments': comments,
        'can_add_internal_comments': request.user.is_staff
    }
    return render(request, 'tickets/ticket_detail.html', context)

@login_required
def create_ticket(request):
    """Create a new ticket"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        category_id = request.POST.get('category', '')
        priority = request.POST.get('priority', 'Medium')
        assigned_to_id = request.POST.get('assigned_to')
        
        # Validate required fields
        if not title or not priority:
            messages.error(request, 'Title and priority are required.')
            # Get categories and staff users for dropdowns
            categories = Category.objects.all().order_by('name')
            assignable_users = User.objects.filter(is_staff=True) if (request.user.is_staff or request.user.is_superuser) else []
            context = {'admin_users': assignable_users, 'categories': categories}
            return render(request, 'tickets/create_ticket.html', context)
        
        # Get category if provided
        category = None
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                messages.error(request, 'Invalid category selected.')
        
        # Get assigned_to user if provided (only allow if current user is staff/admin)
        assigned_to = None
        if assigned_to_id and (request.user.is_staff or request.user.is_superuser):
            try:
                # Only allow assignment to staff users
                assigned_to = User.objects.get(id=assigned_to_id, is_staff=True)
            except User.DoesNotExist:
                messages.error(request, 'Invalid user assignment. Can only assign to staff users.')
        
        # Create ticket with current user as creator
        ticket = Ticket.objects.create(
            title=title,
            description=description,
            category=category,  # Now it's a ForeignKey object
            priority=priority,
            created_by=request.user,  # Automatically use logged-in user
            assigned_to=assigned_to
        )
        messages.success(request, f'Ticket #{ticket.id} created successfully!')
        return redirect('tickets:ticket_detail', ticket_id=ticket.id)
    
    # Get categories and staff users for dropdowns
    categories = Category.objects.all().order_by('name')
    assignable_users = User.objects.filter(is_staff=True) if (request.user.is_staff or request.user.is_superuser) else []
    
    context = {'admin_users': assignable_users, 'categories': categories}
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
    """User login view"""
    if request.user.is_authenticated:
        return redirect('tickets:home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            next_url = request.GET.get('next', 'tickets:home')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'tickets/login.html')

def user_logout(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('tickets:login')
