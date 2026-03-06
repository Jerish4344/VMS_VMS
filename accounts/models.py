# accounts/models.py - Updated for all employees
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError


class Department(models.Model):
    """
    Department/Team in the organization.
    Used to group employees and vehicles for reporting and management.
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, blank=True, help_text="Short code like 'HR', 'IT', 'SALES'")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
    
    def __str__(self):
        if self.code:
            return f"{self.name} ({self.code})"
        return self.name
    
    def get_employee_count(self):
        """Count employees in this department"""
        return self.employees.count()
    
    def get_vehicle_count(self):
        """Count company vehicles assigned to this department"""
        from vehicles.models import Vehicle
        return Vehicle.objects.filter(department=self, ownership_type='company').count()


class CustomUser(AbstractUser):
    """
    Custom user model with approval-based access for employees
    Any employee from StyleHR can potentially access the vehicle system
    """
    
    USER_TYPES = (
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('vehicle_manager', 'Vehicle Manager'),
        ('driver', 'Driver'),  # Professional drivers
        ('company_vehicle_staff', 'Staff (Company Vehicle)'),  # Staff using company vehicles (bikes, etc.)
        ('personal_vehicle_staff', 'Staff (Personal Vehicle)'),  # Staff using own vehicles for reimbursement
        ('generator_user', 'Generator User'),  # New role for generator-only access
	    ('sor_team', 'SOR Team'),  # SOR team role
	    ('p2p_service', 'P2P Service Account'),  # External P2P system integration
    )
    
    APPROVAL_STATUS = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    user_type = models.CharField(
        max_length=30, 
        choices=USER_TYPES,
        default='driver'  # Default for vehicle access
    )
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/', 
        null=True, 
        blank=True
    )
    
    # Approval system fields
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS,
        default='pending',
        help_text="Approval status for vehicle system access"
    )
    approved_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_employees',
        help_text="Manager/Admin who approved this employee"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection")
    
    # HR Integration fields
    hr_employee_id = models.CharField(max_length=50, blank=True, help_text="Employee ID from HR system")
    hr_data = models.JSONField(null=True, blank=True, help_text="Data received from HR system")
    hr_authenticated_at = models.DateTimeField(null=True, blank=True)
    
    # Employee details from HR
    hr_department = models.CharField(max_length=100, blank=True, help_text="Department from HR")
    hr_designation = models.CharField(max_length=100, blank=True, help_text="Designation from HR")
    hr_employee_type = models.CharField(max_length=50, blank=True, help_text="Employee type from HR")
    
    # Department assignment (Admin managed)
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        help_text="Department this user belongs to (assigned by admin)"
    )
    
    # Generator user specific fields
    assigned_stores = models.ManyToManyField(
        'generators.Store',
        blank=True,
        related_name='assigned_users',
        help_text="Stores this user has access to (for generator users)"
    )
    
    # Platform access control
    ACCESS_TYPE_CHOICES = (
        ('web', 'Web Only'),
        ('mobile', 'Mobile Only'),
        ('both', 'Web & Mobile'),
    )
    access_type = models.CharField(
        max_length=10,
        choices=ACCESS_TYPE_CHOICES,
        default='both',
        help_text="Controls which platform(s) this user can log in from"
    )
    
    # Flag for users with both vehicle and generator access
    has_full_access = models.BooleanField(
        default=False,
        help_text="True if user has both vehicle and generator access"
    )
    
    class Meta:
        ordering = ['username']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['user_type']),
            models.Index(fields=['approval_status']),
            models.Index(fields=['user_type', 'approval_status']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_user_type_display()})"
    
    def get_full_name(self):
        """Return the user's full name."""
        full_name = super().get_full_name()
        if not full_name:
            return self.username
        return full_name
    
    def can_access_system(self):
        """Check if user can access the system"""
        if self.user_type in ['driver', 'company_vehicle_staff', 'generator_user']:  # Include all field users
            return self.is_active and self.approval_status == 'approved'
        else:
            # Admins, managers, vehicle managers use normal Django auth
            return self.is_active
    
    def can_access_web(self):
        """Check if user is allowed to log in via the web interface"""
        return self.access_type in ('web', 'both')
    
    def can_access_mobile(self):
        """Check if user is allowed to log in via the mobile app"""
        return self.access_type in ('mobile', 'both')
    
    def is_pending_approval(self):
        """Check if employee is pending approval"""
        return self.user_type in ['driver', 'company_vehicle_staff', 'generator_user'] and self.approval_status == 'pending'
    
    def needs_approval(self):
        """Check if user needs approval for system access"""
        return self.user_type in ['driver', 'company_vehicle_staff', 'generator_user']
    
    def approve_access(self, approved_by_user, access_type='driver', save=True):
        """Approve employee access with specified access type"""
        if self.needs_approval():
            self.approval_status = 'approved'
            self.approved_by = approved_by_user
            self.approved_at = timezone.now()
            self.rejection_reason = ''
            
            # Set the user type and access flags based on access type granted
            if access_type == 'driver':
                self.user_type = 'driver'
                self.has_full_access = False
            elif access_type == 'company_vehicle_staff':
                self.user_type = 'company_vehicle_staff'
                self.has_full_access = False
            elif access_type == 'generator_user':
                self.user_type = 'generator_user'
                self.has_full_access = False
            elif access_type == 'both':
                # For both access, set as driver with full access flag
                self.user_type = 'driver'
                self.has_full_access = True
            
            if save:
                self.save()
    
    def reject_access(self, rejected_by_user, reason='', save=True):
        """Reject employee access"""
        if self.needs_approval():
            self.approval_status = 'rejected'
            self.approved_by = rejected_by_user
            self.approved_at = timezone.now()
            self.rejection_reason = reason
            if save:
                self.save()
    
    # Keep existing methods but update terminology
    def is_license_valid(self):
        if not self.license_expiry:
            return False
        return self.license_expiry >= timezone.now().date()
    
    def is_employee_with_vehicle_access(self):
        """Check if user is an employee with vehicle access"""
        return self.user_type == 'driver'
    
    def is_driver(self):
        """Legacy method - now means employee with vehicle access"""
        return self.user_type == 'driver'
    
    def is_admin(self):
        return self.user_type == 'admin'
    
    def is_manager(self):
        return self.user_type == 'manager'
    
    def is_vehicle_manager(self):
        return self.user_type == 'vehicle_manager'
    
    def is_company_vehicle_staff(self):
        """Check if user is staff with company vehicle"""
        return self.user_type == 'company_vehicle_staff'
    
    def is_generator_user(self):
        """Check if user is a generator user or has generator access"""
        return self.user_type == 'generator_user' or self.has_full_access
    
    def has_vehicle_access(self):
        """Check if user has vehicle system access"""
        return self.user_type in ['driver', 'company_vehicle_staff'] or self.has_full_access
    
    def has_generator_access(self):
        """Check if user has generator system access"""
        return self.user_type == 'generator_user' or self.has_full_access
    
    def has_store_access(self, store):
        """Check if generator user has access to a specific store"""
        if not self.has_generator_access():
            return False
        if self.has_full_access and self.user_type == 'driver':
            return True  # Full access users can access all stores
        return self.assigned_stores.filter(id=store.id).exists()
    
    def get_accessible_stores(self):
        """Get list of stores this user can access"""
        if not self.has_generator_access():
            from generators.models import Store
            return Store.objects.none()
        if self.has_full_access and self.user_type == 'driver':
            from generators.models import Store
            return Store.objects.all()
        return self.assigned_stores.all()
    
    def has_management_access(self):
        return self.user_type in ['admin', 'manager', 'vehicle_manager']
    
    def has_approval_permissions(self):
        """Check if user can approve/reject employees"""
        return self.user_type in ['admin', 'manager', 'vehicle_manager']
    
    def get_hr_role_display(self):
        """Get formatted HR role information"""
        if not self.hr_data:
            return "No HR data"
        
        parts = []
        if self.hr_designation:
            parts.append(self.hr_designation)
        if self.hr_department:
            parts.append(f"({self.hr_department})")
        
        return " ".join(parts) if parts else "HR Employee"
    
    def has_driving_license(self):
        """Check if employee has driving license on file"""
        return bool(self.license_number and self.license_expiry)
    
    def license_status(self):
        """Get license status for display"""
        if not self.license_number:
            return "No License on File"
        elif not self.license_expiry:
            return "License Expiry Not Set"
        elif not self.is_license_valid():
            return "License Expired"
        elif (self.license_expiry - timezone.now().date()).days <= 30:
            return "License Expiring Soon"
        else:
            return "Valid License"
        
    def _get_permissions_cache_key(self):
        """Get the Redis cache key for this user's permissions."""
        return f'user_permissions_{self.pk}'
    
    def _load_all_permissions(self):
        """
        Load ALL permissions for this user in a single query and cache them.
        Returns a dict: {(module_name, action): bool}
        
        Previously has_module_permission() ran 3 DB queries per call.
        With 103 permission checks in base.html alone, that was 309 queries
        per page load. This replaces all of them with 1 query, cached in Redis.
        """
        from django.core.cache import cache
        
        cache_key = self._get_permissions_cache_key()
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            # Cache backend is down (Redis not running, etc.) — skip cache
            pass
        
        # Map user_type to the corresponding default field name
        role_field_map = {
            'admin': 'is_default_for_admin',
            'manager': 'is_default_for_manager',
            'vehicle_manager': 'is_default_for_vehicle_manager',
            'driver': 'is_default_for_driver',
            'company_vehicle_staff': 'is_default_for_company_vehicle_staff',
            'personal_vehicle_staff': 'is_default_for_personal_vehicle_staff',
            'generator_user': 'is_default_for_generator_user',
            'sor_team': 'is_default_for_sor_team',
        }
        
        role_field = role_field_map.get(self.user_type)
        
        # Single query: fetch all permissions with their module names
        all_permissions = Permission.objects.select_related('module').values_list(
            'module__name', 'action', 'id',
            'is_default_for_admin', 'is_default_for_manager',
            'is_default_for_vehicle_manager', 'is_default_for_driver',
            'is_default_for_company_vehicle_staff', 'is_default_for_personal_vehicle_staff',
            'is_default_for_generator_user', 'is_default_for_sor_team',
        )
        
        # Single query: fetch all explicit user overrides
        user_overrides = dict(
            UserPermission.objects.filter(user=self).values_list(
                'permission_id', 'granted'
            )
        )
        
        # Field index map for the values_list tuple
        field_index = {
            'is_default_for_admin': 3,
            'is_default_for_manager': 4,
            'is_default_for_vehicle_manager': 5,
            'is_default_for_driver': 6,
            'is_default_for_company_vehicle_staff': 7,
            'is_default_for_personal_vehicle_staff': 8,
            'is_default_for_generator_user': 9,
            'is_default_for_sor_team': 10,
        }
        
        permissions_map = {}
        for perm_row in all_permissions:
            module_name = perm_row[0]
            action = perm_row[1]
            perm_id = perm_row[2]
            
            # Check explicit user override first
            if perm_id in user_overrides:
                permissions_map[(module_name, action)] = user_overrides[perm_id]
            elif role_field and role_field in field_index:
                permissions_map[(module_name, action)] = perm_row[field_index[role_field]]
            else:
                permissions_map[(module_name, action)] = False
        
        # Cache for 5 minutes
        try:
            cache.set(cache_key, permissions_map, 300)
        except Exception:
            pass  # Cache backend down — still return the computed result
        return permissions_map
    
    def invalidate_permissions_cache(self):
        """Invalidate cached permissions. Call after granting/revoking."""
        from django.core.cache import cache
        try:
            cache.delete(self._get_permissions_cache_key())
        except Exception:
            pass  # Cache backend down — safe to ignore
    
    def has_module_permission(self, module_name, action):
        """
        Check if user has permission for a specific module and action.
        Uses cached permissions — 0 DB queries after the first call.
        """
        permissions_map = self._load_all_permissions()
        return permissions_map.get((module_name, action), False)
    
    def get_accessible_modules(self):
        """
        Get list of modules this user can access.
        Uses cached permissions + 1 query for active modules.
        """
        permissions_map = self._load_all_permissions()
        
        # Get module names the user can 'view'
        viewable_module_names = {
            module_name for (module_name, action), granted in permissions_map.items()
            if action == 'view' and granted
        }
        
        if not viewable_module_names:
            return []
        
        return list(Module.objects.filter(
            is_active=True,
            name__in=viewable_module_names
        ))
    
    def get_user_permissions_for_module(self, module_name):
        """
        Get all permissions for a specific module for this user.
        Uses cached permissions — 0 DB queries.
        """
        permissions_map = self._load_all_permissions()
        return {
            action: granted
            for (mod_name, action), granted in permissions_map.items()
            if mod_name == module_name
        }
    
    def grant_permission(self, module_name, action, granted_by_user):
        """
        Grant a specific permission to this user
        """
        try:
            module = Module.objects.get(name=module_name)
            permission = Permission.objects.get(module=module, action=action)
            
            user_perm, created = UserPermission.objects.get_or_create(
                user=self,
                permission=permission,
                defaults={
                    'granted': True,
                    'granted_by': granted_by_user
                }
            )
            
            if not created:
                user_perm.granted = True
                user_perm.granted_by = granted_by_user
                user_perm.granted_at = timezone.now()
                user_perm.save()
            
            # Invalidate cached permissions after granting
            self.invalidate_permissions_cache()
            
            return user_perm
        except (Module.DoesNotExist, Permission.DoesNotExist):
            return None
    
    def revoke_permission(self, module_name, action, granted_by_user):
        """
        Revoke a specific permission from this user
        """
        try:
            module = Module.objects.get(name=module_name)
            permission = Permission.objects.get(module=module, action=action)
            
            user_perm, created = UserPermission.objects.get_or_create(
                user=self,
                permission=permission,
                defaults={
                    'granted': False,
                    'granted_by': granted_by_user
                }
            )
            
            if not created:
                user_perm.granted = False
                user_perm.granted_by = granted_by_user
                user_perm.granted_at = timezone.now()
                user_perm.save()
            
            # Invalidate cached permissions after revoking
            self.invalidate_permissions_cache()
            
            return user_perm
        except (Module.DoesNotExist, Permission.DoesNotExist):
            return None


