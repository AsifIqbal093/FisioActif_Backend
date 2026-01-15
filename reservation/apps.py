from django.apps import AppConfig
import os

class ReservationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # Use the label 'bookings' so existing migrations and DB tables remain associated.
    name = 'reservation'
    label = 'bookings'