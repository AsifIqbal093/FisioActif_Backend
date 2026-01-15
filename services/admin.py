from django.contrib import admin
from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'reference', 'duration', 'price', 'show_online')
    list_filter = ('show_online',)
    search_fields = ('name', 'reference')
