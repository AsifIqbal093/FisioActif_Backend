from services.models import Service
from .models import User
from django.contrib.auth import (
    get_user_model,
    authenticate,
)
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User
from django.contrib.auth import (
    get_user_model,
    authenticate,
)
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


def get_services_by_category_for_user(user):
    if user.role != 'professional':
        return {}
    from collections import defaultdict
    result = defaultdict(list)
    services = Service.objects.filter(collaborators=user)
    for service in services:
        cat_id = service.category.id if service.category else None
        if cat_id:
            result[str(cat_id)].append(service.id)
    return result

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['email'] = user.email
        token['full_name'] = user.full_name
        token['role'] = user.role

        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['email'] = self.user.email
        data['full_name'] = self.user.full_name
        data['role'] = self.user.role
        return data



# Unified serializer for client registration and update
class UserClientSerializer(serializers.ModelSerializer):
    professionals = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='professional'),
        many=True,
        required=False
    )
    password = serializers.CharField(write_only=True, min_length=5, required=True)

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'password', 'contact_number', 'joined_at', 'professionals']
        read_only_fields = ['id', 'joined_at']

    def create(self, validated_data):
        password = validated_data.pop('password')
        professionals = validated_data.pop('professionals', None)
        user = User(**validated_data)
        user.set_password(password)
        user.role = 'client'
        user.save()
        if professionals is not None:
            user.professionals.set(professionals)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        professionals = validated_data.pop('professionals', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if professionals is not None:
            instance.professionals.set(professionals)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def validate_email(self, value):
        if self.instance and self.instance.email == value:
            return value
        if User.objects.filter(email=value, role='client').exists():
            raise serializers.ValidationError("A client with this email already exists.")
        return value

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class TimeslotSerializer(serializers.ModelSerializer):
    """Serializer for professional timeslot availability"""
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'role',
            'monday_enabled', 'monday_start', 'monday_break_from', 'monday_break_to', 'monday_end',
            'tuesday_enabled', 'tuesday_start', 'tuesday_break_from', 'tuesday_break_to', 'tuesday_end',
            'wednesday_enabled', 'wednesday_start', 'wednesday_break_from', 'wednesday_break_to', 'wednesday_end',
            'thursday_enabled', 'thursday_start', 'thursday_break_from', 'thursday_break_to', 'thursday_end',
            'friday_enabled', 'friday_start', 'friday_break_from', 'friday_break_to', 'friday_end',
            'saturday_enabled', 'saturday_start', 'saturday_break_from', 'saturday_break_to', 'saturday_end',
            'sunday_enabled', 'sunday_start', 'sunday_break_from', 'sunday_break_to', 'sunday_end',
        ]
        read_only_fields = ['id', 'full_name', 'email', 'role']


class UserSerializer(serializers.ModelSerializer):
    category_services = serializers.DictField(child=serializers.ListField(child=serializers.IntegerField()), write_only=True, required=False, help_text="{category_id: [service_id, ...], ...}")
    services_by_category = serializers.SerializerMethodField(read_only=True)
    def get_services_by_category(self, obj):
        return get_services_by_category_for_user(obj)
    password = serializers.CharField(write_only=True, min_length=5, required=False)

    class Meta:
        model = User
        fields = [
            # core
            'id',
            'email',
            'password',
            'full_name',
            'role',
            'is_active',
            'bio',
            'photo',

            # contact & address
            'contact_number',
            'personal_mobile',
            'show_mobile_in_app',
            'street',
            'city',
            'state',
            'country',
            'zipcode',

            # collaborator / professional
            'collaborator_code',
            'specialty',
            'gender_senhora',
            'gender_homem',
            'domicilio',
            'color_scheme',

            # commissions
            'commission_executing_percent',
            'commission_executing_euro',
            'commission_responsible_percent',
            'commission_responsible_euro',

            # links
            'zappy_page',

            # availability
            'monday_enabled', 'monday_start', 'monday_break_from', 'monday_break_to', 'monday_end',
            'tuesday_enabled', 'tuesday_start', 'tuesday_break_from', 'tuesday_break_to', 'tuesday_end',
            'wednesday_enabled', 'wednesday_start', 'wednesday_break_from', 'wednesday_break_to', 'wednesday_end',
            'thursday_enabled', 'thursday_start', 'thursday_break_from', 'thursday_break_to', 'thursday_end',
            'friday_enabled', 'friday_start', 'friday_break_from', 'friday_break_to', 'friday_end',
            'saturday_enabled', 'saturday_start', 'saturday_break_from', 'saturday_break_to', 'saturday_end',
            'sunday_enabled', 'sunday_start', 'sunday_break_from', 'sunday_break_to', 'sunday_end',

            # meta
            'date_joined',

            # new field for registration
            'category_services',
            # new field for GET
            'services_by_category',
        ]
        read_only_fields = ['date_joined']

    def create(self, validated_data):
        category_services = validated_data.pop('category_services', None)
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        # Assign services if provided and user is professional
        if category_services and user.role == 'professional':
            for service_ids in category_services.values():
                for service_id in service_ids:
                    try:
                        service = Service.objects.get(id=service_id)
                        service.collaborators.add(user)
                    except Service.DoesNotExist:
                        continue
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


    # def get_subscribed_pack_details(self, obj):
    #     # Get all subscription history for this user
    #     from subscriptions.models import SubscriptionHistory
    #     subscriptions = SubscriptionHistory.objects.filter(user=obj).order_by('-subscribed_at')
        
    #     if subscriptions.exists():
    #         return [
    #             {
    #                 'id': sub.pack.id,
    #                 'title': sub.pack.title,
    #                 'total_hours': sub.hours_added,
    #                 'subscription_date': sub.subscribed_at,
    #             }
    #             for sub in subscriptions
    #         ]
    #     return []

    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save()

        return user


