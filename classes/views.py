from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.exceptions import NotFound
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .models import Class
from .serializers import ClassSerializer

User = get_user_model()


class ClassViewSet(viewsets.ModelViewSet):
    """CRUD and status toggle for classes."""
    queryset = Class.objects.all().order_by('-created_at')
    serializer_class = ClassSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        cls = self.get_object()
        cls.status = not cls.status
        cls.save()
        serializer = self.get_serializer(cls)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='professional_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=True,
                description='ID of the professional to fetch assigned classes for'
            )
        ],
        responses=ClassSerializer(many=True),
        description="Get classes assigned to a specific professional by ID"
    )
    @action(detail=False, methods=['get'], url_path='by-professional')
    def by_professional(self, request):
        professional_id = request.query_params.get('professional_id')

        if not professional_id:
            return Response({"detail": "professional_id is required."}, status=400)

        try:
            professional = User.objects.get(id=professional_id, role='professional')
        except User.DoesNotExist:
            raise NotFound("Professional not found.")

        classes = Class.objects.filter(professional=professional)
        serializer = self.get_serializer(classes, many=True)
        return Response(serializer.data)
