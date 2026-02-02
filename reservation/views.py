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
from services.models import Service
from user.models import User
from .serializers import BookingSerializer

from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone


# Helper function to calculate available slots
def get_available_slots_for_professional(professional, date_obj, total_duration):
    """
    Returns a list of available start/end time pairs for a professional on a given date,
    considering working hours, breaks, and existing bookings. total_duration in minutes (sum of all services).
    """
    from datetime import datetime, timedelta, time
    import pytz

    # Map weekday to field prefix
    weekday = date_obj.weekday()  # Monday=0
    day_map = [
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
    ]
    day_prefix = day_map[weekday]

    enabled = getattr(professional, f"{day_prefix}_enabled", False)
    start = getattr(professional, f"{day_prefix}_start", None)
    break_from = getattr(professional, f"{day_prefix}_break_from", None)
    break_to = getattr(professional, f"{day_prefix}_break_to", None)
    end = getattr(professional, f"{day_prefix}_end", None)

    if not enabled or not start or not end:
        return []

    # Convert times to datetime for calculations
    tz = pytz.UTC
    dt_start = datetime.combine(date_obj, start).replace(tzinfo=tz)
    dt_end = datetime.combine(date_obj, end).replace(tzinfo=tz)
    dt_break_from = datetime.combine(date_obj, break_from, tz) if break_from else None
    dt_break_to = datetime.combine(date_obj, break_to, tz) if break_to else None

    # Get existing bookings for this professional on this date
    bookings = Booking.objects.filter(professional=professional, data=date_obj)
    busy_times = []
    for b in bookings:
        if b.start_time and b.end_time:
            busy_times.append((datetime.combine(date_obj, b.start_time, tz), datetime.combine(date_obj, b.end_time, tz)))

    # Generate slots
    slots = []
    slot_length = timedelta(minutes=total_duration)
    current = dt_start
    while current + slot_length <= dt_end:
        slot_end = current + slot_length
        # Skip if overlaps with break
        if dt_break_from and dt_break_to:
            if (current < dt_break_to and slot_end > dt_break_from):
                current += timedelta(minutes=15)
                continue
        # Skip if overlaps with existing bookings
        overlap = False
        for busy_start, busy_end in busy_times:
            if (current < busy_end and slot_end > busy_start):
                overlap = True
                break
        if not overlap:
            slots.append({
                'start': current.time().strftime('%H:%M'),
                'end': slot_end.time().strftime('%H:%M')
            })
        current += timedelta(minutes=15)  # step by 15 min
    return slots


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = {
        'data': ['exact'],
        'services': ['exact', 'icontains'],
        'professional': ['exact'],
        'room_equipment': ['icontains', 'exact'],
        'class_id': ['exact'],
    }
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='services',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by service name or ID',
            ),
            OpenApiParameter(
                name='professional',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter by professional user ID',
            ),
            OpenApiParameter(
                name='room_equipment',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by room or equipment name',
            ),
            OpenApiParameter(
                name='class_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter by class ID',
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

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
        # and user.remaining_hours < 1
        if getattr(user, 'role', None) in ['professional', 'teacher']:
            return Response(
                {"error": "Insufficient hours. Please subscribe to a pack before booking."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    def perform_create(self, serializer):
        if not self.request.user.role == 'admin':
            serializer.save(professional=self.request.user)
        else:
            serializer.save()
    
    @action(detail=True, methods=['GET'])
    def approve(self, request, pk=None):
        """Admin-only endpoint to approve a reservation"""
        return self._change_booking_status(pk, 'confirmed', request)

    @action(detail=True, methods=['GET'])
    def reject(self, request, pk=None):
        """Admin-only endpoint to reject a reservation"""
        return self._change_booking_status(pk, 'cancelled', request)

    def _change_booking_status(self, pk, new_status, request):
        booking = self.get_object()

        # Admin can change status for any reservation
        if request.user.role == 'admin':
            pass
        # Professional (professional/teacher) can change only their own reservations
        elif request.user.role in ['professional', 'teacher']:
            if booking.professional != request.user:
                return Response(
                    {"detail": "You can only change status for your own reservations"},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(
                {"detail": "You are not allowed to change reservation status"},
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
        subject = f"Reservation {status}"
        time_text = ''
        if booking.start_time and booking.end_time:
            time_text = f" from {booking.start_time} to {booking.end_time}"
        message = f"Your reservation for {booking.data}{time_text} has been {status}"
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
                description='Filter by reservation status',
                enum=['pending', 'confirmed', 'cancelled'],
            ),
        ],
    )
    @action(detail=False, methods=['get'])
    def filter_reservations(self, request):
        """
        Filter reservations by day, week, or month
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
        
        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param.lower())
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
# from rest_framework import viewsets, status, permissions
# from rest_framework.response import Response
# from rest_framework.decorators import action
# from datetime import datetime, timedelta
# from dateutil.relativedelta import relativedelta

# from drf_spectacular.utils import extend_schema, OpenApiParameter
# from drf_spectacular.types import OpenApiTypes


# from django_filters.rest_framework import DjangoFilterBackend
# from rest_framework.filters import SearchFilter, OrderingFilter

# from .models import Booking, TIME_SLOTS
# from .serializers import BookingSerializer

# from django.db.models import Case, When, Value, IntegerField
# from django.utils import timezone

# class BookingViewSet(viewsets.ModelViewSet):
#     serializer_class = BookingSerializer
#     filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
#     filterset_fields = {
#         'data': ['exact'],
#     }
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         # During schema generation (swagger_fake_view) self.request may be a dummy
#         # or have an AnonymousUser without the expected attributes. Guard against that.
#         if getattr(self, 'swagger_fake_view', False):
#             return Booking.objects.none()

#         user = getattr(self.request, 'user', None)
#         if user is None or getattr(user, 'is_authenticated', False) is False:
#             return Booking.objects.none()
#         now = timezone.now().date()

#         base_qs = Booking.objects.annotate(
#             is_past=Case(
#                 When(data__lt=now, then=Value(1)),
#                 default=Value(0),
#                 output_field=IntegerField(),
#             )
#         ).order_by('is_past', 'data', 'start_time')

#         if user.role == 'admin':
#             return base_qs
#         if user.role in ['professional', 'teacher']:
#             return base_qs.filter(professional=user)
#         return Booking.objects.none()

#     def create(self, request, *args, **kwargs):
#         user = request.user

#         # Professionals/teachers must have at least 1 remaining hour to book
#         #  and user.remaining_hours < 1
#         if getattr(user, 'role', None) in ['professional', 'teacher']:
#             return Response(
#                 {"error": "Insufficient hours. Please subscribe to a pack before booking."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         self.perform_create(serializer)
#         headers = self.get_success_headers(serializer.data)
#         return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

#     # @extend_schema(
#     #     parameters=[
#     #         OpenApiParameter(
#     #             name='date',
#     #             type=OpenApiTypes.DATE,
#     #             location=OpenApiParameter.QUERY,
#     #             description='Date to get available slots for (format: YYYY-MM-DD)',
#     #         ),
#     #     ],
#     #     responses={
#     #         200: OpenApiTypes.OBJECT,
#     #         400: OpenApiTypes.OBJECT,
#     #     },
#     # )
#     # @action(detail=False, methods=['get'])
#     # def available_slots(self, request):
#     #     """Get all available slots for a specific date"""
#     #     date = request.query_params.get('date')
#     #     if not date:
#     #         return Response(
#     #             {"error": "Date parameter is required"},
#     #             status=status.HTTP_400_BAD_REQUEST
#     #         )

#     #     # The Booking model now stores start_time/end_time rather than a time_slot string.
#     #     # For backwards compatibility return the available TIME_SLOTS list unfiltered here.
#     #     from .models import TIME_SLOTS

#     #     available = [
#     #         {'value': slot[0], 'display': slot[1]}
#     #         for slot in TIME_SLOTS
#     #     ]

#     #     return Response(available)

#     @extend_schema(
#         parameters=[
#             OpenApiParameter(
#                 name='professional_id',
#                 type=OpenApiTypes.INT,
#                 location=OpenApiParameter.QUERY,
#                 description='Professional user ID',
#             ),
#             OpenApiParameter(
#                 name='date',
#                 type=OpenApiTypes.DATE,
#                 location=OpenApiParameter.QUERY,
#                 description='Date to get available slots for (format: YYYY-MM-DD)',
#             ),
#             OpenApiParameter(
#                 name='service_ids',
#                 type=OpenApiTypes.STR,
#                 location=OpenApiParameter.QUERY,
#                 description='Comma-separated list of service IDs to sum durations',
#             ),
#         ],
#         responses={
#             200: OpenApiTypes.OBJECT,
#             400: OpenApiTypes.OBJECT,
#         },
#     )
#     @action(detail=False, methods=['get'])
#     def available_slots(self, request):
#         """Get all available slots for a specific professional, date, and total duration of multiple services"""
#         from datetime import datetime, timedelta, time
#         professional_id = request.query_params.get('professional_id')
#         date_str = request.query_params.get('date')
#         service_ids_str = request.query_params.get('service_ids')
#         if not (professional_id and date_str and service_ids_str):
#             return Response(
#                 {"error": "professional_id, date, and service_ids are required"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         try:
#             professional = User.objects.get(id=professional_id)
#         except User.DoesNotExist:
#             return Response({"error": "Invalid professional ID"}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
#         except Exception:
#             return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             service_ids = [int(sid) for sid in service_ids_str.split(',') if sid.strip()]
#             services = Service.objects.filter(id__in=service_ids)
#             if services.count() != len(service_ids):
#                 return Response({"error": "One or more service IDs are invalid."}, status=status.HTTP_400_BAD_REQUEST)
#             total_duration = sum(s.duration for s in services)
#         except Exception:
#             return Response({"error": "Invalid service_ids parameter."}, status=status.HTTP_400_BAD_REQUEST)

#         slots = get_available_slots_for_professional(professional, date_obj, total_duration)
#         return Response(slots)


#     def perform_create(self, serializer):
#         if not self.request.user.role == 'admin':
#             serializer.save(professional=self.request.user)
#         else:
#             serializer.save()
    
#     @action(detail=True, methods=['GET'])
#     def approve(self, request, pk=None):
#         """Admin-only endpoint to approve a booking"""
#         return self._change_booking_status(pk, 'confirmed', request)

    
#     @action(detail=True, methods=['GET'])
#     def reject(self, request, pk=None):
#         """Admin-only endpoint to reject a booking"""
#         return self._change_booking_status(pk, 'cancelled', request)

    
#     def _change_booking_status(self, pk, new_status, request):
#         booking = self.get_object()

#         # Admin can change status for any booking
#         if request.user.role == 'admin':
#             pass
#         # Professional (professional/teacher) can change only their own bookings
#         elif request.user.role in ['professional', 'teacher']:
#             if booking.professional != request.user:
#                 return Response(
#                     {"detail": "You can only change status for your own bookings"},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#         else:
#             return Response(
#                 {"detail": "You are not allowed to change booking status"},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         # Update status
#         booking.status = new_status
#         booking.save()

#         serializer = self.get_serializer(booking)
#         self._send_status_notification(booking, new_status)

#         return Response(serializer.data, status=status.HTTP_200_OK)


    
#     def _send_status_notification(self, booking, status):
#         """Example notification method (implement with your email service)"""
#         subject = f"Booking {status}"
#         time_text = ''
#         if booking.start_time and booking.end_time:
#             time_text = f" from {booking.start_time} to {booking.end_time}"
#         message = f"Your booking for {booking.data}{time_text} has been {status}"
#         print(f"Notification sent: {subject} - {message}")

#     @extend_schema(
#         parameters=[
#             OpenApiParameter(
#                 name='month',
#                 type=OpenApiTypes.STR,
#                 location=OpenApiParameter.QUERY,
#                 description='Filter by month (format: "Month Year" e.g. "June 2025")',
#             ),
#             OpenApiParameter(
#                 name='week_start',
#                 type=OpenApiTypes.DATE,
#                 location=OpenApiParameter.QUERY,
#                 description='Start date for week filter (format: YYYY-MM-DD)',
#             ),
#             OpenApiParameter(
#                 name='week_end',
#                 type=OpenApiTypes.DATE,
#                 location=OpenApiParameter.QUERY,
#                 description='End date for week filter (format: YYYY-MM-DD)',
#             ),
#             OpenApiParameter(
#                 name='day',
#                 type=OpenApiTypes.DATE,
#                 location=OpenApiParameter.QUERY,
#                 description='Filter by specific day (format: YYYY-MM-DD)',
#             ),
#             OpenApiParameter(
#                 name='status',
#                 type=OpenApiTypes.STR,
#                 location=OpenApiParameter.QUERY,
#                 description='Filter by booking status',
#                 enum=['pending', 'confirmed', 'cancelled'],
#             ),
#         ],
#     )
#     @action(detail=False, methods=['get'])
#     def filter_reservations(self, request):
#         """
#         Filter reservations by day, week, or month
#         Parameters (all optional):
#         - month: "June 2025" (format: "%B %Y")
#         - week_start: "2025-06-01" (format: "%Y-%m-%d")
#         - week_end: "2025-06-07" (format: "%Y-%m-%d")
#         - day: "2025-06-15" (format: "%Y-%m-%d")
#         """
#         queryset = self.get_queryset()
        
#         # Month filter
#         month_str = request.query_params.get('month')
#         if month_str:
#             try:
#                 month_date = datetime.strptime(month_str, "%B %Y").date()
#                 start_date = month_date.replace(day=1)
#                 end_date = start_date + relativedelta(months=1) - timedelta(days=1)
#                 queryset = queryset.filter(
#                     data__gte=start_date,
#                     data__lte=end_date
#                 )
#             except ValueError:
#                 return Response(
#                     {"error": "Invalid month format. Use 'Month Year' (e.g. 'June 2025')"},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
        
#         # Week filter
#         week_start = request.query_params.get('week_start')
#         week_end = request.query_params.get('week_end')
#         if week_start and week_end:
#             try:
#                 start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
#                 end_date = datetime.strptime(week_end, "%Y-%m-%d").date()
#                 queryset = queryset.filter(
#                     data__gte=start_date,
#                     data__lte=end_date
#                 )
#             except ValueError:
#                 return Response(
#                     {"error": "Invalid date format. Use 'YYYY-MM-DD'"},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
        
#         day_str = request.query_params.get('day')
#         if day_str:
#             try:
#                 day_date = datetime.strptime(day_str, "%Y-%m-%d").date()
#                 queryset = queryset.filter(data=day_date)
#             except ValueError:
#                 return Response(
#                     {"error": "Invalid date format. Use 'YYYY-MM-DD'"},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
        
#         status = request.query_params.get('status')
#         if status:
#             queryset = queryset.filter(status=status.lower())
        
#         serializer = self.get_serializer(queryset, many=True)
#         return Response(serializer.data)