class AuthTokenSerializer(serializers.Serializer):
    """Serializer for the user auth token."""
    email = serializers.EmailField()
    password = serializers.CharField(
        style={'input_type': 'password'},
        trim_whitespace=False,
    )

    def validate(self, attrs):
        """Validate and authenticate the user."""
        email = attrs.get('email')
        password = attrs.get('password')
        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password,
        )
        if not user:
            msg = 'Unable to authenticate with provided credentials.'
            raise serializers.ValidationError(msg, code='authorization')

        attrs['user'] = user
        return attrs


class FlexiblePKRelatedField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        try:
            data = int(data)
        except (ValueError, TypeError):
            self.fail('incorrect_type', data_type=type(data).__name__)
        return super().to_internal_value(data)


class UserAdminSerializer(serializers.ModelSerializer):
    services_by_category = serializers.SerializerMethodField(read_only=True)
    def get_services_by_category(self, obj):
        return get_services_by_category_for_user(obj)
    
    category_services = serializers.DictField(child=serializers.ListField(child=serializers.IntegerField()), write_only=True, required=False, help_text="{category_id: [service_id, ...], ...}")
    # Read clients as nested data
    customers = UserClientSerializer(source='clients', many=True, read_only=True)
    customer_ids = FlexiblePKRelatedField(
        queryset=User.objects.filter(role='client'),
        many=True,
        write_only=True,
        required=False
    )
    # subscribed_pack_details = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            # core
            'id', 'email', 'password', 'full_name', 'role', 'is_active', 'bio', 'photo', 'date_joined',

            # contact & address
            'contact_number', 'personal_mobile', 'show_mobile_in_app',
            'street', 'city', 'state', 'country', 'zipcode',

            # collaborator / professional
            'collaborator_code', 'specialty', 'gender_senhora', 'gender_homem', 'domicilio', 'color_scheme',

            # commissions
            'commission_executing_percent', 'commission_executing_euro',
            'commission_responsible_percent', 'commission_responsible_euro',

            # links
            'zappy_page',

            # availability
            'monday_enabled', 'monday_start', 'monday_break_from', 'monday_break_to', 'monday_end',
            'tuesday_enabled', 'tuesday_start', 'tuesday_break_from', 'tuesday_break_to', 'tuesday_end',
            'wednesday_enabled', 'wednesday_start', 'wednesday_break_from', 'wednesday_break_to', 'wednesday_end',
            'thursday_enabled', 'thursday_start', 'thursday_break_from', 'thursday_break_to', 'thursday_end',
            'friday_enabled', 'friday_start', 'friday_break_from', 'friday_break_to', 'friday_end',
            'saturday_enabled', 'saturday_start', 'saturday_break_from', 'saturday_break_to', 'saturday_end',
            'sunday_enabled', 'sunday_start', 'sunday_break_from', 'sunday_break_to', 'sunday_end',

            # relations
            'customers', 'customer_ids',

            # new field for registration
            'category_services',
            # new field for GET
            'services_by_category',
        ]
        read_only_fields = ['id', 'date_joined']
        extra_kwargs = {
            'password': {'write_only': True, 'min_length': 5, 'required': False},
            'is_active': {'read_only': True},
            'email': {'required': False},
        }

    def validate_email(self, value):
        """Allow the same email when updating the user"""
        if self.instance and self.instance.email == value:
            return value
        
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("user with this email already exists.")
        
        return value

    # def get_subscribed_pack_details(self, obj):
    #     # Get all subscription history for this user
    #     from subscriptions.models import SubscriptionHistory
    #     subscriptions = SubscriptionHistory.objects.filter(user=obj).order_by('-subscribed_at')
        
    #     if subscriptions.exists():
    #         return [
    #             {
    #                 'id': sub.pack.id,
    #                 'title': sub.pack.title,
    #                 'total_hours': sub.hours_added,
    #                 'subscription_date': sub.subscribed_at,
    #             }
    #             for sub in subscriptions
    #         ]
    #     return []

    def create(self, validated_data):
        customer_ids = validated_data.pop('customer_ids', [])
        category_services = validated_data.pop('category_services', None)
        user = get_user_model().objects.create_user(**validated_data)

        if user.role == 'professional':
            for customer in customer_ids:
                customer.professionals.add(user)
            # Assign services if provided
            if category_services:
                for service_ids in category_services.values():
                    for service_id in service_ids:
                        try:
                            service = Service.objects.get(id=service_id)
                            service.collaborators.add(user)
                        except Service.DoesNotExist:
                            continue
        return user

    def update(self, instance, validated_data):
        customer_ids = validated_data.pop('customer_ids', None)
        category_services = validated_data.pop('category_services', None)
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save()

        if customer_ids is not None and user.role == 'professional':
            # Remove this professional from all clients
            for customer in user.clients.all():
                customer.professionals.remove(user)
            # Add this professional to selected clients
            for customer in customer_ids:
                customer.professionals.add(user)

        # Update services assignment
        if category_services is not None and user.role == 'professional':
            # Remove from all current services
            for service in Service.objects.filter(collaborators=user):
                service.collaborators.remove(user)
            # Add to new services
            for service_ids in category_services.values():
                for service_id in service_ids:
                    try:
                        service = Service.objects.get(id=service_id)
                        service.collaborators.add(user)
                    except Service.DoesNotExist:
                        continue

        return user
    

