# videos/serializers.py
from rest_framework import serializers
from .models import Video

class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['id', 'uploaded_by', 'video_file', 'title', 'description', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']

    def create(self, validated_data):
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)
