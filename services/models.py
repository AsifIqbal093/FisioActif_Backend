from django.db import models
from django.conf import settings


class Service(models.Model):
    DURATION_CHOICES = [
        (15, '15 min'),
        (30, '30 min'),
        (45, '45 min'),
        (60, '60 min'),
        (90, '90 min'),
    ]

    name = models.CharField(max_length=200)
    reference = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(
        'categories.Category',
        on_delete=models.CASCADE,
        related_name='services',
        null=True,
        blank=True
    )
    duration = models.PositiveIntegerField(choices=DURATION_CHOICES)
    rate = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    show_online = models.BooleanField(default=True)
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='services_collaborated',
        limit_choices_to={'role': 'professional'},
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
