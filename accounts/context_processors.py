from django.db.models import Q
from .models import CustomUser

def approval_notifications(request):
    """
    Add approval notification context to all templates
    """
    context = {}
    
    if request.user.is_authenticated and request.user.has_approval_permissions():
        # Count pending approvals
        pending_count = CustomUser.objects.filter(
            user_type='driver',
            approval_status='pending'
        ).count()
        
        # Get recent pending employees (last 5)
        recent_pending = CustomUser.objects.filter(
            user_type='driver',
            approval_status='pending'
        ).order_by('-hr_authenticated_at')[:5]
        
        # Count new requests (last 24 hours)
        from django.utils import timezone
        from datetime import timedelta
        
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        new_requests_count = CustomUser.objects.filter(
            user_type='driver',
            approval_status='pending',
            hr_authenticated_at__gte=twenty_four_hours_ago
        ).count()
        
        context.update({
            'pending_approvals_count': pending_count,
            'recent_pending_employees': recent_pending,
            'new_approval_requests_count': new_requests_count,
            'has_pending_approvals': pending_count > 0,
        })
    
    return context