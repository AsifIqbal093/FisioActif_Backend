from rest_framework import serializers
from .models import Room


class RoomSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity', 'location', 'status', 'created_at', 'updated_at', 'actions']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_actions(self, obj):
        return {
            'edit': True,
            'toggle_status': True,
            'status_label': 'Active' if obj.status else 'Inactive'
        }

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Capacity must be a positive integer.')
        return value
