from django.contrib.auth.mixins import UserPassesTestMixin

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

class ManagerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.user_type == 'manager' or 
            self.request.user.user_type == 'admin'
        )

class VehicleManagerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.user_type == 'vehicle_manager' or 
            self.request.user.user_type == 'manager' or 
            self.request.user.user_type == 'admin'
        )

    
class ApprovalRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.has_approval_permissions()

class DriverRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'driver'


# Permission-based mixins that use our custom permission system
class ModulePermissionRequiredMixin(UserPassesTestMixin):
    """Base mixin for checking module permissions"""
    permission_module = None
    permission_action = None
    
    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        
        if not self.permission_module or not self.permission_action:
            return False
            
        return self.request.user.has_module_permission(self.permission_module, self.permission_action)


def _make_permission_mixin(module, action):
    """Factory to create permission mixin classes with less boilerplate."""
    class_name = f"{''.join(w.capitalize() for w in module.split('_'))}{''.join(w.capitalize() for w in action.split('_'))}PermissionMixin"
    return type(class_name, (ModulePermissionRequiredMixin,), {
        'permission_module': module,
        'permission_action': action,
    })


# --- Generated permission mixins ---
# Vehicles
VehicleViewPermissionMixin = _make_permission_mixin('vehicles', 'view')
VehicleAddPermissionMixin = _make_permission_mixin('vehicles', 'add')
VehicleEditPermissionMixin = _make_permission_mixin('vehicles', 'edit')
VehicleDeletePermissionMixin = _make_permission_mixin('vehicles', 'delete')
VehicleManagePermissionMixin = _make_permission_mixin('vehicles', 'manage')

# Fuel
FuelViewPermissionMixin = _make_permission_mixin('fuel', 'view')
FuelAddPermissionMixin = _make_permission_mixin('fuel', 'add')
FuelEditPermissionMixin = _make_permission_mixin('fuel', 'edit')
FuelDeletePermissionMixin = _make_permission_mixin('fuel', 'delete')
FuelManagePermissionMixin = _make_permission_mixin('fuel', 'manage')

# Trips
TripsViewPermissionMixin = _make_permission_mixin('trips', 'view')
TripsAddPermissionMixin = _make_permission_mixin('trips', 'add')
TripsEditPermissionMixin = _make_permission_mixin('trips', 'edit')
TripsDeletePermissionMixin = _make_permission_mixin('trips', 'delete')
TripsManagePermissionMixin = _make_permission_mixin('trips', 'manage')

# Dashboard
CompanyDashboardPermissionMixin = _make_permission_mixin('dashboard', 'company_dashboard')
StaffDashboardPermissionMixin = _make_permission_mixin('dashboard', 'staff_dashboard')

# Maintenance
MaintenanceViewPermissionMixin = _make_permission_mixin('maintenance', 'view')
MaintenanceAddPermissionMixin = _make_permission_mixin('maintenance', 'add')
MaintenanceEditPermissionMixin = _make_permission_mixin('maintenance', 'edit')
MaintenanceDeletePermissionMixin = _make_permission_mixin('maintenance', 'delete')
MaintenanceManagePermissionMixin = _make_permission_mixin('maintenance', 'manage')

# Generators
GeneratorsViewPermissionMixin = _make_permission_mixin('generators', 'view')
GeneratorsAddPermissionMixin = _make_permission_mixin('generators', 'add')
GeneratorsEditPermissionMixin = _make_permission_mixin('generators', 'edit')
GeneratorsDeletePermissionMixin = _make_permission_mixin('generators', 'delete')
GeneratorsManagePermissionMixin = _make_permission_mixin('generators', 'manage')

# Documents
DocumentsViewPermissionMixin = _make_permission_mixin('documents', 'view')
DocumentsAddPermissionMixin = _make_permission_mixin('documents', 'add')
DocumentsEditPermissionMixin = _make_permission_mixin('documents', 'edit')
DocumentsDeletePermissionMixin = _make_permission_mixin('documents', 'delete')
DocumentsManagePermissionMixin = _make_permission_mixin('documents', 'manage')

# Accidents
AccidentsViewPermissionMixin = _make_permission_mixin('accidents', 'view')
AccidentsAddPermissionMixin = _make_permission_mixin('accidents', 'add')
AccidentsEditPermissionMixin = _make_permission_mixin('accidents', 'edit')
AccidentsDeletePermissionMixin = _make_permission_mixin('accidents', 'delete')

# Tracking
TrackingViewPermissionMixin = _make_permission_mixin('tracking', 'view')
TrackingManagePermissionMixin = _make_permission_mixin('tracking', 'manage')

# Reports
ReportsViewPermissionMixin = _make_permission_mixin('reports', 'view')
ReportsExportPermissionMixin = _make_permission_mixin('reports', 'export')
VehicleReportPermissionMixin = _make_permission_mixin('reports', 'vehicle_report')
FirmReportPermissionMixin = _make_permission_mixin('reports', 'firm_report')
DriverReportPermissionMixin = _make_permission_mixin('reports', 'driver_report')
MaintenanceReportPermissionMixin = _make_permission_mixin('reports', 'maintenance_report')
FuelReportPermissionMixin = _make_permission_mixin('reports', 'fuel_report')

# Users
UsersViewPermissionMixin = _make_permission_mixin('users', 'view')
UsersAddPermissionMixin = _make_permission_mixin('users', 'add')
UsersEditPermissionMixin = _make_permission_mixin('users', 'edit')
UsersDeletePermissionMixin = _make_permission_mixin('users', 'delete')
UsersManagePermissionMixin = _make_permission_mixin('users', 'manage')

# SOR
SorViewPermissionMixin = _make_permission_mixin('sor', 'view')
SorAddPermissionMixin = _make_permission_mixin('sor', 'add')
SorEditPermissionMixin = _make_permission_mixin('sor', 'edit')
SorDeletePermissionMixin = _make_permission_mixin('sor', 'delete')

class ConsultantReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'consultant_report'))

class StaffReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'staff_report'))

class DepartmentReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'department_report'))

class DailyUsageCostPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'daily_usage_cost'))


# Employee Management Permission Mixins for granular access control
class PendingEmployeesPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('employee_management', 'pending_approvals'))

class AllEmployeesPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('employee_management', 'all_employees'))


# Generator User Management Permission Mixins for granular access control  
class GeneratorUsersPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('generator_management', 'all_generator_users'))

class StoreAccessPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('generator_management', 'store_access'))


# User Rights Management Permission Mixin for granular access control
class UserRightsPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('users', 'user_rights'))
