from django.contrib import admin
from .models import Pack, SubscriptionHistory, Order

@admin.register(Pack)
class PackAdmin(admin.ModelAdmin):
    list_display = ['title', 'price', 'total_hours', 'active', 'created_at']
    list_filter = ['active']
    search_fields = ['title', 'description']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'pack', 'amount', 'payment_method', 'payment_status', 'created_at', 'paid_at']
    list_filter = ['payment_status', 'payment_method', 'created_at']
    search_fields = ['order_id', 'user__email', 'user__full_name', 'mb_reference', 'request_id']
    readonly_fields = ['order_id', 'created_at', 'request_id']
    fieldsets = (
        ('Order Info', {
            'fields': ('order_id', 'user', 'pack', 'amount', 'payment_method', 'payment_status')
        }),
        ('MultiBanco Details', {
            'fields': ('mb_key', 'mb_entity', 'mb_reference', 'expiry_date')
        }),
        ('IfThenPay Tracking', {
            'fields': ('request_id',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'paid_at')
        }),
    )


@admin.register(SubscriptionHistory)
class SubscriptionHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'pack', 'hours_added', 'order', 'subscribed_at']
    list_filter = ['subscribed_at', 'pack']
    search_fields = ['user__email', 'user__full_name', 'pack__title']
    readonly_fields = ['subscribed_at']
