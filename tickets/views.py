from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import models
from .models import Ticket, EndUser, Admin

# Create your views here.

# Restore proper authentication with User model linked to custom profiles

@login_required
def ticket_list(request):
    """Display a list of all tickets"""
    # Users can see all tickets they created or are assigned to
    tickets = Ticket.objects.filter(
        models.Q(created_by=request.user) | models.Q(assigned_to=request.user)
    ).distinct()
    context = {'tickets': tickets}
    return render(request, 'tickets/ticket_list.html', context)

@login_required
def ticket_detail(request, ticket_id):
    """Display details of a specific ticket"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    # Check if user has permission to view this ticket
    if ticket.created_by != request.user and ticket.assigned_to != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this ticket.")
        return redirect('tickets:ticket_list')
    context = {'ticket': ticket}
    return render(request, 'tickets/ticket_detail.html', context)

@login_required
def create_ticket(request):
    """Create a new ticket"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        priority = request.POST.get('priority', 'medium')
        assigned_to_id = request.POST.get('assigned_to')
        
        # Get assigned_to admin if provided
        assigned_to = None
        if assigned_to_id:
            try:
                assigned_to = User.objects.get(id=assigned_to_id, is_staff=True)
            except User.DoesNotExist:
                messages.error(request, 'Invalid admin assignment.')
        
        # Create ticket with current user as creator
        ticket = Ticket.objects.create(
            title=title,
            description=description,
            priority=priority,
            created_by=request.user,  # Automatically use logged-in user
            assigned_to=assigned_to
        )
        messages.success(request, 'Ticket created successfully!')
        return redirect('tickets:ticket_detail', ticket_id=ticket.id)
    
    # Get admin users for assignment dropdown (only for staff users to assign)
    admin_users = User.objects.filter(is_staff=True) if request.user.is_staff else []
    context = {'admin_users': admin_users}
    return render(request, 'tickets/create_ticket.html', context)

def home(request):
    """Home page view"""
    if request.user.is_authenticated:
        # Show dashboard with user's tickets
        user_tickets = Ticket.objects.filter(
            models.Q(created_by=request.user) | models.Q(assigned_to=request.user)
        ).distinct()[:5]  # Show latest 5 tickets
        
        # Get user profile info
        profile_info = {}
        if hasattr(request.user, 'end_user_profile'):
            profile = request.user.end_user_profile
            profile_info = {
                'type': 'End User',
                'role': profile.role,
                'location': profile.location,
                'department': profile.department
            }
        elif hasattr(request.user, 'admin_profile'):
            profile = request.user.admin_profile
            profile_info = {
                'type': 'Admin',
                'role': profile.role
            }
        
        context = {
            'user_tickets': user_tickets,
            'profile_info': profile_info,
            'total_tickets': Ticket.objects.count(),
            'total_end_users': EndUser.objects.count(),
            'total_admins': Admin.objects.count()
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
