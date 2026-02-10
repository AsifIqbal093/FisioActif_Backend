from django.db import models
from django.conf import settings


class Class(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    duration = models.PositiveIntegerField(help_text='Duration in minutes')
    capacity = models.PositiveIntegerField(default=1)
    professional = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='classes',
        limit_choices_to={'role': 'professional'},
        null=True,
        blank=True
    )
    clients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='enrolled_classes',
        limit_choices_to={'role': 'client'}
    )
    status = models.BooleanField(default=True)  # True = active
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
