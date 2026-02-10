from django.db.models.signals import post_save
from django.dispatch import receiver
from user.models import User

@receiver(post_save, sender=User)
def professional_created(sender, instance, created, **kwargs):
    if created and instance.role == 'professional':
        # Place analytics update logic here
        pass

# Unified client creation signal using User model
@receiver(post_save, sender=User)
def client_created(sender, instance, created, **kwargs):
    if created and instance.role == 'client':
        # Place analytics update logic here
        pass
