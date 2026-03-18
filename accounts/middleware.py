from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class DriverApprovalMiddleware(MiddlewareMixin):
    """
    Middleware to enforce approval-based access control for employees
    """
    
    # Prefix-based paths that don't have named URL patterns
    STATIC_ALLOWED_PREFIXES = ('/admin/', '/static/', '/media/')
    
    def _get_allowed_paths(self):
        """Build allowed paths from named URL patterns."""
        return [
            reverse('login'),
            reverse('logout'),
            reverse('pending_approval'),
            reverse('access_rejected'),
            reverse('notification_data'),
        ]
    
    def process_request(self, request):
        # Skip middleware for unauthenticated users
        if not request.user.is_authenticated:
            return None
        
        current_path = request.path
        
        # Check static prefixes first (admin, static, media)
        if current_path.startswith(self.STATIC_ALLOWED_PREFIXES):
            return None
        
        # Check named URL paths
        if current_path in self._get_allowed_paths():
            return None
        
        # Allow managers/vehicle managers/admins full access (they don't need approval)
        if request.user.has_approval_permissions():
            return None
        
        # For employees with vehicle access (user_type='driver') and generator users
        if request.user.user_type in ['driver', 'generator_user']:
            # Check if user can access the system
            if not request.user.can_access_system():
                logger.info(f"Blocking access for unapproved user: {request.user.username} to {current_path}")
                
                # Handle AJAX requests differently
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Access denied',
                        'message': 'Your account is pending approval',
                        'redirect': reverse('pending_approval')
                    }, status=403)
                
                # Redirect based on approval status
                if request.user.approval_status == 'pending':
                    return redirect('pending_approval')
                elif request.user.approval_status == 'rejected':
                    return redirect('access_rejected')
                else:
                    # Fallback to pending approval
                    return redirect('pending_approval')
        
        # Additional check for generator users - restrict to generator module only
        if request.user.user_type == 'generator_user':
            # Define allowed paths for generator users
            generator_allowed_paths = [
                '/dashboard/',
                '/generators/',
                '/accounts/profile/',
                '/accounts/change-password/',
                '/accounts/notifications/',
            ]
            
            # Check if current path is allowed for generator users
            generator_path_allowed = any(current_path.startswith(path) for path in generator_allowed_paths)
            
            if not generator_path_allowed:
                logger.info(f"Blocking generator user {request.user.username} from accessing {current_path}")
                messages.error(request, "You don't have permission to access this section. You can only access the Generator module.")
                return redirect('generators:generator_list')
        
        # Additional check for SOR team and SOR Head users - restrict to SOR module only
        if request.user.user_type in ['sor_team', 'sor_head']:
            # Define allowed paths for SOR team/head users
            sor_allowed_paths = [
                '/sor/',
                '/accounts/profile/',
                '/accounts/change-password/',
                '/accounts/notifications/',
                '/accounts/logout/',
            ]
            
            # Check if current path is allowed for SOR team/head users
            sor_path_allowed = any(current_path.startswith(path) for path in sor_allowed_paths)
            
            if not sor_path_allowed:
                logger.info(f"Blocking {request.user.user_type} user {request.user.username} from accessing {current_path}")
                messages.error(request, "You don't have permission to access this section. You can only access the SOR module.")
                return redirect('sor_list')
        
        # Allow access for all other cases
        return None
