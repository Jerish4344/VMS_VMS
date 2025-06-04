from django.db import models
from django.conf import settings

class Notification(models.Model):
    """System notifications for users."""
    
    LEVEL_CHOICES = (
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('danger', 'Danger'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    text = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    icon = models.CharField(max_length=50, default='bell')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.text} ({self.user.username})"