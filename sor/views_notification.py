from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.timezone import localtime
from .notification import SORNotification

@login_required
def sor_notifications_api(request):
    notifications = SORNotification.objects.filter(driver=request.user, is_read=False).order_by('-created_at')[:10]
    data = [
        {
            'id': n.id,
            'message': n.message,
            'created_at': localtime(n.created_at).strftime('%Y-%m-%d %H:%M'),
            'sor_id': n.sor.id,
        }
        for n in notifications
    ]
    return JsonResponse({'notifications': data, 'count': len(data)})
