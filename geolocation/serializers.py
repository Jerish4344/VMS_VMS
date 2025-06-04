from rest_framework import serializers
from .models import LocationLog

class LocationLogSerializer(serializers.ModelSerializer):
    """Serializer for LocationLog model."""
    
    class Meta:
        model = LocationLog
        fields = ['id', 'trip', 'latitude', 'longitude', 'altitude', 'speed', 'timestamp']
        read_only_fields = ['timestamp']
    
    def validate(self, data):
        """
        Validate that the location data is reasonable.
        """
        # Validate latitude range
        if data.get('latitude') and (data['latitude'] < -90 or data['latitude'] > 90):
            raise serializers.ValidationError({"latitude": "Latitude must be between -90 and 90 degrees."})
        
        # Validate longitude range
        if data.get('longitude') and (data['longitude'] < -180 or data['longitude'] > 180):
            raise serializers.ValidationError({"longitude": "Longitude must be between -180 and 180 degrees."})
        
        # Validate speed (if provided)
        if data.get('speed') and data['speed'] < 0:
            raise serializers.ValidationError({"speed": "Speed cannot be negative."})
        
        return data
    
    def create(self, validated_data):
        """
        Create a new location log.
        """
        return LocationLog.objects.create(**validated_data)