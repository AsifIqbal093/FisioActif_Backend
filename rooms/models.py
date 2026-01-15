from django.db import models


class Room(models.Model):
    name = models.CharField(max_length=200, unique=True)
    capacity = models.PositiveIntegerField(default=1)
    location = models.CharField(max_length=255, blank=True)
    status = models.BooleanField(default=True)  # True = active
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
