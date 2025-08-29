from django.db import models
from django.conf import settings
from .models import SOR

class SORNotification(models.Model):
    sor = models.ForeignKey(SOR, on_delete=models.CASCADE, related_name='notifications')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SOR Notification for {self.driver} - SOR #{self.sor.id}"