class Module(models.Model):
    """
    Represents system modules like Vehicles, Trips, Fuel, etc.
    """
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order in navigation")
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Module'
        verbose_name_plural = 'Modules'
    
    def __str__(self):
        return self.display_name


class Permission(models.Model):
    """
    Represents specific permissions for actions within modules
    """
    ACTION_CHOICES = [
        ('view', 'View'),
        ('add', 'Add/Create'),
        ('edit', 'Edit/Update'),
        ('delete', 'Delete'),
        ('export', 'Export'),
        ('manage', 'Manage'),  # Special permission for admin-like actions
    ]
    
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='permissions')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    name = models.CharField(max_length=100)  # e.g., "vehicle_view", "trip_add"
    description = models.TextField(blank=True)
    
    # Default permissions for each user type
    is_default_for_admin = models.BooleanField(default=True, help_text="Default permission for admin role")
    is_default_for_manager = models.BooleanField(default=False, help_text="Default permission for manager role")
    is_default_for_vehicle_manager = models.BooleanField(default=False, help_text="Default permission for vehicle manager role")
    is_default_for_driver = models.BooleanField(default=False, help_text="Default permission for driver role")
    is_default_for_company_vehicle_staff = models.BooleanField(default=False, help_text="Default permission for staff with company vehicle")
    is_default_for_personal_vehicle_staff = models.BooleanField(default=False, help_text="Default permission for personal vehicle staff role")
    is_default_for_generator_user = models.BooleanField(default=False, help_text="Default permission for generator user role")
    is_default_for_sor_team = models.BooleanField(default=False, help_text="Default permission for SOR team role")
    
    class Meta:
        unique_together = ['module', 'action']
        ordering = ['module', 'action']
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
    
    def __str__(self):
        return f"{self.module.display_name} - {self.get_action_display()}"


class UserPermission(models.Model):
    """
    Represents user-specific permissions that override default role permissions
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_permissions_custom')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    granted = models.BooleanField(default=True, help_text="True to grant permission, False to explicitly deny")
    granted_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='granted_permissions'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'permission']
        ordering = ['user', 'permission__module', 'permission__action']
        verbose_name = 'User Permission'
        verbose_name_plural = 'User Permissions'
    
    def __str__(self):
        status = "Granted" if self.granted else "Denied"
        return f"{self.user.get_full_name()} - {self.permission} ({status})"


class UserRole(models.Model):
    """
    Extended role model for more granular role management
    """
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    default_permissions = models.ManyToManyField(
        Permission, 
        blank=True, 
        related_name='default_roles',
        help_text="Default permissions for this role"
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
    
    def __str__(self):
        return self.display_name
