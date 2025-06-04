from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

class DriverApprovalMiddleware(MiddlewareMixin):
    """
    Middleware to enforce approval-based access control for employees
    """
    
    def process_request(self, request):
        # Skip middleware for unauthenticated users
        if not request.user.is_authenticated:
            return None
        
        # Define paths that should be accessible without approval
        allowed_paths = [
            '/accounts/login/',
            '/accounts/logout/',
            '/accounts/pending-approval/',
            '/accounts/access-rejected/',
            '/admin/',
            '/static/',
            '/media/',
            # Add API endpoints that should be accessible
            '/accounts/notifications/data/',
        ]
        
        # Check if current path is in allowed paths
        current_path = request.path
        if any(current_path.startswith(path) for path in allowed_paths):
            return None
        
        # Allow managers/vehicle managers/admins full access (they don't need approval)
        if request.user.has_approval_permissions():
            return None
        
        # For employees with vehicle access (user_type='driver')
        if request.user.user_type == 'driver':
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
        
        # Allow access for all other cases
        return None