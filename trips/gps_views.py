"""
GPS Tracking API Views for receiving and storing location data
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import json
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
        
        # Verify trip exists and belongs to current user
        try:
            trip = Trip.objects.get(id=trip_id, driver=request.user, status='ongoing')
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
