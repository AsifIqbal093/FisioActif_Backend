from django.db.models.signals import post_save
from django.dispatch import receiver
from user.models import User
from user.models import Client

@receiver(post_save, sender=User)
def professional_created(sender, instance, created, **kwargs):
    if created and instance.role == 'professional':
        # Place analytics update logic here
        pass

@receiver(post_save, sender=Client)
def client_created(sender, instance, created, **kwargs):
    if created:
        # Place analytics update logic here
        pass
