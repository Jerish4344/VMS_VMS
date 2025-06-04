from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse

def approval_required(view_func):
    """
    Decorator to ensure user has been approved for system access
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Managers and admins don't need approval
        if request.user.has_approval_permissions():
            return view_func(request, *args, **kwargs)
        
        # Check if employee has been approved
        if not request.user.can_access_system():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Access denied',
                    'message': 'Your account is pending approval'
                }, status=403)
            
            if request.user.approval_status == 'pending':
                messages.warning(request, 'Your account is still pending approval. Please wait for management to review your request.')
                return redirect('pending_approval')
            elif request.user.approval_status == 'rejected':
                messages.error(request, 'Your access has been rejected. Please contact management.')
                return redirect('access_rejected')
            else:
                return redirect('pending_approval')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

def employee_required(view_func):
    """
    Decorator to ensure only employees (with vehicle access) can access a view
    """
    @wraps(view_func)
    @approval_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.user_type != 'driver':
            raise PermissionDenied("This page is only accessible to employees with vehicle access.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def manager_required(view_func):
    """
    Decorator to ensure only managers can access a view
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.has_approval_permissions():
            raise PermissionDenied("This page is only accessible to managers.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def vehicle_manager_required(view_func):
    """
    Decorator to ensure only vehicle managers, managers, or admins can access a view
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.has_approval_permissions():
            raise PermissionDenied("This page is only accessible to vehicle managers, managers, or administrators.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view