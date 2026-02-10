from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from django.utils.html import format_html
from .models import CustomUser, Module, Permission, UserPermission, UserRole, Department
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

# Should match the value in backends.py
CACHED_AUTH_VALIDITY_DAYS = 30

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
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'department', 'is_active', 'approval_status', 'cached_password_status', 'hr_authenticated_at', 'get_assigned_stores_count')
    list_filter = ('user_type', 'department', 'approval_status', 'is_active', 'is_staff', 'assigned_stores')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    filter_horizontal = ('assigned_stores',)  # Makes the many-to-many field easier to manage
    
    def get_assigned_stores_count(self, obj):
        return obj.assigned_stores.count()
    get_assigned_stores_count.short_description = 'Assigned Stores'
    
    def cached_password_status(self, obj):
        """Show if user has cached password and its validity status"""
        # Check if password exists and is hashed (not unusable)
        has_cached_password = obj.password and obj.password.startswith(('pbkdf2_', 'argon2', 'bcrypt'))
        
        if not has_cached_password:
            return format_html('<span style="color: gray;">❌ No</span>')
        
        if not obj.hr_authenticated_at:
            return format_html('<span style="color: orange;">⚠️ Cached (No HR auth date)</span>')
        
        # Check if cached credentials are still valid
        expiry_date = obj.hr_authenticated_at + timedelta(days=CACHED_AUTH_VALIDITY_DAYS)
        days_remaining = (expiry_date - timezone.now()).days
        
        if days_remaining < 0:
            return format_html('<span style="color: red;">⏰ Expired ({} days ago)</span>', abs(days_remaining))
        elif days_remaining <= 7:
            return format_html('<span style="color: orange;">⚠️ Valid ({} days left)</span>', days_remaining)
        else:
            return format_html('<span style="color: green;">✅ Valid ({} days left)</span>', days_remaining)
    
    cached_password_status.short_description = 'Cached Password'
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'address', 'profile_picture')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('User Type & Department'), {'fields': ('user_type', 'department')}),
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


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'icon', 'is_active', 'order', 'permissions_count')
    list_filter = ('is_active',)
    search_fields = ('name', 'display_name', 'description')
    ordering = ('order', 'name')
    list_editable = ('is_active', 'order')
    
    def permissions_count(self, obj):
        count = obj.permissions.count()
        return format_html(
            '<span class="badge badge-info">{}</span>',
            count
        )
    permissions_count.short_description = 'Permissions'
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # If editing an existing object
            return ('name',)  # Make name readonly when editing
        return []


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'module', 'action', 'is_default_for_admin', 'is_default_for_manager', 
                     'is_default_for_vehicle_manager', 'is_default_for_driver', 
                     'is_default_for_generator_user', 'is_default_for_sor_team')
    list_filter = ('module', 'action', 'is_default_for_admin', 'is_default_for_manager', 
                   'is_default_for_vehicle_manager', 'is_default_for_driver', 
                   'is_default_for_generator_user', 'is_default_for_sor_team')
    search_fields = ('name', 'action', 'description')
    ordering = ('module__order', 'action')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'module', 'action')
        }),
        ('Default Permissions for User Types', {
            'fields': (
                'is_default_for_admin', 
                'is_default_for_manager',
                'is_default_for_vehicle_manager',
                'is_default_for_driver',
                'is_default_for_generator_user',
                'is_default_for_sor_team'
            ),
            'classes': ('wide',),
            'description': 'Set which user types should have this permission by default.'
        }),
    )


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'permission', 'granted', 'granted_by', 'granted_at')
    list_filter = ('granted', 'permission__module', 'permission__action', 'granted_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'permission__name')
    ordering = ('-granted_at',)
    date_hierarchy = 'granted_at'
    raw_id_fields = ('user', 'granted_by')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'permission', 'permission__module', 'granted_by'
        )


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'is_active', 'permissions_count')
    list_filter = ('is_active',)
    search_fields = ('name', 'display_name', 'description')
    ordering = ('name',)
    filter_horizontal = ('default_permissions',)
    list_editable = ('is_active',)
    
    def permissions_count(self, obj):
        count = obj.default_permissions.count()
        return format_html(
            '<span class="badge badge-primary">{}</span>',
            count
        )
    permissions_count.short_description = 'Default Permissions'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'get_employee_count', 'get_vehicle_count', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)
    list_editable = ('is_active',)
    
    fieldsets = (
        (None, {'fields': ('name', 'code', 'description')}),
        ('Status', {'fields': ('is_active',)}),
    )
    
    def get_employee_count(self, obj):
        count = obj.get_employee_count()
        return format_html('<span style="color: blue;">{}</span>', count)
    get_employee_count.short_description = 'Employees'
    
    def get_vehicle_count(self, obj):
        count = obj.get_vehicle_count()
        return format_html('<span style="color: green;">{}</span>', count)
    get_vehicle_count.short_description = 'Vehicles'


# Customize the admin site
admin.site.site_header = "VMS User Rights Administration"
admin.site.site_title = "VMS Admin"
admin.site.index_title = "Welcome to VMS Administration"
