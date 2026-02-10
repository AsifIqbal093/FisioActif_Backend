from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Class
from user.models import User
from user.serializers import UserClientSerializer

User = get_user_model()


class ClassSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()
    professional = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='professional'),
        many=True,
        required=False,
        allow_null=True
    )
    # For POST: accept list of client IDs
    client_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.filter(role='client'),
        write_only=True,
        required=False,
        source='clients'
    )
    # For GET: return full client details
    clients = UserClientSerializer(many=True, read_only=True)

    class Meta:
        model = Class
        fields = ['id', 'name', 'description', 'duration', 'capacity', 'professional', 'client_ids', 'clients', 'status', 'created_at', 'updated_at', 'actions']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_actions(self, obj):
        # Provide frontend with minimal action metadata (frontend will render buttons)
        return {
            'edit': True,
            'toggle_status': True,
            'status_label': 'Active' if obj.status else 'Inactive'
        }

    def validate_duration(self, value):
        if value <= 0:
            raise serializers.ValidationError('Duration must be a positive integer (minutes).')
        return value

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Capacity must be a positive integer.')
        return value

    def validate(self, data):
        """Validate that the number of clients doesn't exceed capacity"""
        clients = data.get('clients', [])
        capacity = data.get('capacity')
        
        # If updating, use existing capacity if not provided
        if self.instance and capacity is None:
            capacity = self.instance.capacity
        
        # Check if clients list exceeds capacity
        if capacity and len(clients) > capacity:
            raise serializers.ValidationError({
                'client_ids': f'Cannot add {len(clients)} clients. Class capacity is {capacity}.'
            })
        
        return data
