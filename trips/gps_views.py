"""
GPS Tracking API Views for receiving and storing location data
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
import json
import requests
from decimal import Decimal
from .models import Trip
from .gps_models import TripLocation, GPSTrackingSession


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def record_gps_location(request):
    """
    API endpoint to receive GPS coordinates from the browser
    Expected JSON payload:
    {
        "trip_id": 123,
        "latitude": 12.345678,
        "longitude": 78.123456,
        "accuracy": 10.5,
        "speed": 45.2,
        "altitude": 100.0,
        "heading": 180.0,
        "timestamp": "2026-01-08T10:30:00Z",
        "battery_level": 75
    }
    """
    try:
        data = json.loads(request.body)
        
        trip_id = data.get('trip_id')
        if not trip_id:
            return JsonResponse({'error': 'trip_id is required'}, status=400)
        
        # Verify trip exists and user has permission to record GPS
        # Allow: trip driver OR admin/manager/vehicle_manager
        try:
            trip = Trip.objects.get(id=trip_id, status='ongoing')
            # Check permission: must be driver OR management
            allowed_types = ['admin', 'manager', 'vehicle_manager']
            if trip.driver != request.user and request.user.user_type not in allowed_types:
                return JsonResponse({'error': 'Permission denied'}, status=403)
        except Trip.DoesNotExist:
            return JsonResponse({'error': 'Trip not found or not accessible'}, status=404)
        
        # Get or create GPS session
        gps_session, created = GPSTrackingSession.objects.get_or_create(
            trip=trip,
            defaults={'status': 'active'}
        )
        
        # Create location record
        location = TripLocation.objects.create(
            trip=trip,
            latitude=Decimal(str(data.get('latitude'))),
            longitude=Decimal(str(data.get('longitude'))),
            accuracy=float(data.get('accuracy', 0)),
            speed=float(data.get('speed')) if data.get('speed') else None,
            altitude=float(data.get('altitude')) if data.get('altitude') else None,
            heading=float(data.get('heading')) if data.get('heading') else None,
            battery_level=int(data.get('battery_level')) if data.get('battery_level') else None,
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
        
        return JsonResponse({
            'success': True,
            'location_id': location.id,
            'total_points': gps_session.total_points,
            'message': 'Location recorded successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def get_trip_gps_status(request, trip_id):
    """
    Get GPS tracking status for a trip
    """
    try:
        trip = Trip.objects.get(id=trip_id, driver=request.user)
        
        try:
            session = GPSTrackingSession.objects.get(trip=trip)
            return JsonResponse({
                'tracking_enabled': True,
                'total_points': session.total_points,
                'valid_points': session.valid_points,
                'gaps_detected': session.gaps_detected,
                'status': session.status
            })
        except GPSTrackingSession.DoesNotExist:
            return JsonResponse({
                'tracking_enabled': False,
                'message': 'No GPS tracking session found'
            })
            
    except Trip.DoesNotExist:
        return JsonResponse({'error': 'Trip not found'}, status=404)


@require_http_methods(["POST"])
@login_required
def finalize_gps_tracking(request, trip_id):
    """
    Finalize GPS tracking when trip ends - calculate distances and validate
    """
    try:
        trip = Trip.objects.get(id=trip_id, driver=request.user)
        
        try:
            session = GPSTrackingSession.objects.get(trip=trip)
            
            # Mark session as completed
            session.status = 'completed'
            session.ended_at = timezone.now()
            
            # Calculate GPS distance
            try:
                gps_dist = session.calculate_gps_distance()
                session.gps_distance = gps_dist
            except Exception as e:
                print(f"Error calculating GPS distance: {e}")
                session.gps_distance = Decimal('0.00')
            
            # Get odometer distance from request if provided
            try:
                data = json.loads(request.body)
                end_odometer = data.get('end_odometer')
                if end_odometer and trip.start_odometer:
                    session.odometer_distance = Decimal(str(int(end_odometer) - trip.start_odometer))
            except Exception as e:
                print(f"Error getting odometer from request: {e}")
                # If not in request, try from trip object
                if trip.end_odometer is not None and trip.start_odometer is not None:
                    session.odometer_distance = Decimal(str(trip.end_odometer - trip.start_odometer))
            
            # Validate and flag for review if needed
            try:
                session.validate_trip()
            except Exception as e:
                print(f"Error validating trip: {e}")
            
            session.save()
            
            return JsonResponse({
                'success': True,
                'gps_distance': float(session.gps_distance) if session.gps_distance else 0,
                'odometer_distance': float(session.odometer_distance) if session.odometer_distance else 0,
                'variance_percentage': float(session.variance_percentage) if session.variance_percentage else 0,
                'requires_review': session.requires_review,
                'review_reason': session.review_reason
            })
            
        except GPSTrackingSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'No active trip to finalize'}, status=404)
            
    except Trip.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Unexpected error in finalize_gps_tracking: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================
# Google Maps Route API Views
# ============================================

@require_http_methods(["GET"])
@login_required
def get_google_route(request, trip_id):
    """
    Get road-snapped route using Google Directions API
    Returns route polyline that follows actual roads
    """
    try:
        trip = Trip.objects.get(id=trip_id)
        
        # Get GPS locations for this trip
        gps_locations = TripLocation.objects.filter(trip=trip).order_by('timestamp')
        
        if not gps_locations.exists():
            return JsonResponse({
                'success': False,
                'error': 'No GPS data available for this trip'
            }, status=404)
        
        # Get start and end points
        first_point = gps_locations.first()
        last_point = gps_locations.last()
        
        origin = f"{first_point.latitude},{first_point.longitude}"
        destination = f"{last_point.latitude},{last_point.longitude}"
        
        # Build waypoints from intermediate GPS points (sample every nth point to stay under API limits)
        waypoints = []
        total_points = gps_locations.count()
        
        if total_points > 2:
            # Google allows max 25 waypoints, sample accordingly
            step = max(1, (total_points - 2) // 23)
            intermediate_points = list(gps_locations)[1:-1:step][:23]
            waypoints = [f"{p.latitude},{p.longitude}" for p in intermediate_points]
        
        # Call Google Directions API
        api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
        if not api_key:
            return JsonResponse({
                'success': False,
                'error': 'Google Maps API key not configured'
            }, status=500)
        
        params = {
            'origin': origin,
            'destination': destination,
            'key': api_key,
            'mode': 'driving',
        }
        
        if waypoints:
            params['waypoints'] = '|'.join(waypoints)
        
        response = requests.get(
            'https://maps.googleapis.com/maps/api/directions/json',
            params=params,
            timeout=30
        )
        
        data = response.json()
        
        if data.get('status') != 'OK':
            # Fallback to raw GPS polyline if Directions API fails
            raw_points = [
                {'lat': float(p.latitude), 'lng': float(p.longitude)}
                for p in gps_locations
            ]
            return JsonResponse({
                'success': True,
                'fallback': True,
                'message': f"Google Directions API: {data.get('status')}. Using raw GPS points.",
                'route_points': raw_points,
                'distance_km': calculate_gps_distance(gps_locations),
                'trip_info': get_trip_info(trip)
            })
        
        # Extract route information
        route = data['routes'][0]
        legs = route['legs']
        
        # Decode the overview polyline
        overview_polyline = route.get('overview_polyline', {}).get('points', '')
        decoded_points = decode_polyline(overview_polyline) if overview_polyline else []
        
        # Calculate total distance and duration from legs
        total_distance_m = sum(leg['distance']['value'] for leg in legs)
        total_duration_s = sum(leg['duration']['value'] for leg in legs)
        
        return JsonResponse({
            'success': True,
            'fallback': False,
            'route_points': decoded_points,
            'encoded_polyline': overview_polyline,
            'distance_km': round(total_distance_m / 1000, 2),
            'duration_minutes': round(total_duration_s / 60, 1),
            'trip_info': get_trip_info(trip),
            'gps_points': [
                {
                    'lat': float(p.latitude),
                    'lng': float(p.longitude),
                    'timestamp': p.timestamp.isoformat(),
                    'speed': p.speed
                }
                for p in gps_locations
            ]
        })
        
    except Trip.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def decode_polyline(encoded):
    """
    Decode Google's encoded polyline format
    Returns list of {lat, lng} dictionaries
    """
    points = []
    index = 0
    lat = 0
    lng = 0
    
    while index < len(encoded):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        lat += (~(result >> 1) if result & 1 else result >> 1)
        
        # Decode longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        lng += (~(result >> 1) if result & 1 else result >> 1)
        
        points.append({
            'lat': lat / 1e5,
            'lng': lng / 1e5
        })
    
    return points


def calculate_gps_distance(gps_locations):
    """Calculate total distance from GPS points using Haversine formula"""
    import math
    
    total_distance = 0
    locations = list(gps_locations)
    
    for i in range(1, len(locations)):
        lat1 = float(locations[i-1].latitude)
        lon1 = float(locations[i-1].longitude)
        lat2 = float(locations[i].latitude)
        lon2 = float(locations[i].longitude)
        
        # Haversine formula
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        total_distance += 6371 * c  # Earth's radius in km
    
    return round(total_distance, 2)


def get_trip_info(trip):
    """Get trip information for display"""
    return {
        'id': trip.id,
        'driver': trip.driver.get_full_name() if trip.driver else 'N/A',
        'vehicle': f"{trip.vehicle.license_plate} ({trip.vehicle.make} {trip.vehicle.model})" if trip.vehicle else 'N/A',
        'origin': trip.origin,
        'destination': trip.destination or 'N/A',
        'start_time': trip.start_time.isoformat() if trip.start_time else None,
        'end_time': trip.end_time.isoformat() if trip.end_time else None,
        'status': trip.status,
        'odometer_distance': trip.end_odometer - trip.start_odometer if trip.end_odometer and trip.start_odometer else None
    }


class TripGoogleMapView(LoginRequiredMixin, View):
    """
    View to display trip route on Google Maps with road-snapped route
    """
    template_name = 'trips/trip_google_map.html'
    
    def get(self, request, pk):
        trip = get_object_or_404(Trip, id=pk)
        
        # Get GPS locations
        gps_locations = TripLocation.objects.filter(trip=trip).order_by('timestamp')
        
        # Prepare GPS points for JavaScript
        gps_points = [
            {
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'timestamp': p.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'speed': p.speed,
                'accuracy': p.accuracy
            }
            for p in gps_locations
        ]
        
        context = {
            'trip': trip,
            'gps_points': json.dumps(gps_points),
            'gps_count': len(gps_points),
            'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
            'has_gps_data': len(gps_points) > 0
        }
        
        return render(request, self.template_name, context)


@require_http_methods(["GET"])
@login_required
def get_trip_locations(request, trip_id):
    """
    API endpoint to get GPS locations for a specific trip.
    Used by the dashboard Vehicle Location modal.
    Accessible by: admin, manager, vehicle_manager, or the trip driver
    """
    try:
        trip = get_object_or_404(Trip, id=trip_id)
        
        # Check permission: must be admin/manager/vehicle_manager or the driver
        user = request.user
        allowed_types = ['admin', 'manager', 'vehicle_manager']
        if user.user_type not in allowed_types and trip.driver != user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Get GPS locations for the trip
        locations = TripLocation.objects.filter(trip=trip).order_by('timestamp')
        
        location_data = [
            {
                'latitude': float(loc.latitude),
                'longitude': float(loc.longitude),
                'accuracy': loc.accuracy,
                'speed': loc.speed,
                'timestamp': loc.timestamp.isoformat() if loc.timestamp else None
            }
            for loc in locations
        ]
        
        return JsonResponse(location_data, safe=False)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
