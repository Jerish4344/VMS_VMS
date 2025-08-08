# accounts/models.py - Updated for all employees
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class CustomUser(AbstractUser):
    """
    Custom user model with approval-based access for employees
    Any employee from StyleHR can potentially access the vehicle system
    """
    
    USER_TYPES = (
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('vehicle_manager', 'Vehicle Manager'),
        ('driver', 'Employee (Vehicle Access)'),  # Updated label
        ('generator_user', 'Generator User'),  # New role for generator-only access
    )
    
    APPROVAL_STATUS = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    user_type = models.CharField(
        max_length=20, 
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
    
    # Generator user specific fields
    assigned_stores = models.ManyToManyField(
        'generators.Store',
        blank=True,
        related_name='assigned_users',
        help_text="Stores this user has access to (for generator users)"
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
        if self.user_type in ['driver', 'generator_user']:  # Include generator users
            return self.is_active and self.approval_status == 'approved'
        else:
            # Admins, managers, vehicle managers use normal Django auth
            return self.is_active
    
    def is_pending_approval(self):
        """Check if employee is pending approval"""
        return self.user_type in ['driver', 'generator_user'] and self.approval_status == 'pending'
    
    def needs_approval(self):
        """Check if user needs approval for system access"""
        return self.user_type in ['driver', 'generator_user']
    
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
    
    def is_generator_user(self):
        """Check if user is a generator user or has generator access"""
        return self.user_type == 'generator_user' or self.has_full_access
    
    def has_vehicle_access(self):
        """Check if user has vehicle system access"""
        return self.user_type == 'driver' or self.has_full_access
    
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
        
    def has_approval_permissions(self):
        """Check if user can approve/reject employees"""
        return self.user_type in ['admin', 'manager', 'vehicle_manager']
    
    def has_management_access(self):
        """Check if user has any management access"""
        return self.user_type in ['admin', 'manager', 'vehicle_manager']
