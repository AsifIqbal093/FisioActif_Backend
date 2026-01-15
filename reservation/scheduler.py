from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def send_booking_reminders():
    """
    Send reminders for reservations scheduled tomorrow.
    This will be triggered externally via a cron job.
    """
    from .models import Booking  

    tomorrow = timezone.now().date() + timedelta(days=1)
    upcoming_reservations = Booking.objects.filter(
        data=tomorrow,
        status='confirmed'
    ).select_related('professional').select_related('customer')

    if not upcoming_reservations.exists():
        logger.info("No upcoming reservations found for tomorrow.")
        return

    for booking in upcoming_reservations:
        try:
            # Send to professional
            if booking.professional:
                send_reminder_email(
                    recipient_email=booking.professional.email,
                    recipient_name=booking.professional.full_name,
                    booking=booking
                )

            # Send to the customer (if any)
            if booking.customer:
                send_reminder_email(
                    recipient_email=booking.customer.email,
                    recipient_name=booking.customer.full_name,
                    booking=booking
                )

        except Exception as e:
            logger.error(f"Error sending reminder for reservation {booking.id}: {e}")

    logger.info(f"Reminders sent for {upcoming_reservations.count()} reservation(s) scheduled for {tomorrow}.")


def send_reminder_email(recipient_email, recipient_name, booking):
    """Send individual reminder email."""
    subject = f"Reminder: Reservation Tomorrow - {booking.data}"
    
    time_text = ''
    if booking.start_time and booking.end_time:
        time_text = f" from {booking.start_time} to {booking.end_time}"

    message = f"""Hello {recipient_name},

This is a reminder that you have a reservation scheduled for TOMORROW:

Date: {booking.data}
Time: {time_text or 'N/A'}
Professional: {booking.professional.full_name if booking.professional else 'N/A'}
Title: {booking.title or 'N/A'}
Notes: {booking.internal_notes or 'No additional notes'}

Please make sure to attend on time.

Best regards,
Reservation System
"""

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient_email],
        fail_silently=False,
    )
    logger.info(f"Reminder email sent to {recipient_email} for reservation {booking.id}.")
