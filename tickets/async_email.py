"""
Simple async email utilities using email queue to prevent rate limiting.
Prevents Outlook/Office365 concurrent connection limits.
"""

import logging
from .email_queue import send_email_queued

logger = logging.getLogger(__name__)


def send_email_async(email_function, *args, **kwargs):
    """
    Send email asynchronously via queue to prevent rate limiting.

    Args:
        email_function: The email function to call
        *args: Arguments to pass to the email function
        **kwargs: Keyword arguments to pass to the email function
    """
    send_email_queued(email_function, *args, **kwargs)
    logger.info(f"Email queued for sending: {email_function.__name__}")
