# accounts/backends.py - Fixed to extract name from StyleHR username field
import requests
import logging
from django.contrib.auth.backends import BaseBackend, ModelBackend
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()
logger = logging.getLogger(__name__)

class StyleHRAuthBackend(BaseBackend):
    """
    StyleHR authentication backend for drivers only
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        
        try:
            # Authenticate with StyleHR system
            hr_user_data = self._authenticate_with_stylehr(username, password)
            
            if not hr_user_data:
                logger.warning(f"StyleHR authentication failed for user: {username}")
                return None
            
            # Log the actual HR data received for debugging
            logger.info(f"StyleHR data received for {username}: {list(hr_user_data.keys())}")
            
            # Check if user is a driver in HR system
            if not self._is_driver(hr_user_data):
                logger.warning(f"User {username} is not a driver in StyleHR system")
                return None
            
            # Get or create driver user
            user = self._get_or_create_driver(hr_user_data, login_username=username)
            
            # Update user information from HR system
            self._update_user_from_hr_data(user, hr_user_data)
            
            # Update HR authentication timestamp
            user.hr_authenticated_at = timezone.now()
            user.save()
            
            logger.info(f"StyleHR authentication successful for driver: {username}")
            return user
            
        except Exception as e:
            logger.error(f"StyleHR authentication error for {username}: {str(e)}")
            return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
    
    def _authenticate_with_stylehr(self, username, password):
        """Authenticate with StyleHR API"""
        try:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                'email': username,
                'password': password
            }
            
            response = requests.post(
                'https://stylehr.in/api/login/',
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    logger.info(f"StyleHR raw response for {username}: {response_data}")
                    
                    if isinstance(response_data, dict) and self._is_valid_response(response_data):
                        return response_data
                except json.JSONDecodeError:
                    pass
            
            return None
            
        except requests.RequestException as e:
            logger.error(f"StyleHR API request failed: {str(e)}")
            return None
    
    def _is_valid_response(self, response_data):
        """Check if response contains valid employee data"""
        # Check for common employee data fields
        required_fields = ['employee_id', 'email', 'id', 'user_id', 'username']
        
        # At least one required field should be present
        has_required = any(field in response_data for field in required_fields)
        
        # Should not be an error message
        is_not_error = 'Invalid username/password' not in str(response_data).lower()
        
        return has_required and is_not_error
    
    def _is_driver(self, hr_user_data):
        """
        Check if user can be allowed to drive vehicles
        Now allows ANY employee from StyleHR (not just job title "driver")
        """
        # Since any employee might need to drive, we'll be more inclusive
        # Check if user has basic employee information
        has_employee_data = any([
            hr_user_data.get('employee_id'),
            hr_user_data.get('id'),
            hr_user_data.get('user_id'),
            hr_user_data.get('email'),
            hr_user_data.get('username')  # StyleHR puts name here
        ])
        
        if not has_employee_data:
            logger.info(f"User lacks basic employee data: {hr_user_data}")
            return False
        
        # Allow all employees with valid data
        logger.info(f"Employee approved for potential driving access: {hr_user_data.get('employee_id', hr_user_data.get('id', 'Unknown'))}")
        return True
    
    def _get_or_create_driver(self, hr_user_data, login_username):
        """Get or create employee user (can be any employee, not just drivers)"""
        # Use the login username (employee ID) as the Django username
        # The actual employee name is in hr_data['username']
        employee_id = login_username  # This is what they logged in with (10051)
        email = hr_user_data.get('email', '')
        
        # Try to find existing user by employee ID
        user = None
        try:
            user = User.objects.get(username=str(employee_id))
        except User.DoesNotExist:
            pass
        
        # Try to find by email if not found by username
        if not user and email:
            try:
                user = User.objects.get(email=email)
                # Update username to employee ID if found by email
                user.username = str(employee_id)
                user.save()
            except User.DoesNotExist:
                pass
        
        # Create new user if not found
        if not user:
            user_type = self._determine_user_type(hr_user_data)
            
            user = User.objects.create_user(
                username=str(employee_id),  # Use employee ID as username
                email=email,
                user_type=user_type,
                is_active=True,  # Active but needs approval
                approval_status='pending'  # Needs approval to access system
            )
            logger.info(f"Created new employee account for {employee_id} ({user_type}) - Pending approval")
        
        return user
    
    def _determine_user_type(self, hr_user_data):
        """
        Determine user type based on HR data
        Most employees will be 'driver' for vehicle access, but some might be managers
        """
        # For now, default everyone to 'driver' for vehicle access
        # You can enhance this logic later based on HR data
        return 'driver'
    
    def _update_user_from_hr_data(self, user, hr_user_data):
        """Update user data from StyleHR - FIXED for StyleHR's specific format"""
        updated = False
        
        # Store complete HR data
        user.hr_data = hr_user_data
        
        # Store employee ID 
        employee_id = (
            hr_user_data.get('employee_id') or 
            hr_user_data.get('emp_id') or 
            hr_user_data.get('id') or 
            user.username  # Fallback to Django username
        )
        user.hr_employee_id = str(employee_id)
        updated = True
        
        # Extract department and role info
        user.hr_department = hr_user_data.get('department', '')
        user.hr_designation = hr_user_data.get('designation', '')
        user.hr_employee_type = hr_user_data.get('employee_type', '')
        
        # CRITICAL FIX: Extract name from StyleHR's 'username' field
        # StyleHR puts the employee's actual name in the 'username' field
        stylehr_name = hr_user_data.get('username', '')  # This contains "Balachandran R"
        
        if stylehr_name:
            logger.info(f"Extracting name from StyleHR username field: '{stylehr_name}'")
            
            # Split the name - assume first word is first name, rest is last name
            name_parts = stylehr_name.strip().split()
            
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])
            elif len(name_parts) == 1:
                first_name = name_parts[0]
                last_name = ''
            else:
                first_name = stylehr_name
                last_name = ''
            
            # Update Django user fields
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
                logger.info(f"Updated first_name to: {first_name}")
                
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
                logger.info(f"Updated last_name to: {last_name}")
        
        # Update email if provided
        email = hr_user_data.get('email', '')
        if email and user.email != email:
            user.email = email
            updated = True
        
        # Try to extract other fields that might be present
        phone_fields = ['phone', 'mobile', 'phone_number', 'contact_number', 'mobile_number']
        for field in phone_fields:
            phone = hr_user_data.get(field, '')
            if phone and user.phone_number != phone:
                user.phone_number = phone
                updated = True
                break
        
        # Try to extract address
        address_fields = ['address', 'current_address', 'permanent_address']
        for field in address_fields:
            address = hr_user_data.get(field, '')
            if address and user.address != address:
                user.address = address
                updated = True
                break
        
        if updated:
            user.save()
            logger.info(f"Updated user data for {user.username}: name='{stylehr_name}' -> first='{user.first_name}', last='{user.last_name}'")
        
        return user


class ApprovalBasedAuthBackend(BaseBackend):
    """
    Approval-based authentication backend:
    - Drivers: Authenticate via StyleHR, then need approval
    - Managers/Admins: Regular Django authentication
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        
        # First, check if this is an existing non-driver user (admin/manager)
        try:
            existing_user = User.objects.get(username=username)
            if existing_user.user_type != 'driver':
                # Use Django's default authentication for non-drivers
                if existing_user.check_password(password):
                    if existing_user.is_active:
                        return existing_user
                return None
        except User.DoesNotExist:
            pass
        
        # For employees or new users, try StyleHR authentication
        stylehr_backend = StyleHRAuthBackend()
        return stylehr_backend.authenticate(request, username, password, **kwargs)
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class CombinedAuthBackend(ModelBackend):
    """
    Combined backend that handles both cases:
    - Tries approval-based auth first (handles both drivers via StyleHR and managers via Django)
    - Falls back to standard Django auth
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Try approval-based authentication first
        approval_backend = ApprovalBasedAuthBackend()
        user = approval_backend.authenticate(request, username, password, **kwargs)
        
        if user:
            return user
        
        # Fallback to Django's default authentication
        return super().authenticate(request, username, password, **kwargs)