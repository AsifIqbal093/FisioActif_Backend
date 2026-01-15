from django.core.management.base import BaseCommand
from reservation.scheduler import send_booking_reminders

class Command(BaseCommand):
    help = 'Send reminder emails for tomorrow’s reservations.'

    def handle(self, *args, **kwargs):
        send_booking_reminders()
        self.stdout.write(self.style.SUCCESS("Reservation reminders sent successfully."))
