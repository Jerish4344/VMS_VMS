import time
import requests
import json
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from geolocation.models import AiroTrackDevice, VehicleLocation, LocationHistory
from vehicles.models import Vehicle
from colorama import init, Fore, Style
import urllib3

# Initialize colorama for cross-platform colored terminal output
init()

class Command(BaseCommand):
    help = 'Test AiroTrack API connectivity and functionality'
    
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
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-devices',
            action='store_true',
            dest='create_devices',
            help='Create sample devices for testing',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            dest='verbose',
            help='Show detailed output',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=10,
            help='API request timeout in seconds',
        )
    
    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.timeout = options['timeout']
        self.create_devices = options['create_devices']
        self.auth = (self.USERNAME, self.PASSWORD)
        self.session = requests.Session()
        self.session.auth = self.auth
        # ------------------------------------------------------------------ #
        # Disable SSL verification because the AiroTrack server presents an  #
        # un-trusted certificate in many environments. This mirrors the same #
        # behaviour implemented in `AiroTrackAPI` so that the management     #
        # command does not fail with an `SSLError` during tests.             #
        # NOTE: Disabling verification weakens transport security – use a    #
        # proper CA bundle in production and remove this override.           #
        # ------------------------------------------------------------------ #
        self.session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        self.results = {
            'connectivity': False,
            'devices': False,
            'positions': False,
            'created_devices': 0,
            'errors': []
        }
        
        self.style.SUCCESS = lambda x: f"{Fore.GREEN}{x}{Style.RESET_ALL}"
        self.style.WARNING = lambda x: f"{Fore.YELLOW}{x}{Style.RESET_ALL}"
        self.style.ERROR = lambda x: f"{Fore.RED}{x}{Style.RESET_ALL}"
        self.style.NOTICE = lambda x: f"{Fore.CYAN}{x}{Style.RESET_ALL}"
        
        self.stdout.write(self.style.NOTICE("\n=== AiroTrack API Test ===\n"))
        self.stdout.write(self.style.WARNING(
            "⚠ SSL certificate verification is DISABLED for these test "
            "requests. Use a valid certificate bundle in production.\n"
        ))
        
        try:
            # Test 1: Basic connectivity
            self.test_connectivity()
            
            # Test 2: Device information
            self.test_device_info()
            
            # Test 3: Position data
            self.test_position_data()
            
            # Create sample devices if requested
            if self.create_devices:
                self.create_sample_devices()
            
            # Display summary
            self.display_summary()
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.ERROR("\nTest interrupted by user."))
            return
    
    def _make_request(self, endpoint, params=None, method="GET", data=None):
        """Make an HTTP request to the AiroTrack API."""
        url = f"{self.BASE_URL}{endpoint}"
        request_params = self.DEFAULT_PARAMS.copy()
        
        if params:
            request_params.update(params)
        
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=request_params, timeout=self.timeout)
            elif method.upper() == "POST":
                response = self.session.post(url, params=request_params, json=data, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            elapsed_time = time.time() - start_time
            
            if self.verbose:
                self.stdout.write(f"  Request URL: {response.url}")
                self.stdout.write(f"  Status Code: {response.status_code}")
                self.stdout.write(f"  Response Time: {elapsed_time:.2f}s")
            
            response.raise_for_status()
            return response.json(), elapsed_time
            
        except requests.exceptions.RequestException as e:
            elapsed_time = time.time() - start_time
            self.results['errors'].append(str(e))
            raise CommandError(f"API request failed: {str(e)}")
    
    def test_connectivity(self):
        """Test basic connectivity to the AiroTrack API."""
        self.stdout.write("1. Testing API connectivity...")
        
        try:
            # Just hit the base endpoint to check connectivity
            response, elapsed_time = self._make_request(self.DEVICES_ENDPOINT, {"limit": 1})
            
            self.results['connectivity'] = True
            self.stdout.write(self.style.SUCCESS(f"  ✓ Connected to AiroTrack API ({elapsed_time:.2f}s)"))
            
            if self.verbose and response:
                self.stdout.write("  Response preview:")
                self.stdout.write(json.dumps(response[:2] if isinstance(response, list) else response, indent=2)[:500] + "...")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Failed to connect to AiroTrack API: {str(e)}"))
            self.results['connectivity'] = False
            self.results['errors'].append(str(e))
    
    def test_device_info(self):
        """Test fetching device information from the AiroTrack API."""
        self.stdout.write("\n2. Testing device information retrieval...")
        
        if not self.results['connectivity']:
            self.stdout.write(self.style.WARNING("  ⚠ Skipping test due to connectivity failure"))
            return
        
        try:
            # Get all devices
            devices, elapsed_time = self._make_request(self.DEVICES_ENDPOINT)
            
            if isinstance(devices, list):
                self.results['devices'] = True
                device_count = len(devices)
                self.stdout.write(self.style.SUCCESS(f"  ✓ Retrieved {device_count} devices ({elapsed_time:.2f}s)"))
                
                if device_count > 0 and self.verbose:
                    self.stdout.write("  Device sample:")
                    for i, device in enumerate(devices[:3]):
                        self.stdout.write(f"  - Device {i+1}: ID={device.get('id')}, Name={device.get('name')}")
                    
                    if device_count > 3:
                        self.stdout.write(f"  ... and {device_count - 3} more")
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ Unexpected response format: {type(devices)}"))
                self.results['devices'] = False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Failed to retrieve device information: {str(e)}"))
            self.results['devices'] = False
            self.results['errors'].append(str(e))
    
    def test_position_data(self):
        """Test fetching position data from the AiroTrack API."""
        self.stdout.write("\n3. Testing position data retrieval...")
        
        if not self.results['connectivity']:
            self.stdout.write(self.style.WARNING("  ⚠ Skipping test due to connectivity failure"))
            return
        
        try:
            # Get positions for all devices
            positions, elapsed_time = self._make_request(self.POSITIONS_ENDPOINT)
            
            if isinstance(positions, list):
                self.results['positions'] = True
                position_count = len(positions)
                self.stdout.write(self.style.SUCCESS(f"  ✓ Retrieved {position_count} position records ({elapsed_time:.2f}s)"))
                
                if position_count > 0 and self.verbose:
                    self.stdout.write("  Position sample:")
                    for i, position in enumerate(positions[:3]):
                        device_id = position.get('deviceId')
                        lat = position.get('latitude')
                        lng = position.get('longitude')
                        speed = position.get('speed')
                        time = position.get('deviceTime')
                        self.stdout.write(f"  - Position {i+1}: Device={device_id}, Coords=({lat}, {lng}), Speed={speed}, Time={time}")
                    
                    if position_count > 3:
                        self.stdout.write(f"  ... and {position_count - 3} more")
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ Unexpected response format: {type(positions)}"))
                self.results['positions'] = False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Failed to retrieve position data: {str(e)}"))
            self.results['positions'] = False
            self.results['errors'].append(str(e))
    
    @transaction.atomic
    def create_sample_devices(self):
        """Create sample devices for testing."""
        self.stdout.write("\n4. Creating sample devices...")
        
        if not self.results['connectivity'] or not self.results['devices']:
            self.stdout.write(self.style.WARNING("  ⚠ Skipping device creation due to API test failures"))
            return
        
        try:
            # Get devices from API
            devices, _ = self._make_request(self.DEVICES_ENDPOINT)
            
            if not isinstance(devices, list) or len(devices) == 0:
                self.stdout.write(self.style.WARNING("  ⚠ No devices found in API to create samples from"))
                return
            
            # Get vehicles without devices
            unassigned_vehicles = Vehicle.objects.filter(
                airotrack_device__isnull=True,
                gps_fitted='yes'
            )
            
            if not unassigned_vehicles.exists():
                self.stdout.write(self.style.WARNING("  ⚠ No unassigned vehicles with GPS found in database"))
                return
            
            # Create devices from API data
            created_count = 0
            for i, device_data in enumerate(devices[:min(len(devices), 5)]):
                device_id = device_data.get('id')
                if not device_id:
                    continue
                
                # Check if device already exists
                if AiroTrackDevice.objects.filter(device_id=device_id).exists():
                    if self.verbose:
                        self.stdout.write(f"  - Device {device_id} already exists, skipping")
                    continue
                
                # Create new device
                device = AiroTrackDevice(
                    device_id=device_id,
                    name=device_data.get('name', f"Test Device {i+1}"),
                    status='unknown',
                    last_update=timezone.now()
                )
                
                # Assign to vehicle if available
                if i < unassigned_vehicles.count():
                    device.vehicle = unassigned_vehicles[i]
                    
                device.save()
                created_count += 1
                
                self.stdout.write(self.style.SUCCESS(f"  ✓ Created device {device.name} (ID: {device.device_id})"))
                
                # Create sample location data if we have position data
                if self.results['positions']:
                    try:
                        # Get positions for this device
                        device_positions, _ = self._make_request(
                            self.POSITIONS_ENDPOINT, 
                            {"deviceId": device_id, "limit": 1}
                        )
                        
                        if isinstance(device_positions, list) and len(device_positions) > 0:
                            position = device_positions[0]
                            
                            # Parse device time
                            try:
                                device_time_str = position.get('deviceTime')
                                device_time = datetime.fromisoformat(device_time_str.replace('Z', '+00:00'))
                            except (ValueError, TypeError):
                                device_time = timezone.now()
                            
                            # Create location
                            if device.vehicle:
                                location = VehicleLocation.objects.create(
                                    vehicle=device.vehicle,
                                    device=device,
                                    latitude=position.get('latitude', 0),
                                    longitude=position.get('longitude', 0),
                                    altitude=position.get('altitude'),
                                    speed=position.get('speed'),
                                    course=position.get('course'),
                                    device_time=device_time,
                                    server_time=timezone.now(),
                                    fix_time=device_time,
                                    valid=position.get('valid', True),
                                    address=position.get('address'),
                                    ignition=position.get('ignition', False),
                                    raw_data=position
                                )
                                
                                self.stdout.write(self.style.SUCCESS(f"  ✓ Created location data for device {device.name}"))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"  ⚠ Failed to create location data: {str(e)}"))
            
            self.results['created_devices'] = created_count
            
            if created_count == 0:
                self.stdout.write(self.style.WARNING("  ⚠ No new devices created"))
            else:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Created {created_count} sample devices"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Failed to create sample devices: {str(e)}"))
            self.results['errors'].append(str(e))
    
    def display_summary(self):
        """Display a summary of test results."""
        self.stdout.write("\n=== Test Summary ===")
        
        # Connectivity
        if self.results['connectivity']:
            self.stdout.write(self.style.SUCCESS("✓ API Connectivity: Success"))
        else:
            self.stdout.write(self.style.ERROR("✗ API Connectivity: Failed"))
        
        # Device information
        if self.results['devices']:
            self.stdout.write(self.style.SUCCESS("✓ Device Information: Success"))
        else:
            self.stdout.write(self.style.ERROR("✗ Device Information: Failed"))
        
        # Position data
        if self.results['positions']:
            self.stdout.write(self.style.SUCCESS("✓ Position Data: Success"))
        else:
            self.stdout.write(self.style.ERROR("✗ Position Data: Failed"))
        
        # Created devices
        if self.create_devices:
            if self.results['created_devices'] > 0:
                self.stdout.write(self.style.SUCCESS(f"✓ Created Devices: {self.results['created_devices']}"))
            else:
                self.stdout.write(self.style.WARNING("⚠ Created Devices: None"))
        
        # Errors
        if self.results['errors']:
            self.stdout.write(self.style.ERROR("\nErrors encountered:"))
            for i, error in enumerate(self.results['errors']):
                self.stdout.write(self.style.ERROR(f"{i+1}. {error}"))
        
        # Overall result
        if self.results['connectivity'] and self.results['devices'] and self.results['positions']:
            self.stdout.write(self.style.SUCCESS("\n✅ All tests passed successfully!"))
            self.stdout.write(self.style.NOTICE("\nYou can now use the AiroTrack integration in your application."))
        else:
            self.stdout.write(self.style.ERROR("\n❌ Some tests failed. Please check the errors above."))
            
        self.stdout.write("\n")
