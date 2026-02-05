from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Sum, Count, F
from datetime import timedelta

from vehicles.models import Vehicle, VehicleType
from trips.models import Trip
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
    pagination_class = None  # Return all vehicles without pagination
    
    def get_queryset(self):
        user = self.request.user
        is_admin = user.user_type in ['admin', 'manager', 'vehicle_manager']
        is_personal_vehicle_staff = user.user_type == 'personal_vehicle_staff'
        
        if is_admin:
            # Admins see all vehicles
            queryset = Vehicle.objects.all()
        elif is_personal_vehicle_staff:
            # Personal vehicle staff see only their own vehicles
            queryset = Vehicle.objects.filter(ownership_type='personal', owned_by=user)
        else:
            # Drivers see available company vehicles only
            queryset = Vehicle.objects.filter(ownership_type='company')
        
        # Apply status filter if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('vehicle_type')


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


class EndTripView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, is_deleted=False)
        except Trip.DoesNotExist:
            return Response({'detail': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
        
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
        queryset = Document.objects.all().select_related('vehicle', 'document_type')
        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        return queryset


class DocumentTypeListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentTypeSerializer
    queryset = DocumentType.objects.all()


class ExpiringDocumentsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer
    
    def get_queryset(self):
        today = timezone.now().date()
        thirty_days_later = today + timedelta(days=30)
        return Document.objects.filter(
            expiry_date__range=[today, thirty_days_later]
        ).select_related('vehicle', 'document_type').order_by('expiry_date')


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
        
        if user.user_type in ['admin', 'manager', 'vehicle_manager']:
            queryset = SOR.objects.all()
        elif user.user_type == 'driver':
            queryset = SOR.objects.filter(driver=user)
        else:
            queryset = SOR.objects.filter(created_by=user)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('vehicle', 'driver', 'created_by').order_by('-created_at')


class SORDetailView(generics.RetrieveAPIView):
    """Get details of a specific SOR"""
    permission_classes = [IsAuthenticated]
    serializer_class = SORSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type in ['admin', 'manager', 'vehicle_manager']:
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
