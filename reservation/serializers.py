from rest_framework import serializers
from .models import Booking
from django.utils import timezone
from user.models import User
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal
from classes.models import Class


class UserDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'color_scheme']


class CustomerDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email']


class BookingSerializer(serializers.ModelSerializer):
    # Map to the simplified model fields: professional (FK) and customer (FK)
    professional = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role__in=['professional', 'teacher']),
        write_only=True
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='client'),
        write_only=True,
        allow_null=True,
        required=False,
    )
    class_id = serializers.PrimaryKeyRelatedField(
        queryset=Class.objects.all(),  # Assuming Class is the model for the classes app
        write_only=True,
        allow_null=True,
        required=False,
    )
    professional_details = UserDataSerializer(source='professional', read_only=True)
    customer_details = CustomerDataSerializer(source='customer', read_only=True)
    class_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'title', 'professional', 'professional_details', 'customer', 'customer_details', 
            'class_id', 'class_details', 'coupon', 'services', 'room_equipment', 'data', 'start_time', 
            'end_time', 'internal_notes', 'treatment_record_marking', 'treatment_record_customer_file', 'state'
        ]
        extra_kwargs = {
            'status': {'required': False},
            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
            'total_clients': {'read_only': True},
            'approve': {'required': False}
        }

    def get_class_details(self, obj):
        """Return class details if class_id is set."""
        if obj.class_id:
            return {
                "id": obj.class_id.id,
                "name": obj.class_id.name,  # Assuming name is a field in the Class model
            }
        return None
    
    def validate(self, data):
        # Validate date is not in the past
        if data.get('class_id') and data.get('customer'):
            raise serializers.ValidationError("You can only provide either 'class_id' or 'customer', not both.")
        if not data.get('class_id') and not data.get('customer'):
            raise serializers.ValidationError("You must provide either 'class_id' or 'customer'.")
        
        if 'data' in data and data['data'] < timezone.now().date():
            raise serializers.ValidationError("Reservation date must be in the future")

        # Validate subscription for professionals (not for admins)
        # professional = data.get('professional') or (self.instance.professional if self.instance else None)
        # if professional and getattr(professional, 'role', None) in ['professional', 'teacher']:
        #     if getattr(professional, 'remaining_hours', 0) < 1:
        #         raise serializers.ValidationError(
        #             "Insufficient hours. Please subscribe to a pack to book classes."
        #         )

        return data

    def validate_status(self, value):
        if 'status' in self.initial_data and self.context['request'].user.role != 'admin':
            raise serializers.ValidationError("Only admin can change reservation status")
        return value

    def create(self, validated_data):
        booking = Booking.objects.create(**validated_data)
        # Deduct 1 hour from professional's remaining_hours (not for admin)
        if getattr(booking.professional, 'role', None) in ['professional', 'customer']:
            # booking.professional.remaining_hours = booking.professional.remaining_hours - Decimal('1')
            booking.professional.save()

        self.send_booking_email(booking, 'created')
        return booking

    def update(self, instance, validated_data):
        # Ensure class_id and customer are mutually exclusive
        if 'class_id' in validated_data and validated_data['class_id'] is not None:
            validated_data['customer'] = None
        elif 'customer' in validated_data and validated_data['customer'] is not None:
            validated_data['class_id'] = None

        for attr in ['title', 'professional', 'customer', 'class_id', 'coupon', 'services', 'room_equipment',
                     'data', 'start_time', 'end_time', 'internal_notes', 'treatment_record_marking',
                     'treatment_record_customer_file', 'state']:
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])
        instance.save()
        self.send_booking_email(instance, 'updated')
        return instance
    
    def send_booking_email(self, booking, action):
        """Send email notification to client and professional."""
        subject = f"Reservation {action.capitalize()} Notification"
        time_text = ''
        if booking.start_time and booking.end_time:
            time_text = f" from {booking.start_time} to {booking.end_time}"
        message = f"Your reservation for {booking.data}{time_text} has been {action}."

        # Send email to the professional
        if getattr(booking, 'professional', None):
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [booking.professional.email],
                fail_silently=False,
            )

        # Send email to the customer (if any)
        if getattr(booking, 'customer', None):
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [booking.customer.email],
                fail_silently=False,
            )
