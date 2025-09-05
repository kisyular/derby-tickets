"""
Email queue to prevent concurrent connection limits with Outlook/Office365.
Sends emails sequentially with small delays to avoid rate limiting.
"""

import threading
import time
import queue
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


class EmailQueue:
    """Thread-safe email queue with rate limiting."""

    def __init__(self, delay_between_emails=0.5):
        self.queue = queue.Queue()
        self.delay_between_emails = delay_between_emails
        self.worker_thread = None
        self.running = False
        self._lock = threading.Lock()

    def start_worker(self):
        """Start the email worker thread."""
        with self._lock:
            if not self.running:
                self.running = True
                self.worker_thread = threading.Thread(target=self._worker)
                self.worker_thread.daemon = True
                self.worker_thread.start()
                logger.info("Email queue worker started")

    def stop_worker(self):
        """Stop the email worker thread."""
        with self._lock:
            self.running = False
            if self.worker_thread:
                self.worker_thread.join(timeout=5)
                logger.info("Email queue worker stopped")

    def add_email(self, email_function: Callable, *args, **kwargs):
        """Add an email to the queue."""
        self.queue.put((email_function, args, kwargs))
        self.start_worker()  # Ensure worker is running
        logger.info(f"Email queued: {email_function.__name__}")

    def _worker(self):
        """Worker thread that processes emails sequentially."""
        while self.running:
            try:
                # Get email from queue with timeout
                email_function, args, kwargs = self.queue.get(timeout=1)

                # Send email
                try:
                    email_function(*args, **kwargs)
                    logger.info(f"Email sent successfully: {email_function.__name__}")
                except Exception as e:
                    logger.error(
                        f"Failed to send email {email_function.__name__}: {str(e)}"
                    )

                # Mark task as done
                self.queue.task_done()

                # Add delay to prevent rate limiting
                if self.delay_between_emails > 0:
                    time.sleep(self.delay_between_emails)

            except queue.Empty:
                # No emails in queue, continue checking
                continue
            except Exception as e:
                logger.error(f"Email worker error: {str(e)}")


# Global email queue instance
email_queue = EmailQueue(delay_between_emails=1.0)  # 1 second delay between emails


def send_email_queued(email_function: Callable, *args, **kwargs):
    """
    Send email via queue to prevent concurrent connection limits.

    Args:
        email_function: The email function to call
        *args: Arguments to pass to the email function
        **kwargs: Keyword arguments to pass to the email function
    """
    email_queue.add_email(email_function, *args, **kwargs)
