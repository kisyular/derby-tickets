"""
Computer information utilities for linking tickets with computer data.
"""

from django.db import connections
from django.db import models
from django.contrib.auth.models import User
from .models import ComputerInfo, TicketComputerInfo
import logging

logger = logging.getLogger(__name__)


def get_computer_info_by_user(username):
    """
    Get computer information for a user from the computers database.

    Args:
        username (str): The username to search for

    Returns:
        ComputerInfo or None: Computer information if found, None otherwise
    """
    try:
        # Use the computers database connection
        computer_info = (
            ComputerInfo.objects.using("computers")
            .filter(current_user__iexact=username)
            .first()
        )

        if computer_info:
            logger.info(
                f"Found computer info for user {username}: {computer_info.hostname}"
            )
            return computer_info
        else:
            logger.warning(f"No computer information found for user: {username}")
            return None

    except Exception as e:
        logger.error(f"Error fetching computer info for user {username}: {str(e)}")
        return None


def get_computer_info_by_ip(client_ip):
    """
    Get computer information by client IP address.

    Args:
        client_ip (str): The client IP address

    Returns:
        ComputerInfo or None: Computer information if found, None otherwise
    """
    try:
        computer_info = (
            ComputerInfo.objects.using("computers").filter(client_ip=client_ip).first()
        )

        if computer_info:
            logger.info(
                f"Found computer info for IP {client_ip}: {computer_info.hostname}"
            )
            return computer_info
        else:
            logger.warning(f"No computer information found for IP: {client_ip}")
            return None

    except Exception as e:
        logger.error(f"Error fetching computer info for IP {client_ip}: {str(e)}")
        return None


def get_computer_info_by_hostname(hostname):
    """
    Get computer information by hostname.

    Args:
        hostname (str): The hostname to search for

    Returns:
        ComputerInfo or None: Computer information if found, None otherwise
    """
    try:
        computer_info = (
            ComputerInfo.objects.using("computers")
            .filter(hostname__iexact=hostname)
            .first()
        )

        if computer_info:
            logger.info(f"Found computer info for hostname {hostname}")
            return computer_info
        else:
            logger.warning(f"No computer information found for hostname: {hostname}")
            return None

    except Exception as e:
        logger.error(f"Error fetching computer info for hostname {hostname}: {str(e)}")
        return None


def link_ticket_to_computer_info(ticket, request=None):
    """
    Link a ticket to computer information based on the creating user.
    This function tries multiple methods to find the computer information.

    Args:
        ticket: The Ticket instance
        request: The HTTP request object (optional, for IP detection)

    Returns:
        TicketComputerInfo or None: Created computer info link or None if not found
    """
    try:
        computer_info = None

        # Method 1: Try to find by username
        if ticket.created_by and ticket.created_by.username:
            computer_info = get_computer_info_by_user(ticket.created_by.username)

        # Method 2: Try to find by client IP if request is available
        if not computer_info and request:
            client_ip = get_client_ip(request)
            if client_ip:
                computer_info = get_computer_info_by_ip(client_ip)

        # Method 3: Could add more methods here (hostname detection, etc.)

        if computer_info:
            # Create a snapshot of the computer info linked to this ticket
            ticket_computer_info = TicketComputerInfo.objects.create(
                ticket=ticket,
                serial_number=computer_info.serial_number,
                hostname=computer_info.hostname,
                wan_ip=computer_info.wan_ip,
                isp=computer_info.isp,
                wan_geo_loc=computer_info.wan_geo_loc,
                client_ip=computer_info.client_ip,
                mac=computer_info.mac,
                derby_plant_loc=computer_info.derby_plant_loc,
                current_user=computer_info.current_user,
                domain=computer_info.domain,
                pc_make_model=computer_info.pc_make_model,
                ram=computer_info.ram,
                processor_name=computer_info.processor_name,
                os_name=computer_info.os_name,
            )

            logger.info(
                f"Successfully linked ticket {ticket.id} to computer {computer_info.hostname}"
            )
            return ticket_computer_info
        else:
            logger.warning(
                f"Could not link ticket {ticket.id} to any computer information"
            )
            return None

    except Exception as e:
        logger.error(f"Error linking ticket {ticket.id} to computer info: {str(e)}")
        return None


def get_client_ip(request):
    """
    Get the client IP address from the request.

    Args:
        request: The HTTP request object

    Returns:
        str or None: The client IP address
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")

    return ip


def search_computers(search_term):
    """
    Search for computers by various criteria.

    Args:
        search_term (str): The search term

    Returns:
        QuerySet: Computer information matching the search
    """
    try:
        return ComputerInfo.objects.using("computers").filter(
            models.Q(hostname__icontains=search_term)
            | models.Q(current_user__icontains=search_term)
            | models.Q(serial_number__icontains=search_term)
            | models.Q(derby_plant_loc__icontains=search_term)
        )[
            :10
        ]  # Limit to 10 results

    except Exception as e:
        logger.error(f"Error searching computers: {str(e)}")
        return ComputerInfo.objects.none()
