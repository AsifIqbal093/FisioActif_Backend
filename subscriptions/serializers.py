from rest_framework import serializers
from .models import Pack, SubscriptionHistory, Order


class PackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pack
        fields = ["id", "title", "description", "image", "active", "price", "total_hours", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    pack_title = serializers.CharField(source='pack.title', read_only=True)
    
    class Meta:
        model = SubscriptionHistory
        fields = ["id", "pack", "pack_title", "hours_added", "subscribed_at"]
        read_only_fields = ["id", "subscribed_at"]


class OrderSerializer(serializers.ModelSerializer):
    pack_details = PackSerializer(source='pack', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'user', 'user_email', 'user_name', 'pack', 'pack_details',
            'amount', 'payment_method', 'payment_status', 'mb_key', 'mb_entity',
            'mb_reference', 'order_id', 'request_id', 'expiry_date',
            'created_at', 'paid_at'
        ]
        read_only_fields = [
            'id', 'user', 'mb_key', 'mb_entity', 'mb_reference', 'order_id',
            'request_id', 'expiry_date', 'created_at', 'paid_at', 'payment_status'
        ]
