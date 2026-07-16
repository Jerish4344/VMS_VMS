from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm
from django.contrib.auth import authenticate
from django.core.cache import cache
from .models import CustomUser

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 15 * 60  # seconds


def login_attempts_cache_key(username):
    """Shared with accounts.admin so the unlock action clears the same key this form sets."""
    return f'login_attempts:{username.strip().lower()}'


class ApprovalAuthenticationForm(AuthenticationForm):
    """
    Authentication form that handles both StyleHR (employees) and local (managers) auth
    """
    username = forms.CharField(
        label='Username / Employee ID / Email',
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Employees: Employee ID/Email | Managers: Username',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Employees: HR Password | Managers: VMS Password'
        })
    )
    
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is not None and password:
            cache_key = login_attempts_cache_key(username)
            attempts = cache.get(cache_key, 0)

            if attempts >= LOGIN_ATTEMPT_LIMIT:
                raise forms.ValidationError(
                    'Too many failed login attempts for this account. '
                    'Please wait 15 minutes and try again.',
                    code='locked_out'
                )

            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password
            )

            if self.user_cache is None:
                cache.set(cache_key, attempts + 1, LOGIN_ATTEMPT_WINDOW)
                raise forms.ValidationError(
                    'Invalid credentials. Please check your username/password.',
                    code='invalid_login'
                )
            else:
                cache.delete(cache_key)
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data
    
    def confirm_login_allowed(self, user):
        """Allow login but handle approval status in views"""
        if not user.is_active:
            raise forms.ValidationError(
                'Your account has been deactivated.',
                code='inactive'
            )
        # Check if user has web access
        if not user.can_access_web():
            raise forms.ValidationError(
                'Your account is configured for mobile access only. '
                'Please use the mobile app to log in.',
                code='no_web_access'
            )


class EmployeeApprovalForm(forms.Form):
    """Form for approving/rejecting employee access with role selection"""
    
    # Access type selection
    access_type = forms.ChoiceField(
        choices=[
            ('driver', 'Vehicle System Access (Driver)'),
            ('generator_user', 'Generator System Access Only'),
            ('both', 'Full Access (Vehicles + Generators)'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'access-type-radio'}),
        initial='driver',
        label='Grant Access Type',
        help_text='Choose what type of system access to grant to this employee'
    )
    
    # Action selection
    action = forms.ChoiceField(
        choices=[
            ('approve', 'Approve Access'),
            ('reject', 'Reject Access')
        ],
        widget=forms.RadioSelect(attrs={'class': 'action-radio'}),
        initial='approve',
        label='Approval Decision'
    )
    
    # Rejection reason
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter reason for rejection (required only for rejection)'
        }),
        required=False,
        label='Rejection Reason'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        # Require rejection reason only when rejecting
        if action == 'reject' and not rejection_reason:
            raise forms.ValidationError('Please provide a reason for rejection.')
        
        return cleaned_data


# Keep legacy form names for backward compatibility
DriverApprovalForm = EmployeeApprovalForm

# Existing forms for admin user management
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'user_type', 'access_type',
                  'phone_number', 'address', 'license_number', 'license_expiry', 'profile_picture')

class CustomUserChangeForm(UserChangeForm):
    password = None  # Remove password field from the form
    
    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'access_type', 'phone_number', 'address', 
                  'license_number', 'license_expiry', 'profile_picture')
        
class DriverUserChangeForm(UserChangeForm):
    password = None  # Remove password field from the form
    
    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'phone_number', 'address', 
                  'license_number', 'license_expiry', 'profile_picture')
