from rest_framework import serializers
from vehicles.models import Vehicle, VehicleType
from trips.models import Trip
from maintenance.models import Maintenance, MaintenanceType, MaintenanceProvider
from fuel.models import FuelTransaction, FuelStation
from documents.models import Document, DocumentType
from accounts.models import CustomUser
from sor.models import SOR
from sor.notification import SORNotification
from django.utils import timezone


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'user_type', 'access_type', 'phone_number', 'approval_status', 'hr_designation',
            'hr_department', 'profile_picture',
        ]
        read_only_fields = ['id', 'username', 'user_type', 'access_type', 'approval_status']
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'description', 'category']


class VehicleSerializer(serializers.ModelSerializer):
    vehicle_type = VehicleTypeSerializer(read_only=True)
    vehicle_type_id = serializers.PrimaryKeyRelatedField(
        queryset=VehicleType.objects.all(),
        source='vehicle_type',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'license_plate', 'make', 'model', 'year', 'status',
            'vehicle_type', 'vehicle_type_id', 'color', 'fuel_type',
            'seating_capacity', 'current_odometer', 'vin',
            'owner_name', 'insurance_expiry_date', 'fitness_expiry',
            'pollution_cert_expiry', 'image', 'ownership_type',
            'rate_per_km', 'reimbursement_rate_per_km',
        ]


class TripSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    driver = UserSerializer(read_only=True)
    distance = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = Trip
        fields = [
            'id', 'vehicle', 'driver', 'start_time', 'end_time',
            'start_odometer', 'end_odometer', 'origin', 'destination',
            'purpose', 'notes', 'status', 'entry_type', 'distance', 'duration',
            'gps_tracking_enabled', 'created_at', 'updated_at',
            'start_odometer_image', 'end_odometer_image',
        ]
    
    def get_distance(self, obj):
        return obj.distance_traveled()
    
    def get_duration(self, obj):
        return obj.duration()


class TripCreateSerializer(serializers.ModelSerializer):
    start_odometer_image = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = Trip
        fields = ['vehicle', 'origin', 'purpose', 'start_odometer', 'notes', 'start_odometer_image']
    
    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user:
            ongoing_trips = Trip.objects.filter(
                driver=request.user,
                status='ongoing',
                is_deleted=False
            )
            if ongoing_trips.exists():
                raise serializers.ValidationError(
                    'You already have an active trip. Please end your current trip before starting a new one.'
                )
        return attrs
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['driver'] = request.user
        validated_data['start_time'] = timezone.now()
        validated_data['status'] = 'ongoing'
        validated_data['entry_type'] = 'real_time'
        
        # Auto-enable GPS tracking for personal vehicle staff
        if request.user.user_type == 'personal_vehicle_staff':
            validated_data['gps_tracking_enabled'] = True
        
        return super().create(validated_data)


class TripEndSerializer(serializers.Serializer):
    destination = serializers.CharField(max_length=255)
    end_odometer = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True)
    end_odometer_image = serializers.ImageField(required=False, allow_null=True)
    
    def validate_end_odometer(self, value):
        if self.instance and value <= self.instance.start_odometer:
            raise serializers.ValidationError(
                f'End odometer must be greater than start odometer ({self.instance.start_odometer})'
            )
        return value


class MaintenanceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceType
        fields = ['id', 'name', 'description']


class MaintenanceProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceProvider
        fields = ['id', 'name', 'address', 'phone', 'email']


class MaintenanceSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    vehicle_id = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.all(),
        source='vehicle',
        write_only=True
    )
    maintenance_type = MaintenanceTypeSerializer(read_only=True)
    maintenance_type_id = serializers.PrimaryKeyRelatedField(
        queryset=MaintenanceType.objects.all(),
        source='maintenance_type',
        write_only=True
    )
    provider = MaintenanceProviderSerializer(read_only=True)
    
    class Meta:
        model = Maintenance
        fields = [
            'id', 'vehicle', 'vehicle_id', 'maintenance_type', 'maintenance_type_id',
            'provider', 'date_reported', 'description', 'odometer_reading',
            'status', 'scheduled_date', 'completion_date', 'cost',
            'invoice_image', 'notes',
        ]
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['reported_by'] = request.user
        validated_data['date_reported'] = timezone.now().date()
        return super().create(validated_data)


class FuelStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelStation
        fields = ['id', 'name', 'address', 'station_type', 'latitude', 'longitude']


class FuelTransactionSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    vehicle_id = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.all(),
        source='vehicle',
        write_only=True
    )
    driver = UserSerializer(read_only=True)
    fuel_station = FuelStationSerializer(read_only=True)
    fuel_station_id = serializers.PrimaryKeyRelatedField(
        queryset=FuelStation.objects.all(),
        source='fuel_station',
        write_only=True,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = FuelTransaction
        fields = [
            'id', 'vehicle', 'vehicle_id', 'driver', 'fuel_station', 'fuel_station_id',
            'date', 'fuel_type', 'quantity', 'cost_per_liter', 'total_cost',
            'energy_consumed', 'cost_per_kwh', 'odometer_reading',
            'receipt_image', 'notes', 'created_at',
        ]


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = ['id', 'name', 'description', 'required']


class DocumentSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    vehicle_id = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.all(),
        source='vehicle',
        write_only=True
    )
    document_type = DocumentTypeSerializer(read_only=True)
    document_type_id = serializers.PrimaryKeyRelatedField(
        queryset=DocumentType.objects.all(),
        source='document_type',
        write_only=True
    )
    status = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    issuing_authority = serializers.CharField(required=False, allow_blank=True, default='')
    
    class Meta:
        model = Document
        fields = [
            'id', 'vehicle', 'vehicle_id', 'document_type', 'document_type_id',
            'document_number', 'issue_date', 'expiry_date', 'issuing_authority',
            'file', 'notes', 'status', 'days_until_expiry',
        ]
    
    def get_status(self, obj):
        return obj.status_label()
    
    def get_days_until_expiry(self, obj):
        return obj.days_until_expiry()


# SOR Serializers
class SORSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    driver = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    transport_cost = serializers.SerializerMethodField()
    transport_cost_percentage = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = SOR
        fields = [
            'id', 'goods_value', 'from_location', 'to_location',
            'vehicle', 'driver', 'distance_km', 'status', 'status_display',
            'trip', 'number_of_crates', 'number_of_sac', 'description',
            'created_by', 'created_at', 'updated_at',
            'transport_cost', 'transport_cost_percentage',
        ]
    
    def get_transport_cost(self, obj):
        return obj.transport_cost()
    
    def get_transport_cost_percentage(self, obj):
        return obj.transport_cost_percentage()
    
    def get_status_display(self, obj):
        return obj.get_status_display()


# P2P Integration Serializer - Read-only for external P2P system
class P2PSORSerializer(serializers.ModelSerializer):
    """Lightweight read-only serializer for P2P (Procure to Pay) system integration.
    Exposes SOR data needed for SIR (Security Inward Register) creation."""
    vehicle_number = serializers.CharField(source='vehicle.license_plate', read_only=True)
    vehicle_make_model = serializers.SerializerMethodField()
    driver_name = serializers.SerializerMethodField()
    driver_phone = serializers.CharField(source='driver.phone_number', read_only=True)
    status_display = serializers.SerializerMethodField()
    transport_cost = serializers.SerializerMethodField()

    class Meta:
        model = SOR
        fields = [
            'id', 'goods_value', 'from_location', 'to_location',
            'vehicle_number', 'vehicle_make_model',
            'driver_name', 'driver_phone',
            'distance_km', 'status', 'status_display',
            'number_of_crates', 'number_of_sac', 'description',
            'transport_cost',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields  # Entirely read-only

    def get_vehicle_make_model(self, obj):
        if obj.vehicle:
            return f"{obj.vehicle.make} {obj.vehicle.model}".strip()
        return None

    def get_driver_name(self, obj):
        if obj.driver:
            return obj.driver.get_full_name()
        return None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_transport_cost(self, obj):
        return obj.transport_cost()


class SORNotificationSerializer(serializers.ModelSerializer):
    sor_id = serializers.IntegerField(source='sor.id')
    
    class Meta:
        model = SORNotification
        fields = ['id', 'sor_id', 'message', 'is_read', 'created_at']
