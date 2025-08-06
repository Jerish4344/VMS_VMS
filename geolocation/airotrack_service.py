import requests
import logging
import time
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from .models import AiroTrackDevice, VehicleLocation, LocationHistory
from vehicles.models import Vehicle
import urllib3

# Configure logging
logger = logging.getLogger(__name__)

class AiroTrackAPI:
    """
    Service class to interact with the AiroTrack API for vehicle tracking.
    
    This class handles all API interactions, data processing, and database updates
    for the AiroTrack GPS tracking system.
    """
    
    # API Configuration
    BASE_URL = "https://login.airotrack.in:8082/api"
    USERNAME = "9020738318"
    PASSWORD = "123456"
    
    # Endpoint paths
    POSITIONS_ENDPOINT = "/positions"
    DEVICES_ENDPOINT = "/devices"
    
    # Request parameters
    DEFAULT_PARAMS = {
        "status": "ALL",
        "isAddressRequired": "false",
        "limit": 80,
        "offset": 0
    }
    
    def __init__(self):
        """Initialize the API service with authentication credentials."""
        self.auth = (self.USERNAME, self.PASSWORD)
        self.session = requests.Session()
        self.session.auth = self.auth
        # Disable SSL verification because the AiroTrack server currently
        # presents a certificate that cannot be verified by the default
        # certificate authorities bundled with Python.  NOTE: Disabling SSL
        # verification reduces transport-level security and should only be
        # used when you fully trust the remote host (e.g., internal network)
        # or have no other option.  A proper solution is to install the
        # correct CA certificate and re-enable verification.
        self.session.verify = False

        # Silence the urllib3 warning about insecure HTTPS requests so logs
        # don’t get flooded.  We still keep our own explicit warning.
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        logger.warning(
            "SSL certificate verification is DISABLED for AiroTrack API "
            "requests.  This should only be used in development or when the "
            "server’s certificate cannot be validated.  Consider supplying a "
            "valid CA bundle and removing this override for production."
        )
        self.last_sync_time = None
    
    def _make_request(self, endpoint, params=None, method="GET", data=None, timeout=10):
        """
        Make an HTTP request to the AiroTrack API.
        
        Args:
            endpoint (str): API endpoint path
            params (dict, optional): Query parameters
            method (str, optional): HTTP method (GET, POST, etc.)
            data (dict, optional): Request body for POST requests
            timeout (int, optional): Request timeout in seconds
            
        Returns:
            dict: JSON response from the API
            
        Raises:
            requests.RequestException: If the request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        request_params = self.DEFAULT_PARAMS.copy()
        
        if params:
            request_params.update(params)
            
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=request_params, timeout=timeout)
            elif method.upper() == "POST":
                response = self.session.post(url, params=request_params, json=data, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"AiroTrack API request failed: {str(e)}")
            # Re-raise with more context
            raise requests.RequestException(f"AiroTrack API request failed: {str(e)}")
    
    def get_positions(self, device_ids=None, from_time=None, to_time=None):
        """
        Get positions of vehicles from the AiroTrack API.
        
        Args:
            device_ids (list, optional): List of device IDs to filter
            from_time (datetime, optional): Start time for position data
            to_time (datetime, optional): End time for position data
            
        Returns:
            list: List of position data dictionaries
        """
        # The AiroTrack API **does not** accept a comma-separated list of device
        # IDs.  Passing such a parameter currently results in a 404.  Therefore
        # we have to:
        #   1.  Omit the deviceId parameter completely to get *all* positions, or
        #   2.  Make individual requests per device and merge the results.
        #
        # Making separate requests is safer because it avoids fetching positions
        # for devices we do not care about (potentially large payloads).  But
        # when `device_ids` is None we keep the previous behaviour (all
        # positions).
        #
        # This method now:
        #   • Returns a combined list for multiple IDs
        #   • Gracefully degrades on per-device request failure
        params_base = {}

        # Time filters are common for all requests
        if from_time:
            params_base["from"] = from_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if to_time:
            params_base["to"] = to_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        all_positions: list = []

        # No device filter – single request
        if not device_ids:
            try:
                all_positions = self._make_request(self.POSITIONS_ENDPOINT, params_base)
            except requests.RequestException as exc:
                logger.error(f"Failed to get positions (all devices): {exc}")
            return all_positions

        # Normalise to list
        if not isinstance(device_ids, (list, tuple, set)):
            device_ids = [device_ids]

        # Fetch each device separately
        for dev_id in device_ids:
            try:
                params = params_base.copy()
                params["deviceId"] = str(dev_id)
                positions = self._make_request(self.POSITIONS_ENDPOINT, params)
                if isinstance(positions, list):
                    all_positions.extend(positions)
                else:
                    logger.debug(
                        "Unexpected response type for device %s: %s",
                        dev_id,
                        type(positions).__name__,
                    )
            except requests.RequestException as exc:
                logger.error("Failed to fetch positions for device %s: %s", dev_id, exc)

        return all_positions
    
    def get_devices(self):
        """
        Get all devices registered with AiroTrack.
        
        Returns:
            list: List of device data dictionaries
        """
        try:
            response = self._make_request(self.DEVICES_ENDPOINT)
            return response
        except requests.RequestException as e:
            logger.error(f"Failed to get devices: {str(e)}")
            return []
    
    def get_device_info(self, device_id):
        """
        Get information about a specific device.
        
        Args:
            device_id (str): Device ID to query
            
        Returns:
            dict: Device information or None if not found
        """
        try:
            response = self._make_request(f"{self.DEVICES_ENDPOINT}/{device_id}")
            return response
        except requests.RequestException as e:
            logger.error(f"Failed to get device info for {device_id}: {str(e)}")
            return None
    
    def _parse_position_data(self, position_data):
        """
        Parse position data from the API response.
        
        Args:
            position_data (dict): Raw position data from API
            
        Returns:
            dict: Parsed and validated position data
        """
        try:
            # Extract and validate required fields
            device_id = position_data.get('deviceId')
            if not device_id:
                logger.warning("Position data missing deviceId")
                return None
                
            # Parse timestamps
            device_time_str = position_data.get('deviceTime')
            if not device_time_str:
                logger.warning(f"Position data for device {device_id} missing deviceTime")
                return None
                
            try:
                # Parse ISO format timestamp
                device_time = datetime.fromisoformat(device_time_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                logger.warning(f"Invalid deviceTime format for device {device_id}: {device_time_str}")
                return None
            
            # Extract location data
            latitude = position_data.get('latitude')
            longitude = position_data.get('longitude')
            
            if latitude is None or longitude is None:
                logger.warning(f"Position data for device {device_id} missing coordinates")
                return None
            
            # Create parsed data dictionary with all available fields
            parsed_data = {
                'device_id': device_id,
                'latitude': latitude,
                'longitude': longitude,
                'altitude': position_data.get('altitude'),
                'speed': position_data.get('speed'),
                'course': position_data.get('course'),
                'device_time': device_time,
                'server_time': timezone.now(),
                'fix_time': datetime.fromisoformat(position_data.get('fixTime').replace('Z', '+00:00')) if position_data.get('fixTime') else None,
                'valid': position_data.get('valid', True),
                'address': position_data.get('address'),
                'ignition': position_data.get('ignition', False),
                'battery_level': position_data.get('batteryLevel'),
                'raw_data': position_data
            }
            
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parsing position data: {str(e)}")
            return None
    
    @transaction.atomic
    def update_device_database(self):
        """
        Update the local database with devices from AiroTrack.
        
        Returns:
            tuple: (created_count, updated_count, error_count)
        """
        created_count = 0
        updated_count = 0
        error_count = 0
        
        try:
            devices = self.get_devices()
            
            if not devices:
                logger.warning("No devices returned from AiroTrack API")
                return (0, 0, 0)
            
            for device_data in devices:
                try:
                    device_id = device_data.get('id')
                    if not device_id:
                        logger.warning("Device data missing ID")
                        error_count += 1
                        continue
                    
                    device, created = AiroTrackDevice.objects.update_or_create(
                        device_id=device_id,
                        defaults={
                            'name': device_data.get('name', f"Device {device_id}"),
                            'status': 'online' if device_data.get('status') == 'online' else 'offline',
                            'last_update': timezone.now()
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                    # Try to associate with a vehicle if not already
                    if not device.vehicle:
                        # Look for a vehicle with matching identifiers
                        # This is a simplistic approach - you might need a more sophisticated matching logic
                        vehicles = Vehicle.objects.filter(
                            gps_fitted='yes',
                            gps_name__icontains='airotrack'
                        )
                        
                        if vehicles.exists():
                            # Take the first unassigned vehicle
                            for vehicle in vehicles:
                                if not hasattr(vehicle, 'airotrack_device'):
                                    device.vehicle = vehicle
                                    device.save()
                                    logger.info(f"Associated device {device_id} with vehicle {vehicle}")
                                    break
                    
                except Exception as e:
                    logger.error(f"Error processing device {device_data.get('id', 'unknown')}: {str(e)}")
                    error_count += 1
            
            return (created_count, updated_count, error_count)
            
        except Exception as e:
            logger.error(f"Error updating device database: {str(e)}")
            return (created_count, updated_count, error_count + 1)
    
    @transaction.atomic
    def update_vehicle_locations(self):
        """
        Update current vehicle locations from AiroTrack API.
        
        Returns:
            tuple: (updated_count, error_count)
        """
        updated_count = 0
        error_count = 0
        
        try:
            # Get all devices from our database
            devices = AiroTrackDevice.objects.all()
            device_ids = [device.device_id for device in devices]
            
            if not device_ids:
                logger.warning("No devices found in database to update locations")
                return (0, 0)
            
            # Get positions for all devices
            positions = self.get_positions(device_ids=device_ids)
            
            if not positions:
                logger.warning("No positions returned from AiroTrack API")
                return (0, 0)
            
            for position_data in positions:
                try:
                    parsed_data = self._parse_position_data(position_data)
                    
                    if not parsed_data:
                        error_count += 1
                        continue
                    
                    device_id = parsed_data['device_id']
                    
                    try:
                        device = AiroTrackDevice.objects.get(device_id=device_id)
                    except AiroTrackDevice.DoesNotExist:
                        logger.warning(f"Device {device_id} not found in database")
                        error_count += 1
                        continue
                    
                    if not device.vehicle:
                        logger.warning(f"Device {device_id} not associated with any vehicle")
                        error_count += 1
                        continue
                    
                    # Update device status
                    device.update_status('online')
                    
                    # Update or create current location
                    location, created = VehicleLocation.objects.update_or_create(
                        vehicle=device.vehicle,
                        device=device,
                        defaults={
                            'latitude': parsed_data['latitude'],
                            'longitude': parsed_data['longitude'],
                            'altitude': parsed_data['altitude'],
                            'speed': parsed_data['speed'],
                            'course': parsed_data['course'],
                            'device_time': parsed_data['device_time'],
                            'server_time': parsed_data['server_time'],
                            'fix_time': parsed_data['fix_time'],
                            'valid': parsed_data['valid'],
                            'address': parsed_data['address'],
                            'ignition': parsed_data['ignition'],
                            'battery_level': parsed_data.get('battery_level'),
                            'raw_data': parsed_data['raw_data']
                        }
                    )
                    
                    # Also create a history entry
                    LocationHistory.objects.create(
                        vehicle=device.vehicle,
                        device=device,
                        latitude=parsed_data['latitude'],
                        longitude=parsed_data['longitude'],
                        altitude=parsed_data['altitude'],
                        speed=parsed_data['speed'],
                        course=parsed_data['course'],
                        device_time=parsed_data['device_time'],
                        valid=parsed_data['valid'],
                        address=parsed_data['address'],
                        ignition=parsed_data['ignition']
                    )
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing position for device {position_data.get('deviceId', 'unknown')}: {str(e)}")
                    error_count += 1
            
            # Update last sync time
            self.last_sync_time = timezone.now()
            
            return (updated_count, error_count)
            
        except Exception as e:
            logger.error(f"Error updating vehicle locations: {str(e)}")
            return (updated_count, error_count + 1)
    
    def sync_all_data(self):
        """
        Synchronize all data from AiroTrack API.
        
        This method updates both devices and vehicle locations.
        
        Returns:
            dict: Summary of sync operation
        """
        start_time = time.time()
        
        # First update devices
        devices_created, devices_updated, devices_error = self.update_device_database()
        
        # Then update locations
        locations_updated, locations_error = self.update_vehicle_locations()
        
        elapsed_time = time.time() - start_time
        
        sync_summary = {
            'timestamp': timezone.now(),
            'devices_created': devices_created,
            'devices_updated': devices_updated,
            'devices_error': devices_error,
            'locations_updated': locations_updated,
            'locations_error': locations_error,
            'elapsed_time': elapsed_time
        }
        
        logger.info(f"AiroTrack sync completed: {sync_summary}")
        
        return sync_summary
    
    def get_vehicle_history(self, vehicle, start_time=None, end_time=None):
        """
        Get location history for a specific vehicle.
        
        Args:
            vehicle (Vehicle): Vehicle object
            start_time (datetime, optional): Start time for history
            end_time (datetime, optional): End time for history
            
        Returns:
            list: List of location history objects
        """
        try:
            if not hasattr(vehicle, 'airotrack_device'):
                logger.warning(f"Vehicle {vehicle} has no associated AiroTrack device")
                return []
            
            device = vehicle.airotrack_device
            
            # Default to last 24 hours if no time range specified
            if not start_time:
                start_time = timezone.now() - timedelta(days=1)
            
            if not end_time:
                end_time = timezone.now()
            
            # First try to get from local database
            history = LocationHistory.objects.filter(
                vehicle=vehicle,
                device_time__gte=start_time,
                device_time__lte=end_time
            ).order_by('device_time')
            
            # If we have sufficient data, return it
            if history.count() > 10:
                return history
            
            # Otherwise, fetch from API and store in database
            positions = self.get_positions(
                device_ids=device.device_id,
                from_time=start_time,
                to_time=end_time
            )
            
            if not positions:
                return history  # Return what we have locally
            
            # Process and store new history data
            with transaction.atomic():
                for position_data in positions:
                    parsed_data = self._parse_position_data(position_data)
                    
                    if not parsed_data:
                        continue
                    
                    # Check if we already have this entry
                    existing = LocationHistory.objects.filter(
                        vehicle=vehicle,
                        device=device,
                        device_time=parsed_data['device_time']
                    ).exists()
                    
                    if not existing:
                        LocationHistory.objects.create(
                            vehicle=vehicle,
                            device=device,
                            latitude=parsed_data['latitude'],
                            longitude=parsed_data['longitude'],
                            altitude=parsed_data['altitude'],
                            speed=parsed_data['speed'],
                            course=parsed_data['course'],
                            device_time=parsed_data['device_time'],
                            valid=parsed_data['valid'],
                            address=parsed_data['address'],
                            ignition=parsed_data['ignition']
                        )
            
            # Get the updated history
            return LocationHistory.objects.filter(
                vehicle=vehicle,
                device_time__gte=start_time,
                device_time__lte=end_time
            ).order_by('device_time')
            
        except Exception as e:
            logger.error(f"Error getting vehicle history for {vehicle}: {str(e)}")
            return []
