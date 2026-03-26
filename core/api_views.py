from rest_framework import viewsets, status, generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Sum, Count, F
from datetime import timedelta
from decimal import Decimal
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from vehicles.models import Vehicle, VehicleType
from trips.models import Trip
from trips.gps_models import TripLocation, GPSTrackingSession
from maintenance.models import Maintenance, MaintenanceType, MaintenanceProvider
from fuel.models import FuelTransaction, FuelStation
from documents.models import Document, DocumentType
from accounts.models import CustomUser
from .serializers import (
    VehicleSerializer, VehicleTypeSerializer,
    TripSerializer, TripCreateSerializer, TripEndSerializer,
    MaintenanceSerializer, MaintenanceTypeSerializer,
    FuelTransactionSerializer, FuelStationSerializer,
    DocumentSerializer, DocumentTypeSerializer,
    UserSerializer, LoginSerializer,
    P2PSORSerializer,
)


class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response(
                {'detail': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'detail': 'Account is inactive'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user has mobile access
        if not user.can_access_mobile():
            return Response(
                {'detail': 'Your account is configured for web access only. Please use the web portal to log in.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data,
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            request.user.auth_token.delete()
        except:
            pass
        return Response({'detail': 'Successfully logged out'})


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return Response(UserSerializer(request.user).data)
    
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserProfileStatsView(APIView):
    """Get user's profile statistics - total trips, distance, and fuel entries"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get total trips for this user
        trips = Trip.objects.filter(driver=user, is_deleted=False)
        total_trips = trips.count()
        
        # Get total distance traveled (only from completed trips with valid odometer readings)
        completed_trips = trips.filter(
            status='completed',
            end_odometer__isnull=False,
            start_odometer__isnull=False
        )
        total_distance = completed_trips.aggregate(
            total=Sum(F('end_odometer') - F('start_odometer'))
        )['total'] or 0
        
        # Get total fuel entries
        total_fuel_entries = FuelTransaction.objects.filter(driver=user).count()
        
        return Response({
            'total_trips': total_trips,
            'total_distance': total_distance,
            'total_fuel_entries': total_fuel_entries,
        })


class PersonalVehicleListView(APIView):
    """Get personal vehicles owned by the logged-in user"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.user_type != 'personal_vehicle_staff':
            return Response(
                {'detail': 'This endpoint is only for personal vehicle staff'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        vehicles = Vehicle.objects.filter(
            ownership_type='personal',
            owned_by=user
        ).order_by('license_plate')
        
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        
        vehicles_data = []
        for vehicle in vehicles:
            # Get trip statistics for this vehicle
            trips = Trip.objects.filter(
                vehicle=vehicle,
                driver=user,
                is_deleted=False
            )
            
            # Current month completed trips
            current_month_trips = trips.filter(
                start_time__gte=first_of_month,
                status='completed',
                end_odometer__isnull=False,
                start_odometer__isnull=False
            )
            
            # Calculate total distance for current month
            total_distance = current_month_trips.aggregate(
                total=Sum(F('end_odometer') - F('start_odometer'))
            )['total'] or 0
            
            # Calculate reimbursement
            reimbursement_amount = 0
            if vehicle.reimbursement_rate_per_km:
                reimbursement_amount = float(total_distance) * float(vehicle.reimbursement_rate_per_km)
            
            # Ongoing trips
            ongoing_trips = trips.filter(status='ongoing').count()
            
            vehicle_data = VehicleSerializer(vehicle).data
            vehicle_data.update({
                'current_month_trips_count': current_month_trips.count(),
                'current_month_distance': total_distance,
                'current_month_reimbursement': round(reimbursement_amount, 2),
                'reimbursement_rate_per_km': float(vehicle.reimbursement_rate_per_km) if vehicle.reimbursement_rate_per_km else 0,
                'total_trips': trips.count(),
                'ongoing_trips': ongoing_trips,
            })
            vehicles_data.append(vehicle_data)
        
        return Response(vehicles_data)


class PersonalVehicleDetailView(APIView):
    """Get details of a specific personal vehicle"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        user = request.user
        
        try:
            vehicle = Vehicle.objects.get(
                pk=pk,
                ownership_type='personal',
                owned_by=user
            )
        except Vehicle.DoesNotExist:
            return Response(
                {'detail': 'Vehicle not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        
        # Get trip statistics
        trips = Trip.objects.filter(
            vehicle=vehicle,
            driver=user,
            is_deleted=False
        )
        
        # Current month completed trips
        current_month_trips = trips.filter(
            start_time__gte=first_of_month,
            status='completed',
            end_odometer__isnull=False,
            start_odometer__isnull=False
        )
        
        total_distance = current_month_trips.aggregate(
            total=Sum(F('end_odometer') - F('start_odometer'))
        )['total'] or 0
        
        reimbursement_amount = 0
        if vehicle.reimbursement_rate_per_km:
            reimbursement_amount = float(total_distance) * float(vehicle.reimbursement_rate_per_km)
        
        # Recent trips
        recent_trips = trips.filter(
            status='completed'
        ).order_by('-start_time')[:10]
        
        vehicle_data = VehicleSerializer(vehicle).data
        vehicle_data.update({
            'current_month_trips_count': current_month_trips.count(),
            'current_month_distance': total_distance,
            'current_month_reimbursement': round(reimbursement_amount, 2),
            'reimbursement_rate_per_km': float(vehicle.reimbursement_rate_per_km) if vehicle.reimbursement_rate_per_km else 0,
            'total_trips': trips.count(),
            'ongoing_trips': trips.filter(status='ongoing').count(),
            'recent_trips': TripSerializer(recent_trips, many=True).data,
        })
        
        return Response(vehicle_data)
    
    def patch(self, request, pk):
        """Update personal vehicle (limited fields)"""
        user = request.user
        
        try:
            vehicle = Vehicle.objects.get(
                pk=pk,
                ownership_type='personal',
                owned_by=user
            )
        except Vehicle.DoesNotExist:
            return Response(
                {'detail': 'Vehicle not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only allow updating certain fields
        allowed_fields = ['current_odometer', 'notes']
        for field in allowed_fields:
            if field in request.data:
                setattr(vehicle, field, request.data[field])
        
        vehicle.save()
        return Response(VehicleSerializer(vehicle).data)


class PersonalVehicleReimbursementView(APIView):
    """Get reimbursement summary and history for personal vehicle staff"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.user_type != 'personal_vehicle_staff':
            return Response(
                {'detail': 'This endpoint is only for personal vehicle staff'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user's personal vehicles
        vehicles = Vehicle.objects.filter(
            ownership_type='personal',
            owned_by=user
        )
        
        if not vehicles.exists():
            return Response({
                'has_vehicles': False,
                'message': 'No personal vehicles registered'
            })
        
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        
        # Get all completed trips for this month across all personal vehicles
        trips = Trip.objects.filter(
            driver=user,
            vehicle__in=vehicles,
            status='completed',
            is_deleted=False,
            end_odometer__isnull=False,
            start_odometer__isnull=False
        ).select_related('vehicle').order_by('-start_time')
        
        current_month_trips = trips.filter(start_time__gte=first_of_month)
        
        # Calculate totals
        total_distance = 0
        total_reimbursement = 0
        trips_data = []
        
        for trip in current_month_trips:
            distance = trip.end_odometer - trip.start_odometer
            rate = float(trip.vehicle.reimbursement_rate_per_km) if trip.vehicle.reimbursement_rate_per_km else 0
            reimbursement = distance * rate
            
            total_distance += distance
            total_reimbursement += reimbursement
            
            trip_data = TripSerializer(trip).data
            trip_data['distance'] = distance
            trip_data['reimbursement_rate'] = rate
            trip_data['reimbursement_amount'] = round(reimbursement, 2)
            trips_data.append(trip_data)
        
        # Monthly history (last 6 months)
        monthly_history = []
        for i in range(6):
            month_date = (today - timedelta(days=30*i))
            month_start = month_date.replace(day=1)
            if i == 0:
                month_end = today
            else:
                # Get last day of month
                if month_start.month == 12:
                    month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
            
            month_trips = trips.filter(
                start_time__gte=month_start,
                start_time__lte=month_end
            )
            
            month_distance = 0
            month_reimbursement = 0
            
            for trip in month_trips:
                distance = trip.end_odometer - trip.start_odometer
                rate = float(trip.vehicle.reimbursement_rate_per_km) if trip.vehicle.reimbursement_rate_per_km else 0
                month_distance += distance
                month_reimbursement += distance * rate
            
            monthly_history.append({
                'month': month_start.strftime('%B %Y'),
                'month_short': month_start.strftime('%b'),
                'year': month_start.year,
                'trips_count': month_trips.count(),
                'total_distance': month_distance,
                'total_reimbursement': round(month_reimbursement, 2),
            })
        
        return Response({
            'has_vehicles': True,
            'current_month': {
                'month': first_of_month.strftime('%B %Y'),
                'trips_count': current_month_trips.count(),
                'total_distance': total_distance,
                'total_reimbursement': round(total_reimbursement, 2),
            },
            'trips': trips_data,
            'monthly_history': monthly_history,
        })


class PersonalVehicleDashboardView(APIView):
    """Get dashboard stats specifically for personal vehicle staff"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        
        # Get user's personal vehicles
        vehicles = Vehicle.objects.filter(
            ownership_type='personal',
            owned_by=user
        )
        
        # Active trips
        active_trips = Trip.objects.filter(
            driver=user,
            status='ongoing',
            is_deleted=False
        ).count()
        
        # Monthly trips
        monthly_trips = Trip.objects.filter(
            driver=user,
            vehicle__in=vehicles,
            start_time__gte=first_of_month,
            status='completed',
            is_deleted=False,
            end_odometer__isnull=False,
            start_odometer__isnull=False
        )
        
        # Calculate monthly distance and reimbursement
        monthly_distance = 0
        monthly_reimbursement = 0
        
        for trip in monthly_trips:
            distance = trip.end_odometer - trip.start_odometer
            monthly_distance += distance
            if trip.vehicle.reimbursement_rate_per_km:
                monthly_reimbursement += distance * float(trip.vehicle.reimbursement_rate_per_km)
        
        return Response({
            'total_vehicles': vehicles.count(),
            'active_trips': active_trips,
            'monthly_trips': monthly_trips.count(),
            'monthly_distance': monthly_distance,
            'monthly_reimbursement': round(monthly_reimbursement, 2),
        })


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        
        # Role-based data access
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        is_driver = user.user_type == 'driver'
        is_personal_vehicle_staff = user.user_type == 'personal_vehicle_staff'
        
        data = {
            'user_type': user.user_type,
            'is_admin': is_admin,
        }
        
        if is_admin:
            # Admins see all company vehicles
            data['total_vehicles'] = Vehicle.objects.filter(ownership_type='company').count()
            data['active_trips'] = Trip.objects.filter(status='ongoing', is_deleted=False).count()
            data['scheduled_maintenance'] = Maintenance.objects.filter(status='scheduled').count()
            
            # All monthly stats
            monthly_trips = Trip.objects.filter(
                start_time__gte=first_of_month,
                status='completed',
                is_deleted=False
            )
        elif is_personal_vehicle_staff:
            # Personal vehicle staff see their own vehicles
            personal_vehicles = Vehicle.objects.filter(ownership_type='personal', owned_by=user)
            data['total_vehicles'] = personal_vehicles.count()
            data['active_trips'] = Trip.objects.filter(
                driver=user, 
                status='ongoing', 
                is_deleted=False
            ).count()
            data['scheduled_maintenance'] = Maintenance.objects.filter(
                vehicle__in=personal_vehicles,
                status='scheduled'
            ).count()
            
            monthly_trips = Trip.objects.filter(
                driver=user,
                start_time__gte=first_of_month,
                status='completed',
                is_deleted=False
            )
        else:
            # Drivers see available company vehicles they can use
            data['total_vehicles'] = Vehicle.objects.filter(
                ownership_type='company', 
                status='available'
            ).count()
            data['active_trips'] = Trip.objects.filter(
                driver=user, 
                status='ongoing', 
                is_deleted=False
            ).count()
            data['scheduled_maintenance'] = 0  # Drivers don't see maintenance
            
            monthly_trips = Trip.objects.filter(
                driver=user,
                start_time__gte=first_of_month,
                status='completed',
                is_deleted=False
            )
        
        monthly_stats = monthly_trips.aggregate(
            total_distance=Sum(F('end_odometer') - F('start_odometer')),
            trip_count=Count('id')
        )
        
        data['monthly_distance'] = monthly_stats['total_distance'] or 0
        data['monthly_trips'] = monthly_stats['trip_count'] or 0
        
        return Response(data)


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return DashboardView().get(request)


class VehicleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = VehicleSerializer
    # Paginated — safe for 300+ users with many vehicles
    # PAGE_SIZE inherited from global settings (20)
    
    def _is_admin(self):
        return self.request.user.user_type in ['admin', 'manager', 'vehicle_manager']
    
    def get_queryset(self):
        user = self.request.user
        is_admin = self._is_admin()
        is_personal_vehicle_staff = user.user_type == 'personal_vehicle_staff'
        
        if is_admin:
            # Admins see all vehicles
            queryset = Vehicle.objects.all()
        elif is_personal_vehicle_staff:
            # Personal vehicle staff see only their own vehicles
            queryset = Vehicle.objects.filter(ownership_type='personal', owned_by=user)
        else:
            # Check if driver has active consultant rate assignments
            from trips.consultant_models import ConsultantRate
            consultant_vehicle_ids = list(ConsultantRate.objects.filter(
                driver=user, status='active'
            ).values_list('vehicle_id', flat=True))
            if consultant_vehicle_ids:
                # Consultant drivers see their assigned vehicles (exclude only retired)
                queryset = Vehicle.objects.filter(
                    id__in=consultant_vehicle_ids
                ).exclude(status='retired')
            else:
                # Regular drivers see company vehicles
                queryset = Vehicle.objects.filter(ownership_type='company')
        
        # Apply status filter if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('vehicle_type')
    
    def create(self, request, *args, **kwargs):
        if not self._is_admin():
            return Response({'detail': 'Only admin/manager users can create vehicles.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        if not self._is_admin():
            return Response({'detail': 'Only admin/manager users can update vehicles.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        if not self._is_admin():
            return Response({'detail': 'Only admin/manager users can update vehicles.'}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        if not self._is_admin():
            return Response({'detail': 'Only admin/manager users can delete vehicles.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class VehicleTypeListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VehicleTypeSerializer
    queryset = VehicleType.objects.all()


class TripViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TripSerializer
    
    def get_queryset(self):
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        
        if is_admin:
            # Admins see all trips
            queryset = Trip.objects.filter(is_deleted=False)
        else:
            # Drivers see only their own trips
            queryset = Trip.objects.filter(driver=user, is_deleted=False)
        
        return queryset.select_related('vehicle', 'driver').order_by('-start_time')


class StartTripView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = TripCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        trip = serializer.save()
        return Response(TripSerializer(trip).data, status=status.HTTP_201_CREATED)


class TripUploadOdometerImageView(APIView):
    """Upload odometer image for a trip (start or end) - for background uploads"""
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, is_deleted=False)
        except Trip.DoesNotExist:
            return Response({'detail': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Only the driver who created the trip can upload images
        if trip.driver != request.user:
            return Response({'detail': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        
        image_type = request.data.get('image_type', 'start')  # 'start' or 'end'
        image = request.FILES.get('image')
        
        if not image:
            return Response({'detail': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        if image_type == 'start':
            trip.start_odometer_image = image
        elif image_type == 'end':
            trip.end_odometer_image = image
        else:
            return Response({'detail': 'Invalid image_type. Use "start" or "end"'}, status=status.HTTP_400_BAD_REQUEST)
        
        trip.save()
        return Response({'detail': 'Image uploaded successfully', 'trip_id': trip.id})


class EndTripView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, is_deleted=False)
        except Trip.DoesNotExist:
            return Response({'detail': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Ownership check: only the trip's driver or admin/manager can end a trip
        is_admin = request.user.user_type in ['admin', 'manager', 'vehicle_manager']
        if trip.driver != request.user and not is_admin:
            return Response({'detail': 'You do not have permission to end this trip'}, status=status.HTTP_403_FORBIDDEN)
        
        if trip.status != 'ongoing':
            return Response({'detail': 'Trip is not ongoing'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = TripEndSerializer(trip, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        trip.destination = serializer.validated_data['destination']
        trip.end_odometer = serializer.validated_data['end_odometer']
        trip.end_time = timezone.now()
        trip.status = 'completed'
        trip.notes = serializer.validated_data.get('notes', trip.notes)
        
        # Handle end odometer image if provided
        if 'end_odometer_image' in serializer.validated_data and serializer.validated_data['end_odometer_image']:
            trip.end_odometer_image = serializer.validated_data['end_odometer_image']
        
        trip.save()
        
        # Update SOR status if this trip is linked to a SOR
        from sor.models import SOR
        try:
            sor = SOR.objects.get(trip=trip)
            sor.status = 'completed'
            # Set SOR distance_km from trip distance
            if trip.end_odometer and trip.start_odometer:
                sor.distance_km = trip.end_odometer - trip.start_odometer
            sor.save()
        except SOR.DoesNotExist:
            pass
        
        # ZeptoMail alert for suspicious distance (async via Celery)
        if trip.distance_traveled() > 300:
            from trips.tasks import send_trip_alert_email_async
            send_trip_alert_email_async.delay(trip.pk)
        
        return Response(TripSerializer(trip).data)


class MyTripsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TripSerializer
    
    def get_queryset(self):
        return Trip.objects.filter(
            driver=self.request.user,
            is_deleted=False
        ).select_related('vehicle', 'driver').order_by('-start_time')


class OngoingTripsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TripSerializer
    
    def get_queryset(self):
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        
        if is_admin:
            # Admins see all ongoing trips
            return Trip.objects.filter(
                status='ongoing',
                is_deleted=False
            ).select_related('vehicle', 'driver')
        else:
            # Drivers see only their own ongoing trips
            return Trip.objects.filter(
                driver=user,
                status='ongoing',
                is_deleted=False
            ).select_related('vehicle', 'driver')


class MaintenanceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MaintenanceSerializer
    
    def get_queryset(self):
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        is_personal_vehicle_staff = user.user_type == 'personal_vehicle_staff'
        
        if is_admin:
            # Admins see all maintenance records
            queryset = Maintenance.objects.all()
        elif is_personal_vehicle_staff:
            # Personal vehicle staff see maintenance for their vehicles
            personal_vehicles = Vehicle.objects.filter(ownership_type='personal', owned_by=user)
            queryset = Maintenance.objects.filter(vehicle__in=personal_vehicles)
        else:
            # Drivers see maintenance records they reported
            queryset = Maintenance.objects.filter(reported_by=user)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('vehicle', 'maintenance_type', 'provider')


class MaintenanceTypeListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MaintenanceTypeSerializer
    queryset = MaintenanceType.objects.all()


class FuelTransactionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FuelTransactionSerializer
    
    def get_queryset(self):
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        
        if is_admin:
            # Admins see all fuel transactions
            queryset = FuelTransaction.objects.all()
        else:
            # Drivers see only their own fuel transactions
            queryset = FuelTransaction.objects.filter(driver=user)
        
        return queryset.select_related('vehicle', 'driver', 'fuel_station').order_by('-date')
    
    def perform_create(self, serializer):
        serializer.save(driver=self.request.user)


class FuelStationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FuelStationSerializer
    queryset = FuelStation.objects.all()


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer
    
    def get_queryset(self):
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        is_personal_vehicle_staff = user.user_type == 'personal_vehicle_staff'
        
        if is_admin:
            # Admins see all documents
            queryset = Document.objects.all()
        elif is_personal_vehicle_staff:
            # Personal vehicle staff only see documents for their personal vehicles
            personal_vehicles = Vehicle.objects.filter(ownership_type='personal', owned_by=user)
            queryset = Document.objects.filter(vehicle__in=personal_vehicles)
        else:
            # Other users (drivers) see documents for vehicles assigned to them or no documents
            queryset = Document.objects.none()
        
        queryset = queryset.select_related('vehicle', 'document_type')
        
        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Validate that Personal Vehicle Staff can only create documents for their vehicles"""
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        is_personal_vehicle_staff = user.user_type == 'personal_vehicle_staff'
        
        vehicle = serializer.validated_data.get('vehicle')
        
        if is_personal_vehicle_staff:
            # Verify the vehicle belongs to this user
            if not vehicle or vehicle.ownership_type != 'personal' or vehicle.owned_by != user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You can only add documents to your own personal vehicles")
        elif not is_admin:
            # Drivers cannot create documents
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to create documents")
        
        serializer.save()
    
    def perform_update(self, serializer):
        """Validate that Personal Vehicle Staff can only update their own documents"""
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        is_personal_vehicle_staff = user.user_type == 'personal_vehicle_staff'
        
        document = self.get_object()
        
        if is_personal_vehicle_staff:
            # Verify the document belongs to user's vehicle
            if document.vehicle.ownership_type != 'personal' or document.vehicle.owned_by != user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You can only update documents for your own personal vehicles")
        elif not is_admin:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to update documents")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Validate that Personal Vehicle Staff can only delete their own documents"""
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        is_personal_vehicle_staff = user.user_type == 'personal_vehicle_staff'
        
        if is_personal_vehicle_staff:
            # Verify the document belongs to user's vehicle
            if instance.vehicle.ownership_type != 'personal' or instance.vehicle.owned_by != user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You can only delete documents for your own personal vehicles")
        elif not is_admin:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to delete documents")
        
        instance.delete()


class DocumentTypeListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentTypeSerializer
    queryset = DocumentType.objects.all()


class ExpiringDocumentsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer
    
    def get_queryset(self):
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        is_personal_vehicle_staff = user.user_type == 'personal_vehicle_staff'
        
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)
        
        if is_admin:
            # Admins see all expiring documents
            queryset = Document.objects.filter(
                expiry_date__range=[today, thirty_days_later]
            )
        elif is_personal_vehicle_staff:
            # Personal vehicle staff only see expiring documents for their personal vehicles
            personal_vehicles = Vehicle.objects.filter(ownership_type='personal', owned_by=user)
            queryset = Document.objects.filter(
                vehicle__in=personal_vehicles,
                expiry_date__range=[today, thirty_days_later]
            )
        else:
            # Other users see no expiring documents
            queryset = Document.objects.none()
        
        return queryset.select_related('vehicle', 'document_type').order_by('expiry_date')


# ============== SOR API Views ==============
from sor.models import SOR
from sor.notification import SORNotification
from .serializers import SORSerializer, SORNotificationSerializer


class SORListView(generics.ListAPIView):
    """List SOR entries for the logged-in driver"""
    permission_classes = [IsAuthenticated]
    serializer_class = SORSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        
        if user.user_type in ['admin', 'manager', 'vehicle_manager', 'sor_head']:
            queryset = SOR.objects.all()
        elif user.user_type == 'driver':
            queryset = SOR.objects.filter(driver=user)
        else:
            queryset = SOR.objects.filter(created_by=user)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('vehicle', 'driver', 'created_by').order_by('-created_at')


class SORCreateView(APIView):
    """Create a new SOR entry (for sor_team, sor_head, admin, manager)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        allowed = ['admin', 'manager', 'vehicle_manager', 'sor_team', 'sor_head']
        if request.user.user_type not in allowed:
            return Response(
                {'detail': 'You do not have permission to create SOR entries.'},
                status=status.HTTP_403_FORBIDDEN
            )

        from core.serializers import SORCreateSerializer
        serializer = SORCreateSerializer(data=request.data)
        if serializer.is_valid():
            sor = serializer.save(created_by=request.user)
            # Create notification for driver
            from sor.notification import SORNotification
            SORNotification.objects.create(
                sor=sor,
                driver=sor.driver,
                message=f"You have a new SOR assignment from {sor.from_location} to {sor.to_location}. Please accept or reject.",
            )
            # Return full SOR detail
            return Response(SORSerializer(sor).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SORFormOptionsView(APIView):
    """Return available vehicles and drivers for SOR creation form"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Commercial vehicles not on an ongoing trip
        ongoing_vehicle_ids = Trip.objects.filter(status='ongoing').values_list('vehicle_id', flat=True)
        vehicles = Vehicle.objects.filter(
            vehicle_type__category='commercial'
        ).exclude(
            id__in=ongoing_vehicle_ids
        ).select_related('vehicle_type').order_by('license_plate')

        # Active drivers
        drivers = CustomUser.objects.filter(
            user_type='driver', is_active=True
        ).order_by('first_name', 'last_name')

        vehicle_data = [
            {'id': v.id, 'license_plate': v.license_plate, 'make': v.make, 'model': v.model}
            for v in vehicles
        ]
        driver_data = [
            {'id': d.id, 'name': d.get_full_name() or d.username, 'username': d.username}
            for d in drivers
        ]

        # Location choices (same as web form)
        locations = [
            'Attakulangara', 'Pazhavangadi', 'Enchakkal', 'Ulloor',
            'Attingal', 'Vellayamvbalam', 'Mall Of Travancore',
            'Neyyatinkara', 'Courtallam', 'Thirumala', 'Nedumangadu',
            'Karakkamandapam', 'Marthandam', 'Panachamoodu', 'kattakada',
            'Kodapanamkunnu', 'Kaval Kinaru', 'Ooty', 'Hosur',
            'Enchakal Warehouse', 'Muthoot Warehouse', 'Hindu Warehouse',
        ]

        return Response({
            'vehicles': vehicle_data,
            'drivers': driver_data,
            'locations': locations,
        })


class SORDetailView(generics.RetrieveAPIView):
    """Get details of a specific SOR"""
    permission_classes = [IsAuthenticated]
    serializer_class = SORSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type in ['admin', 'manager', 'vehicle_manager', 'sor_head']:
            return SOR.objects.all()
        elif user.user_type == 'driver':
            return SOR.objects.filter(driver=user)
        else:
            return SOR.objects.filter(created_by=user)


class SORAcceptView(APIView):
    """Accept a pending SOR and start the trip"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        user = request.user
        
        try:
            sor = SOR.objects.get(pk=pk, driver=user)
        except SOR.DoesNotExist:
            return Response(
                {'detail': 'SOR not found or you are not the assigned driver.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if sor.status != 'pending':
            return Response(
                {'detail': f'SOR is not pending. Current status: {sor.get_status_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update status to driver_accepted
        sor.status = 'driver_accepted'
        sor.save()
        
        # Start trip automatically
        start_odometer = sor.vehicle.current_odometer or 0
        trip = Trip.objects.create(
            vehicle=sor.vehicle,
            driver=sor.driver,
            start_time=timezone.now(),
            start_odometer=start_odometer,
            origin=sor.from_location,
            destination=sor.to_location,
            purpose=f"SOR Goods Value: {sor.goods_value}",
            notes=f"Started from SOR entry #{sor.id}",
            status='ongoing',
            entry_type='real_time',
        )
        
        sor.trip = trip
        sor.status = 'in_progress'
        sor.save()
        
        # Mark notification as read
        SORNotification.objects.filter(sor=sor, driver=user, is_read=False).update(is_read=True)
        
        return Response({
            'detail': 'SOR accepted and trip started.',
            'sor': SORSerializer(sor).data,
            'trip_id': trip.id,
        })


class SORRejectView(APIView):
    """Reject a pending SOR"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        user = request.user
        
        try:
            sor = SOR.objects.get(pk=pk, driver=user)
        except SOR.DoesNotExist:
            return Response(
                {'detail': 'SOR not found or you are not the assigned driver.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if sor.status != 'pending':
            return Response(
                {'detail': f'SOR is not pending. Current status: {sor.get_status_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update status to rejected
        sor.status = 'rejected'
        sor.save()
        
        # Mark notification as read
        SORNotification.objects.filter(sor=sor, driver=user, is_read=False).update(is_read=True)
        
        return Response({
            'detail': 'SOR rejected.',
            'sor': SORSerializer(sor).data,
        })


class SORNotificationsView(generics.ListAPIView):
    """Get unread SOR notifications for the logged-in driver"""
    permission_classes = [IsAuthenticated]
    serializer_class = SORNotificationSerializer
    
    def get_queryset(self):
        return SORNotification.objects.filter(
            driver=self.request.user,
            is_read=False
        ).select_related('sor').order_by('-created_at')[:10]


class SORNotificationMarkReadView(APIView):
    """Mark a notification as read"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            notification = SORNotification.objects.get(pk=pk, driver=request.user)
            notification.is_read = True
            notification.save()
            return Response({'detail': 'Notification marked as read.'})
        except SORNotification.DoesNotExist:
            return Response(
                {'detail': 'Notification not found.'},
                status=status.HTTP_404_NOT_FOUND
            )


class SORNotificationMarkAllReadView(APIView):
    """Mark all notifications as read for the logged-in driver"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        count = SORNotification.objects.filter(
            driver=request.user,
            is_read=False
        ).update(is_read=True)
        return Response({'detail': f'{count} notifications marked as read.'})


# ============================================
# GPS Tracking API Views for Mobile App
# ============================================

class GPSRecordLocationView(APIView):
    """
    Record GPS location points during an ongoing trip.
    Called periodically by the mobile app while trip is active.
    """
    permission_classes = [IsAuthenticated]
    throttle_scope = 'gps_tracking'
    
    def post(self, request):
        trip_id = request.data.get('trip_id')
        if not trip_id:
            return Response({'error': 'trip_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify trip exists and belongs to current user
        try:
            trip = Trip.objects.get(id=trip_id, driver=request.user, status='ongoing')
        except Trip.DoesNotExist:
            return Response({'error': 'Trip not found or not accessible'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get or create GPS session
        gps_session, created = GPSTrackingSession.objects.get_or_create(
            trip=trip,
            defaults={'status': 'active'}
        )
        
        # Create location record
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not latitude or not longitude:
            return Response({'error': 'latitude and longitude are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        location = TripLocation.objects.create(
            trip=trip,
            latitude=Decimal(str(latitude)),
            longitude=Decimal(str(longitude)),
            accuracy=float(request.data.get('accuracy', 0)),
            speed=float(request.data.get('speed')) if request.data.get('speed') else None,
            altitude=float(request.data.get('altitude')) if request.data.get('altitude') else None,
            heading=float(request.data.get('heading')) if request.data.get('heading') else None,
            battery_level=int(request.data.get('battery_level')) if request.data.get('battery_level') else None,
            timestamp=timezone.now()
        )
        
        # Update session statistics
        gps_session.total_points += 1
        if location.accuracy < 50:  # Consider points with accuracy < 50m as valid
            gps_session.valid_points += 1
        
        # Check for gaps (if last point was more than 60 seconds ago)
        last_location = TripLocation.objects.filter(
            trip=trip
        ).exclude(id=location.id).order_by('-timestamp').first()
        
        if last_location:
            gap_seconds = (location.timestamp - last_location.timestamp).total_seconds()
            if gap_seconds > 60:  # More than 1 minute gap
                gps_session.gaps_detected += 1
                if gap_seconds > gps_session.longest_gap_seconds:
                    gps_session.longest_gap_seconds = int(gap_seconds)
        
        gps_session.save()
        
        return Response({
            'success': True,
            'location_id': location.id,
            'total_points': gps_session.total_points,
        })


class GPSBatchRecordView(APIView):
    """
    Record multiple GPS location points at once.
    Useful when the app was offline and needs to sync buffered locations.
    """
    permission_classes = [IsAuthenticated]
    throttle_scope = 'gps_tracking'
    
    def post(self, request):
        trip_id = request.data.get('trip_id')
        locations = request.data.get('locations', [])
        
        if not trip_id:
            return Response({'error': 'trip_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not locations:
            return Response({'error': 'locations array is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify trip exists and belongs to current user
        try:
            trip = Trip.objects.get(id=trip_id, driver=request.user)
        except Trip.DoesNotExist:
            return Response({'error': 'Trip not found or not accessible'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get or create GPS session
        gps_session, created = GPSTrackingSession.objects.get_or_create(
            trip=trip,
            defaults={'status': 'active'}
        )
        
        saved_count = 0
        for loc_data in locations:
            try:
                latitude = loc_data.get('latitude')
                longitude = loc_data.get('longitude')
                
                if not latitude or not longitude:
                    continue
                
                # Use client-provided timestamp if available, otherwise fallback to server time
                client_timestamp = loc_data.get('timestamp')
                if client_timestamp:
                    try:
                        if isinstance(client_timestamp, (int, float)):
                            point_timestamp = datetime.fromtimestamp(client_timestamp / 1000, tz=timezone.utc)
                        else:
                            point_timestamp = timezone.datetime.fromisoformat(str(client_timestamp))
                    except (ValueError, TypeError, OSError):
                        point_timestamp = timezone.now()
                else:
                    point_timestamp = timezone.now()
                
                TripLocation.objects.create(
                    trip=trip,
                    latitude=Decimal(str(latitude)),
                    longitude=Decimal(str(longitude)),
                    accuracy=float(loc_data.get('accuracy', 0)),
                    speed=float(loc_data.get('speed')) if loc_data.get('speed') else None,
                    altitude=float(loc_data.get('altitude')) if loc_data.get('altitude') else None,
                    heading=float(loc_data.get('heading')) if loc_data.get('heading') else None,
                    battery_level=int(loc_data.get('battery_level')) if loc_data.get('battery_level') else None,
                    timestamp=point_timestamp
                )
                saved_count += 1
                gps_session.total_points += 1
            except Exception as e:
                logger.warning(f"GPS batch: failed to save point for trip {trip_id}: {e}", exc_info=True)
                continue
        
        gps_session.save()
        
        return Response({
            'success': True,
            'saved_count': saved_count,
            'total_points': gps_session.total_points,
        })


class GPSTripStatusView(APIView):
    """
    Get GPS tracking status for a trip.
    Returns session statistics and recent locations.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, trip_id):
        try:
            trip = Trip.objects.get(id=trip_id, driver=request.user)
        except Trip.DoesNotExist:
            return Response({'error': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            session = GPSTrackingSession.objects.get(trip=trip)
            locations = TripLocation.objects.filter(trip=trip).order_by('-timestamp')[:10]
            
            return Response({
                'has_gps_data': True,
                'session': {
                    'status': session.status,
                    'total_points': session.total_points,
                    'valid_points': session.valid_points,
                    'gaps_detected': session.gaps_detected,
                    'gps_distance': float(session.gps_distance) if session.gps_distance else None,
                },
                'recent_locations': [
                    {
                        'latitude': float(loc.latitude),
                        'longitude': float(loc.longitude),
                        'accuracy': loc.accuracy,
                        'timestamp': loc.timestamp.isoformat(),
                    }
                    for loc in locations
                ]
            })
        except GPSTrackingSession.DoesNotExist:
            return Response({
                'has_gps_data': False,
                'session': None,
                'recent_locations': []
            })


class GPSFinalizeView(APIView):
    """
    Finalize GPS tracking when a trip ends.
    Calculates total GPS distance and variance from odometer.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, trip_id):
        try:
            trip = Trip.objects.get(id=trip_id, driver=request.user)
        except Trip.DoesNotExist:
            return Response({'error': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            session = GPSTrackingSession.objects.get(trip=trip)
        except GPSTrackingSession.DoesNotExist:
            return Response({'error': 'No GPS session found for this trip'}, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate GPS distance
        gps_distance = session.calculate_gps_distance()
        session.gps_distance = gps_distance
        
        # Get odometer distance
        if trip.start_odometer and trip.end_odometer:
            odometer_distance = trip.end_odometer - trip.start_odometer
            session.odometer_distance = Decimal(str(odometer_distance))
            
            # Calculate variance
            if odometer_distance > 0:
                variance = abs(float(gps_distance) - odometer_distance) / odometer_distance * 100
                session.variance_percentage = Decimal(str(round(variance, 2)))
                
                # Flag for review if variance is too high (>15%)
                if variance > 15:
                    session.requires_review = True
                    session.review_reason = f"High variance detected: GPS shows {gps_distance:.2f} km, odometer shows {odometer_distance} km ({variance:.1f}% difference)"
        
        session.status = 'completed'
        session.ended_at = timezone.now()
        session.save()
        
        return Response({
            'success': True,
            'gps_distance': float(gps_distance),
            'odometer_distance': float(session.odometer_distance) if session.odometer_distance else None,
            'variance_percentage': float(session.variance_percentage) if session.variance_percentage else None,
            'requires_review': session.requires_review,
        })


class GPSTripRouteView(APIView):
    """
    Get all GPS locations for a trip to display on a map.
    Returns the full route with coordinates.
    Accessible by: trip driver OR admin/manager/vehicle_manager
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, trip_id):
        try:
            trip = Trip.objects.get(id=trip_id)
            # Check permission: must be driver OR management
            allowed_types = ['admin', 'manager', 'vehicle_manager']
            if trip.driver != request.user and request.user.user_type not in allowed_types:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        except Trip.DoesNotExist:
            return Response({'error': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get all locations ordered by timestamp (values_list for memory efficiency)
        locations = TripLocation.objects.filter(trip=trip).order_by('timestamp').only(
            'latitude', 'longitude', 'accuracy', 'speed', 'timestamp'
        )
        
        if not locations.exists():
            return Response({
                'has_route': False,
                'message': 'No GPS data available for this trip',
                'route': [],
                'trip_info': {
                    'id': trip.id,
                    'origin': trip.origin,
                    'destination': trip.destination,
                    'status': trip.status,
                }
            })
        
        # Get GPS session for statistics
        try:
            session = GPSTrackingSession.objects.get(trip=trip)
            gps_distance = float(session.gps_distance) if session.gps_distance else None
            total_points = session.total_points
        except GPSTrackingSession.DoesNotExist:
            gps_distance = None
            total_points = locations.count()
        
        # Build route data
        route = [
            {
                'latitude': float(loc.latitude),
                'longitude': float(loc.longitude),
                'accuracy': loc.accuracy,
                'speed': loc.speed,
                'timestamp': loc.timestamp.isoformat(),
            }
            for loc in locations
        ]
        
        # Calculate bounding box for map display
        lats = [loc.latitude for loc in locations]
        lons = [loc.longitude for loc in locations]
        
        return Response({
            'has_route': True,
            'route': route,
            'total_points': total_points,
            'gps_distance': gps_distance,
            'bounding_box': {
                'min_lat': float(min(lats)),
                'max_lat': float(max(lats)),
                'min_lon': float(min(lons)),
                'max_lon': float(max(lons)),
            },
            'trip_info': {
                'id': trip.id,
                'origin': trip.origin,
                'destination': trip.destination,
                'status': trip.status,
                'start_time': trip.start_time.isoformat() if trip.start_time else None,
                'end_time': trip.end_time.isoformat() if trip.end_time else None,
            }
        })


# ==================== P2P Integration APIs ====================
# These endpoints are for the external P2P (Procure to Pay) system
# to fetch SOR data for creating SIR (Security Inward Register)

class IsP2PServiceAccount(permissions.BasePermission):
    """Permission class that allows only P2P service accounts.
    The P2P team authenticates with a token linked to a user with user_type='p2p_service'.
    Also allows admin users for testing/debugging."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.user_type in ['p2p_service', 'admin']


class P2PSORListView(generics.ListAPIView):
    """List SOR entries available for SIR creation.
    Returns SORs with status 'in_progress' or 'completed' (goods dispatched/delivered).
    
    Query Parameters:
        - status: Filter by specific status ('in_progress' or 'completed')
        - from_location: Filter by source warehouse location (partial match)
        - to_location: Filter by destination store location (partial match)
        - date_from: Filter SORs created on or after this date (YYYY-MM-DD)
        - date_to: Filter SORs created on or before this date (YYYY-MM-DD)
        - search: Search by SOR ID or description
    """
    permission_classes = [IsAuthenticated, IsP2PServiceAccount]
    serializer_class = P2PSORSerializer
    
    def get_queryset(self):
        # Only show SORs that are in_progress or completed (goods dispatched)
        queryset = SOR.objects.filter(
            status__in=['in_progress', 'completed']
        ).select_related('vehicle', 'driver')
        
        # Optional filters
        status_filter = self.request.query_params.get('status')
        if status_filter and status_filter in ['in_progress', 'completed']:
            queryset = queryset.filter(status=status_filter)
        
        from_location = self.request.query_params.get('from_location')
        if from_location:
            queryset = queryset.filter(from_location__icontains=from_location)
        
        to_location = self.request.query_params.get('to_location')
        if to_location:
            queryset = queryset.filter(to_location__icontains=to_location)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        search = self.request.query_params.get('search')
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(id__icontains=search) | Q(description__icontains=search)
            )
        
        return queryset.order_by('-created_at')


class P2PSORDetailView(generics.RetrieveAPIView):
    """Get full details of a specific SOR by ID for SIR creation.
    Only accessible for SORs with status 'in_progress' or 'completed'."""
    permission_classes = [IsAuthenticated, IsP2PServiceAccount]
    serializer_class = P2PSORSerializer
    
    def get_queryset(self):
        return SOR.objects.filter(
            status__in=['in_progress', 'completed']
        ).select_related('vehicle', 'driver')


class P2PSORConfirmReceiptView(APIView):
    """Optional: P2P system calls this to confirm goods received at the store.
    This marks the SOR with goods_received=True for tracking purposes."""
    permission_classes = [IsAuthenticated, IsP2PServiceAccount]
    
    def post(self, request, pk):
        try:
            sor = SOR.objects.get(pk=pk, status__in=['in_progress', 'completed'])
        except SOR.DoesNotExist:
            return Response(
                {'detail': 'SOR not found or not in a valid status for receipt confirmation.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        sir_reference = request.data.get('sir_reference', '')
        
        # Store receipt confirmation in notes/description (or a dedicated field if added later)
        receipt_note = f"\n[P2P Receipt] SIR Ref: {sir_reference} | Confirmed at: {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        if sor.description:
            sor.description += receipt_note
        else:
            sor.description = receipt_note.strip()
        sor.save()
        
        return Response({
            'detail': 'Receipt confirmed successfully.',
            'sor_id': sor.id,
            'sir_reference': sir_reference,
            'status': sor.status,
        })
