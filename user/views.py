from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import generics, viewsets, status, permissions
from rest_framework.exceptions import NotFound

from user.models import User
from .permissions import IsAdmin
from user.serializers import UserSerializer, UserAdminSerializer, TimeslotSerializer, UserClientSerializer
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

    serializer_class = UserClientSerializer
    queryset = User.objects.filter(role='client')

    def create(self, request, *args, **kwargs):
        # Only allow client registration, not professional
        if 'role' in request.data and request.data['role'] == 'professional':
            return Response({'detail': 'Professional registration is not allowed.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)


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
    def get_permissions(self):
        user = self.request.user
        # Allow admin always
        if user.is_authenticated and user.role == 'admin':
            return [IsAdmin()]
        # Allow client for list with role=professional or for timeslots action
        if self.action == 'list':
            role_param = self.request.query_params.get('role')
            if user.is_authenticated and user.role == 'client' and role_param == 'professional':
                return [permissions.IsAuthenticated()]
        if self.action == 'timeslots':
            if user.is_authenticated and user.role == 'client':
                return [permissions.IsAuthenticated()]
        return [IsAdmin()]

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
    def destroy(self, request, *args, **kwargs):
        user = self.request.user
        instance = self.get_object()
        # Admin can delete any client; client can only delete their own record
        if hasattr(user, 'role') and user.role == 'admin':
            return super().destroy(request, *args, **kwargs)
        if hasattr(user, 'email') and not hasattr(user, 'role') and instance.email == user.email:
            return super().destroy(request, *args, **kwargs)
        return Response({'detail': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)


    queryset = User.objects.filter(role='client')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return UserClientSerializer

    def get_queryset(self):
        user = self.request.user
        # Admin can see all clients
        if hasattr(user, 'role') and user.role == 'admin':
            return User.objects.filter(role='client').order_by('-id')
        # Client can only see their own record
        if hasattr(user, 'role') and user.role == 'client':
            return User.objects.filter(id=user.id)
        return User.objects.none()
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='professional_id',
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
                description='ID of the professional to fetch assigned clients for'
            )
        ],
        responses=UserClientSerializer(many=True),
        description="Get clients assigned to a specific professional by ID"
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

        clients = User.objects.filter(professionals=professional, role='client')
        serializer = self.get_serializer(clients, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # Only admin can create clients via this endpoint
        user = self.request.user
        if not (hasattr(user, 'role') and user.role == 'admin'):
            return Response({'detail': 'Only admin can create clients.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        user = self.request.user
        instance = self.get_object()
        # Admin can update any client; client can only update their own info
        if hasattr(user, 'role') and user.role == 'admin':
            return super().update(request, *args, **kwargs)
        if hasattr(user, 'email') and not hasattr(user, 'role') and instance.email == user.email:
            return super().update(request, *args, **kwargs)
        return Response({'detail': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)

    def destroy(self, request, *args, **kwargs):
        user = self.request.user
        instance = self.get_object()
        # Admin can delete any client; client can only delete their own record
        if hasattr(user, 'role') and user.role == 'admin':
            return super().destroy(request, *args, **kwargs)
        if hasattr(user, 'email') and not hasattr(user, 'role') and instance.email == user.email:
            return super().destroy(request, *args, **kwargs)
        return Response({'detail': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)


    # Removed by-professional endpoint: professionals no longer have access to clients
    

# Unified login view for both User (admin) and Customer (client)
from user.serializers import AuthTokenSerializer

class CustomTokenObtainView(APIView):
    """Login view for both admin and client (User model)"""
    serializer_class = AuthTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        from django.contrib.auth import authenticate
        user = authenticate(request=request, username=email, password=password)
        if user is not None:
            # Only allow admin and client login, not professional
            if hasattr(user, 'role') and user.role == 'professional':
                return Response({'detail': 'Professional login is not allowed.'}, status=status.HTTP_403_FORBIDDEN)
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user_id': user.pk,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'type': user.role
            })
        return Response({'detail': 'Unable to authenticate with provided credentials.'}, status=400)
