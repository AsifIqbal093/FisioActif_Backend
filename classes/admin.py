from django.contrib import admin
from .models import Class


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'duration', 'capacity', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name',)
