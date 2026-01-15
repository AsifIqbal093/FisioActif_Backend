from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Booking, TIME_SLOTS
from .serializers import BookingSerializer

from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone

class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = {
        'data': ['exact'],
    }
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # During schema generation (swagger_fake_view) self.request may be a dummy
        # or have an AnonymousUser without the expected attributes. Guard against that.
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()

        user = getattr(self.request, 'user', None)
        if user is None or getattr(user, 'is_authenticated', False) is False:
            return Booking.objects.none()
        now = timezone.now().date()

        base_qs = Booking.objects.annotate(
            is_past=Case(
                When(data__lt=now, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by('is_past', 'data', 'start_time')

        if user.role == 'admin':
            return base_qs
        if user.role in ['professional', 'teacher']:
            return base_qs.filter(professional=user)
        return Booking.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user

        # Professionals/teachers must have at least 1 remaining hour to book
        if getattr(user, 'role', None) in ['professional', 'teacher'] and user.remaining_hours < 1:
            return Response(
                {"error": "Insufficient hours. Please subscribe to a pack before booking."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Date to get available slots for (format: YYYY-MM-DD)',
            ),
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
    )
    @action(detail=False, methods=['get'])
    def available_slots(self, request):
        """Get all available slots for a specific date"""
        date = request.query_params.get('date')
        if not date:
            return Response(
                {"error": "Date parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # The Booking model now stores start_time/end_time rather than a time_slot string.
        # For backwards compatibility return the available TIME_SLOTS list unfiltered here.
        from .models import TIME_SLOTS

        available = [
            {'value': slot[0], 'display': slot[1]}
            for slot in TIME_SLOTS
        ]

        return Response(available)

    def perform_create(self, serializer):
        if not self.request.user.role == 'admin':
            serializer.save(professional=self.request.user)
        else:
            serializer.save()
    
    @action(detail=True, methods=['GET'])
    def approve(self, request, pk=None):
        """Admin-only endpoint to approve a booking"""
        return self._change_booking_status(pk, 'confirmed', request)

    
    @action(detail=True, methods=['GET'])
    def reject(self, request, pk=None):
        """Admin-only endpoint to reject a booking"""
        return self._change_booking_status(pk, 'cancelled', request)

    
    def _change_booking_status(self, pk, new_status, request):
        booking = self.get_object()

        # Admin can change status for any booking
        if request.user.role == 'admin':
            pass
        # Professional (professional/teacher) can change only their own bookings
        elif request.user.role in ['professional', 'teacher']:
            if booking.professional != request.user:
                return Response(
                    {"detail": "You can only change status for your own bookings"},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(
                {"detail": "You are not allowed to change booking status"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update status
        booking.status = new_status
        booking.save()

        serializer = self.get_serializer(booking)
        self._send_status_notification(booking, new_status)

        return Response(serializer.data, status=status.HTTP_200_OK)


    
    def _send_status_notification(self, booking, status):
        """Example notification method (implement with your email service)"""
        subject = f"Booking {status}"
        time_text = ''
        if booking.start_time and booking.end_time:
            time_text = f" from {booking.start_time} to {booking.end_time}"
        message = f"Your booking for {booking.data}{time_text} has been {status}"
        print(f"Notification sent: {subject} - {message}")

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='month',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by month (format: "Month Year" e.g. "June 2025")',
            ),
            OpenApiParameter(
                name='week_start',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Start date for week filter (format: YYYY-MM-DD)',
            ),
            OpenApiParameter(
                name='week_end',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='End date for week filter (format: YYYY-MM-DD)',
            ),
            OpenApiParameter(
                name='day',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filter by specific day (format: YYYY-MM-DD)',
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by booking status',
                enum=['pending', 'confirmed', 'cancelled'],
            ),
        ],
    )
    @action(detail=False, methods=['get'])
    def filter_bookings(self, request):
        """
        Filter bookings by day, week, or month
        Parameters (all optional):
        - month: "June 2025" (format: "%B %Y")
        - week_start: "2025-06-01" (format: "%Y-%m-%d")
        - week_end: "2025-06-07" (format: "%Y-%m-%d")
        - day: "2025-06-15" (format: "%Y-%m-%d")
        """
        queryset = self.get_queryset()
        
        # Month filter
        month_str = request.query_params.get('month')
        if month_str:
            try:
                month_date = datetime.strptime(month_str, "%B %Y").date()
                start_date = month_date.replace(day=1)
                end_date = start_date + relativedelta(months=1) - timedelta(days=1)
                queryset = queryset.filter(
                    data__gte=start_date,
                    data__lte=end_date
                )
            except ValueError:
                return Response(
                    {"error": "Invalid month format. Use 'Month Year' (e.g. 'June 2025')"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Week filter
        week_start = request.query_params.get('week_start')
        week_end = request.query_params.get('week_end')
        if week_start and week_end:
            try:
                start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
                end_date = datetime.strptime(week_end, "%Y-%m-%d").date()
                queryset = queryset.filter(
                    data__gte=start_date,
                    data__lte=end_date
                )
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use 'YYYY-MM-DD'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        day_str = request.query_params.get('day')
        if day_str:
            try:
                day_date = datetime.strptime(day_str, "%Y-%m-%d").date()
                queryset = queryset.filter(data=day_date)
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use 'YYYY-MM-DD'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        status = request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status.lower())
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
