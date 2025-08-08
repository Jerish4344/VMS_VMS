from django.db.models import Q
from .models import CustomUser

def approval_notifications(request):
    """
    Add approval notification context to all templates
    """
    context = {}
    
    if request.user.is_authenticated and request.user.has_approval_permissions():
        # Count pending approvals for drivers
        pending_drivers_count = CustomUser.objects.filter(
            user_type='driver',
            approval_status='pending'
        ).count()
        
        # Count pending approvals for generator users
        pending_generator_users_count = CustomUser.objects.filter(
            user_type='generator_user',
            approval_status='pending'
        ).count()
        
        # Total pending approvals (both driver and generator_user types)
        pending_count = pending_drivers_count + pending_generator_users_count
        
        # Get recent pending employees (last 5)
        recent_pending = CustomUser.objects.filter(
            Q(user_type='driver') | Q(user_type='generator_user'),
            approval_status='pending'
        ).order_by('-hr_authenticated_at')[:5]
        
        # Count new requests (last 24 hours)
        from django.utils import timezone
        from datetime import timedelta
        
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        new_requests_count = CustomUser.objects.filter(
            Q(user_type='driver') | Q(user_type='generator_user'),
            approval_status='pending',
            hr_authenticated_at__gte=twenty_four_hours_ago
        ).count()
        
        context.update({
            'pending_approvals_count': pending_count,
            'pending_drivers_count': pending_drivers_count,
            'pending_generator_users_count': pending_generator_users_count,
            'recent_pending_employees': recent_pending,
            'new_approval_requests_count': new_requests_count,
            'has_pending_approvals': pending_count > 0,
        })
    
    # Add user role information for template logic
    if request.user.is_authenticated:
        context['is_generator_user'] = request.user.has_generator_access()
        context['has_vehicle_access'] = request.user.has_vehicle_access()
        context['has_full_access'] = getattr(request.user, 'has_full_access', False)
        context['user_accessible_stores'] = []
        
        if hasattr(request.user, 'get_accessible_stores'):
            context['user_accessible_stores'] = request.user.get_accessible_stores()
    
    return context
