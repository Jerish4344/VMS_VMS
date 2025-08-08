from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = '__all__'

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'user_type')

class CustomUserAdmin(DefaultUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'is_active', 'approval_status', 'get_assigned_stores_count')
    list_filter = ('user_type', 'approval_status', 'is_active', 'is_staff', 'assigned_stores')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    filter_horizontal = ('assigned_stores',)  # Makes the many-to-many field easier to manage
    
    def get_assigned_stores_count(self, obj):
        return obj.assigned_stores.count()
    get_assigned_stores_count.short_description = 'Assigned Stores'
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'address', 'profile_picture')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('User Type'), {'fields': ('user_type',)}),
        (_('Driver Info'), {'fields': ('license_number', 'license_expiry')}),
        (_('Generator Access'), {'fields': ('assigned_stores',)}),
        (_('Approval System'), {'fields': ('approval_status', 'approved_by', 'approved_at', 'rejection_reason')}),
        (_('HR Integration'), {'fields': ('hr_employee_id', 'hr_department', 'hr_designation', 'hr_employee_type', 'hr_authenticated_at')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'user_type'),
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)
