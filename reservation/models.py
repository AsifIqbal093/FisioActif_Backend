from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from user.models import Customer
from classes.models import Class

User = get_user_model()

TIME_SLOTS = [
    ('00:00 - 01:00', '00:00 - 01:00'), ('01:00 - 02:00', '01:00 - 02:00'),
    ('02:00 - 03:00', '02:00 - 03:00'), ('03:00 - 04:00', '03:00 - 04:00'),
    ('04:00 - 05:00', '04:00 - 05:00'), ('05:00 - 06:00', '05:00 - 06:00'),
    ('06:00 - 07:00', '06:00 - 07:00'), ('07:00 - 08:00', '07:00 - 08:00'),
    ('08:00 - 09:00', '08:00 - 09:00'), ('09:00 - 10:00', '09:00 - 10:00'),
    ('10:00 - 11:00', '10:00 - 11:00'), ('11:00 - 12:00', '11:00 - 12:00'),
    ('12:00 - 13:00', '12:00 - 13:00'), ('13:00 - 14:00', '13:00 - 14:00'),
    ('14:00 - 15:00', '14:00 - 15:00'), ('15:00 - 16:00', '15:00 - 16:00'),
    ('16:00 - 17:00', '16:00 - 17:00'), ('17:00 - 18:00', '17:00 - 18:00'),
    ('18:00 - 19:00', '18:00 - 19:00'), ('19:00 - 20:00', '19:00 - 20:00'),
    ('20:00 - 21:00', '20:00 - 21:00'), ('21:00 - 22:00', '21:00 - 22:00'),
    ('22:00 - 23:00', '22:00 - 23:00'), ('23:00 - 24:00', '23:00 - 24:00')
]

class Booking(models.Model):
    # Fields shown in the provided UI screenshot
    professional = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='professional_bookings',
        default=None
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        related_name='customer_bookings'
    )
    class_id = models.ForeignKey(
        Class,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )
    coupon = models.CharField(max_length=100, blank=True, null=True)
    services = models.CharField(max_length=255, blank=True, null=True)
    room_equipment = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=100, blank=True, null=True)
    data = models.DateField(auto_now_add=False, blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    # Additional fields shown in the later screenshot
    internal_notes = models.TextField(blank=True, null=True)
    treatment_record_marking = models.BooleanField(default=False)
    treatment_record_customer_file = models.FileField(blank=True, null=True, upload_to='treatment_files/')
    STATE_CHOICES = [
        ('confirmed', 'CONFIRMED'),
        ('it_arrived', 'IT ARRIVED'),
        ('paid', 'PAID'),
        ('missing', 'MISSING'),
        ('cancel', 'CANCEL'),
    ]
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default='confirmed')
    internal_notes = models.TextField(blank=True, null=True)
    treatment_record_marking = models.BooleanField(default=False)
    treatment_record_customer_file = models.FileField(upload_to='treatment_customer_files/', blank=True, null=True)
    STATE_CHOICES = [
        ('confirmed', 'CONFIRMED'),
        ('it_arrived', 'IT ARRIVED'),
        ('paid', 'PAID'),
        ('missing', 'MISSING'),
        ('cancel', 'CANCEL'),
    ]
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default='confirmed')
