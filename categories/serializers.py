from rest_framework import serializers
from .models import Category


class CategorySerializer(serializers.ModelSerializer):
	services = serializers.SerializerMethodField()

	class Meta:
		model = Category
		fields = ['id', 'name', 'status', 'services', 'created_at', 'updated_at']

	def get_services(self, obj):
		from services.serializers import ServiceSerializer
		services = obj.services.all()
		return ServiceSerializer(services, many=True).data
