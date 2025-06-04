from django.contrib.auth.backends import ModelBackend

from accounts.backends import StyleHRAuthBackend

class CombinedAuthBackend(ModelBackend):
    """
    Combined authentication backend that first tries StyleHR, then falls back to Django's default
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # First try StyleHR authentication
        stylehr_backend = StyleHRAuthBackend()
        user = stylehr_backend.authenticate(request, username, password, **kwargs)
        
        if user:
            return user
        
        # Fall back to Django's default authentication for non-driver users
        return super().authenticate(request, username, password, **kwargs)