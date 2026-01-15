from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Service

User = get_user_model()


class ServiceSerializer(serializers.ModelSerializer):
    collaborators = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.filter(role='professional'),
        required=False
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=__import__('categories.models', fromlist=['Category']).Category.objects.all(),
        required=False,
        allow_null=True
    )
    actions = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Service
        fields = [
            'id',
            'name',
            'reference',
            'category',
            'duration',
            'rate',
            'price',
            'show_online',
            'collaborators',
            'actions',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_actions(self, obj):
        return {}

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price must be non-negative.")
        return value

    def validate_rate(self, value):
        if value < 0:
            raise serializers.ValidationError("Rate must be non-negative.")
        return value

