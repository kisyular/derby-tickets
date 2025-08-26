"""
API views for ticket management system.
Provides JSON endpoints for external integrations.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from .models import Ticket
from .api_auth import require_api_token
import json


@csrf_exempt
@require_http_methods(["GET"])
@require_api_token
def api_tickets_list(request):
    """
    API endpoint to get all tickets in JSON format.
    
    Returns:
        JSON response with ticket data including:
        - ticket_number
        - title  
        - description
        - category
        - created_by
        - assigned_to
        - status
        - priority
        - location
        - department
        - created_at
        - closed_on
    """
    try:
        # Get all tickets with related data
        tickets = Ticket.objects.select_related(
            'category', 'created_by', 'assigned_to'
        ).all().order_by('-created_at')
        
        # Convert tickets to list of dictionaries
        tickets_data = []
        for ticket in tickets:
            ticket_data = {
                'ticket_number': ticket.ticket_number,
                'title': ticket.title,
                'description': ticket.description,
                'category': ticket.category.name if ticket.category else None,
                'created_by': f"{ticket.created_by.first_name} {ticket.created_by.last_name}".strip() if ticket.created_by else None,
                'assigned_to': f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}".strip() if ticket.assigned_to else None,
                'status': ticket.status,
                'priority': ticket.priority,
                'location': ticket.location,
                'department': ticket.department,
                'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
                'closed_on': ticket.closed_on.isoformat() if ticket.closed_on else None,
            }
            tickets_data.append(ticket_data)
        
        response_data = {
            'success': True,
            'count': len(tickets_data),
            'tickets': tickets_data,
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(response_data, safe=False, json_dumps_params={'indent': 2})
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@require_api_token
def api_ticket_detail(request, ticket_id):
    """
    API endpoint to get a specific ticket by ID.
    
    Args:
        ticket_id: The ID of the ticket to retrieve
        
    Returns:
        JSON response with single ticket data
    """
    try:
        ticket = Ticket.objects.select_related(
            'category', 'created_by', 'assigned_to'
        ).get(id=ticket_id)
        
        ticket_data = {
            'ticket_number': ticket.ticket_number,
            'title': ticket.title,
            'description': ticket.description,
            'category': ticket.category.name if ticket.category else None,
            'created_by': f"{ticket.created_by.first_name} {ticket.created_by.last_name}".strip() if ticket.created_by else None,
            'assigned_to': f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}".strip() if ticket.assigned_to else None,
            'status': ticket.status,
            'priority': ticket.priority,
            'location': ticket.location,
            'department': ticket.department,
            'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
            'closed_on': ticket.closed_on.isoformat() if ticket.closed_on else None,
        }
        
        response_data = {
            'success': True,
            'ticket': ticket_data,
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(response_data, json_dumps_params={'indent': 2})
        
    except Ticket.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Ticket with ID {ticket_id} not found',
            'timestamp': timezone.now().isoformat(),
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }, status=500)
