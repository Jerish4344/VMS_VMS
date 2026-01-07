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


def permission_required(module_name, action='view'):
    """
    Decorator to check if user has specific module permission
    Usage: @permission_required('vehicles', 'add')
    """
    def decorator(view_func):
        @wraps(view_func)
        @approval_required
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.has_module_permission(module_name, action):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Permission denied',
                        'message': f'You do not have {action} permission for {module_name} module'
                    }, status=403)
                
                messages.error(request, f'You do not have permission to {action} {module_name}.')
                raise PermissionDenied(f"User does not have {action} permission for {module_name} module")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def module_access_required(module_name):
    """
    Decorator to check if user has access to a specific module (view permission)
    Usage: @module_access_required('vehicles')
    """
    return permission_required(module_name, 'view')


def admin_required(view_func):
    """
    Decorator to ensure only admins can access a view
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.user_type != 'admin':
            raise PermissionDenied("This page is only accessible to administrators.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def ajax_permission_required(module_name, action='view'):
    """
    Decorator specifically for AJAX views that require permissions
    Returns JSON error responses instead of redirects
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            # Check if user can access system
            if not request.user.can_access_system() and not request.user.has_approval_permissions():
                return JsonResponse({
                    'error': 'Access denied',
                    'message': 'Your account is pending approval'
                }, status=403)
            
            # Check specific permission
            if not request.user.has_module_permission(module_name, action):
                return JsonResponse({
                    'error': 'Permission denied',
                    'message': f'You do not have {action} permission for {module_name} module'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def check_user_permissions(user, required_permissions):
    """
    Helper function to check multiple permissions at once
    
    Args:
        user: CustomUser instance
        required_permissions: List of tuples [(module_name, action), ...]
    
    Returns:
        dict: {permission_key: bool, ...}
    """
    permissions = {}
    for module_name, action in required_permissions:
        permission_key = f"{module_name}_{action}"
        permissions[permission_key] = user.has_module_permission(module_name, action)
    
    return permissions
