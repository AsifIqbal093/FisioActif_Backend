from django.contrib import admin
from .models import Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'capacity', 'location', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'location')
