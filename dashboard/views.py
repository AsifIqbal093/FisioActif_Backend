from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, permissions

from reservation.permissions import IsAdminUser
from django.utils import timezone
from datetime import timedelta
from reservation.models import Booking
from user.models import User, Client
from .models import Video
from .serializers import VideoSerializer


from datetime import timedelta


class AnalyticsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()

        """
        API Response Structure for /api/dashboard/analytics/
        {
            "total_reservations": int,
            "total_confirmed_reservations": int,
            "total_canceled_reservations": int,
            "confirmed_last_7_days": int,
            "confirmed_last_30_days": int,
            "confirmed_last_3_months": int,
            "total_clients": int,
            "total_professionals": int,
            "professional_visitors": {
                "last_7_days": [{"date": "YYYY-MM-DD", "count": int}, ...],
                "last_30_days": [{"date": "YYYY-MM-DD", "count": int}, ...],
                "last_3_months": [{"date": "YYYY-MM-DD", "count": int}, ...]
            },
            "client_visitors": {
                "last_7_days": [{"date": "YYYY-MM-DD", "count": int}, ...],
                "last_30_days": [{"date": "YYYY-MM-DD", "count": int}, ...],
                "last_3_months": [{"date": "YYYY-MM-DD", "count": int}, ...]
            }
        }
        """
        # Time ranges (DATE-based)
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        last_3_months = today - timedelta(days=90)

        # Totals
        total_reservations = Booking.objects.count()
        total_confirmed_reservations = Booking.objects.filter(state='confirmed').count()
        total_canceled_reservations = Booking.objects.filter(state='cancel').count()

        # Time-based confirmed reservations (using `data`)
        confirmed_last_7_days = Booking.objects.filter(
            state='confirmed',
            data__gte=last_7_days
        ).count()

        confirmed_last_30_days = Booking.objects.filter(
            state='confirmed',
            data__gte=last_30_days
        ).count()

        confirmed_last_3_months = Booking.objects.filter(
            state='confirmed',
            data__gte=last_3_months
        ).count()

        # Other totals
        total_clients = Client.objects.count()
        total_professionals = User.objects.filter(
            role__in=['professional']
        ).count()

        # Helper to generate date list
        def daterange(start_date, end_date):
            for n in range((end_date - start_date).days + 1):
                yield start_date + timedelta(n)

        # Professional visitors aggregation
        def get_professional_counts(start_date, end_date):
            qs = User.objects.filter(role='professional', date_joined__date__gte=start_date, date_joined__date__lte=end_date)
            counts = {d: 0 for d in daterange(start_date, end_date)}
            for obj in qs:
                join_date = obj.date_joined.date()
                if join_date in counts:
                    counts[join_date] += 1
            return [{"date": d.strftime('%Y-%m-%d'), "count": counts[d]} for d in counts]

        # Client visitors aggregation
        def get_client_counts(start_date, end_date):
            qs = Client.objects.filter(joined_at__date__gte=start_date, joined_at__date__lte=end_date)
            counts = {d: 0 for d in daterange(start_date, end_date)}
            for obj in qs:
                join_date = obj.joined_at.date()
                if join_date in counts:
                    counts[join_date] += 1
            return [{"date": d.strftime('%Y-%m-%d'), "count": counts[d]} for d in counts]

        professional_visitors = {
            "last_7_days": get_professional_counts(today - timedelta(days=6), today),
            "last_30_days": get_professional_counts(today - timedelta(days=29), today),
            "last_3_months": get_professional_counts(today - timedelta(days=89), today),
        }
        client_visitors = {
            "last_7_days": get_client_counts(today - timedelta(days=6), today),
            "last_30_days": get_client_counts(today - timedelta(days=29), today),
            "last_3_months": get_client_counts(today - timedelta(days=89), today),
        }

        return Response({
            "total_reservations": total_reservations,
            "total_confirmed_reservations": total_confirmed_reservations,
            "total_canceled_reservations": total_canceled_reservations,
            "confirmed_last_7_days": confirmed_last_7_days,
            "confirmed_last_30_days": confirmed_last_30_days,
            "confirmed_last_3_months": confirmed_last_3_months,
            "total_clients": total_clients,
            "total_professionals": total_professionals,
            "professional_visitors": professional_visitors,
            "client_visitors": client_visitors,
        })



class VideoViewSet(viewsets.ModelViewSet):
    queryset = Video.objects.all().order_by('-id')
    serializer_class = VideoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        if self.request.user.role == 'admin':
            serializer.save(uploaded_by=self.request.user)
