"""
Django management command to show Related Tickets functionality
Usage: python manage.py show_related_tickets <ticket_id>
"""
from django.core.management.base import BaseCommand
from tickets.models import Ticket
from tickets.related_tickets import get_related_tickets_for_display


class Command(BaseCommand):
    help = 'Show related tickets for a given ticket ID'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'ticket_id',
            type=int,
            help='ID of the ticket to find related tickets for'
        )
        parser.add_argument(
            '--max-results',
            type=int,
            default=5,
            help='Maximum number of related tickets to show'
        )
    
    def handle(self, *args, **options):
        ticket_id = options['ticket_id']
        max_results = options['max_results']
        
        try:
            ticket = Ticket.objects.get(id=ticket_id)
        except Ticket.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Ticket with ID {ticket_id} not found')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'\nAnalyzing ticket #{ticket.id}: "{ticket.title}"')
        )
        self.stdout.write(f"Category: {ticket.category.name if ticket.category else 'None'}")
        self.stdout.write(f"Priority: {ticket.priority}")
        self.stdout.write(f"Status: {ticket.status}")
        self.stdout.write(f"Created by: {ticket.created_by.username}")
        self.stdout.write("-" * 50)
        
        # Find related tickets
        related_tickets = get_related_tickets_for_display(ticket)
        
        if related_tickets:
            self.stdout.write(
                self.style.SUCCESS(f'\nFound {len(related_tickets)} related tickets:')
            )
            
            for i, related in enumerate(related_tickets[:max_results], 1):
                self.stdout.write(f"\n{i}. Ticket #{related['ticket'].id}")
                self.stdout.write(f"   Title: {related['ticket'].title}")
                self.stdout.write(f"   Reason: {related['reason']}")
                self.stdout.write(f"   Score: {related['score']:.2f}")
                self.stdout.write(f"   Status: {related['ticket'].status}")
                self.stdout.write(f"   Priority: {related['ticket'].priority}")
                if related['ticket'].category:
                    self.stdout.write(f"   Category: {related['ticket'].category.name}")
        else:
            self.stdout.write(
                self.style.WARNING('\nNo related tickets found.')
            )
        
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Related Tickets Analysis Complete!")
