from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import generics, viewsets, status, permissions
from rest_framework.exceptions import NotFound

from user.models import User, Customer
from .permissions import IsAdmin
from user.serializers import UserSerializer, UserAdminSerializer, CustomerSerializer, TimeslotSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes


class CustomTokenObtainView(ObtainAuthToken):
    """Custom login view that returns a simple auth token"""
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role
        })


class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer


from rest_framework.authentication import TokenAuthentication

class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]

    def get_object(self):
        return self.request.user

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        user.delete()
        return Response({"detail": "Your account has been deleted."}, status=status.HTTP_204_NO_CONTENT)


class UserAdminViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='role',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter users by role',
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        role = request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = self.queryset
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        return queryset.order_by('-date_joined')

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='user_id',
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY
            )
        ],
        responses={status.HTTP_200_OK: UserAdminSerializer}
    )
    @action(detail=False, methods=['get'])
    def approve(self, request):
        user_id = request.query_params.get('user_id')
        user = User.objects.get(id=user_id)
        user.is_active = True
        user.save()
        return Response(self.get_serializer(user).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='professional_id',
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='ID of the professional to get timeslots for'
            )
        ],
        responses={status.HTTP_200_OK: TimeslotSerializer},
        description="Get timeslot availability for a specific professional"
    )
    @action(detail=False, methods=['get'], url_path='timeslots')
    def timeslots(self, request):
        professional_id = request.query_params.get('professional_id')

        if not professional_id:
            return Response({"detail": "professional_id is required."}, status=400)

        try:
            professional = User.objects.get(id=professional_id, role='professional')
        except User.DoesNotExist:
            raise NotFound("Professional not found.")

        serializer = TimeslotSerializer(professional)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='user_id',
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY
            )
        ],
        responses={status.HTTP_200_OK: UserAdminSerializer}
    )
    @action(detail=False, methods=['get'])
    def cancel(self, request):
        user_id = request.query_params.get('user_id')
        user = User.objects.get(id=user_id)
        user.is_active = False
        user.save()
        return Response(self.get_serializer(user).data)
    

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'professional':
            return Customer.objects.filter(professionals=user).order_by('-id')
        if user.role == 'admin':
            return Customer.objects.all().order_by('-id')
        return Customer.objects.none()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='professional_id',
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
                description='ID of the professional to fetch assigned customers for'
            )
        ],
        responses=CustomerSerializer(many=True),
        description="Get customers assigned to a specific professional by ID"
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

        customers = Customer.objects.filter(professionals=professional)
        serializer = self.get_serializer(customers, many=True)
        return Response(serializer.data)
