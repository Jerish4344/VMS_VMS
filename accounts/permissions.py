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


class VehicleViewPermissionMixin(ModulePermissionRequiredMixin):
    permission_module = 'vehicles'
    permission_action = 'view'


class VehicleAddPermissionMixin(ModulePermissionRequiredMixin):
    permission_module = 'vehicles'
    permission_action = 'add'


class VehicleEditPermissionMixin(ModulePermissionRequiredMixin):
    permission_module = 'vehicles'
    permission_action = 'edit'


class VehicleDeletePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('vehicles', 'delete'))

# Fuel Permission Mixins
class FuelViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('fuel', 'view'))

class FuelAddPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('fuel', 'add'))

class FuelEditPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('fuel', 'edit'))

class FuelDeletePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('fuel', 'delete'))

class FuelManagePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('fuel', 'manage'))

# Trips Permission Mixins
class TripsViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('trips', 'view'))

class TripsAddPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('trips', 'add'))

class TripsEditPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('trips', 'edit'))

class TripsDeletePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('trips', 'delete'))

class TripsManagePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('trips', 'manage'))

# Dashboard Permission Mixins
class CompanyDashboardPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('dashboard', 'company_dashboard'))

class StaffDashboardPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('dashboard', 'staff_dashboard'))

# Maintenance Permission Mixins
class MaintenanceViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('maintenance', 'view'))

class MaintenanceAddPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('maintenance', 'add'))

class MaintenanceEditPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('maintenance', 'edit'))

class MaintenanceDeletePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('maintenance', 'delete'))

class MaintenanceManagePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('maintenance', 'manage'))

# Generators Permission Mixins
class GeneratorsViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('generators', 'view'))

class GeneratorsAddPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('generators', 'add'))

class GeneratorsEditPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('generators', 'edit'))

class GeneratorsDeletePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('generators', 'delete'))

class GeneratorsManagePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('generators', 'manage'))

# Documents Permission Mixins
class DocumentsViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('documents', 'view'))

class DocumentsAddPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('documents', 'add'))

class DocumentsEditPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('documents', 'edit'))

class DocumentsDeletePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('documents', 'delete'))

class DocumentsManagePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('documents', 'manage'))

# Accidents Permission Mixins
class AccidentsViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('accidents', 'view'))

class AccidentsAddPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('accidents', 'add'))

class AccidentsEditPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('accidents', 'edit'))

class AccidentsDeletePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('accidents', 'delete'))

# Tracking Permission Mixins
class TrackingViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('tracking', 'view'))

class TrackingManagePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('tracking', 'manage'))

# Reports Permission Mixins
class ReportsViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'view'))

class ReportsExportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'export'))

# User Management Permission Mixins
class UsersViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('users', 'view'))

class UsersAddPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('users', 'add'))

class UsersEditPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('users', 'edit'))

class UsersDeletePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('users', 'delete'))

class UsersManagePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('users', 'manage'))

# SOR Permission Mixins
class SorViewPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('sor', 'view'))

class SorAddPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('sor', 'add'))

class SorEditPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('sor', 'edit'))

class SorDeletePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('sor', 'delete'))


class VehicleManagePermissionMixin(ModulePermissionRequiredMixin):
    permission_module = 'vehicles'
    permission_action = 'manage'


# Specific Report Permission Mixins for granular access control
class VehicleReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'vehicle_report'))

class FirmReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'firm_report'))

class DriverReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'driver_report'))

class MaintenanceReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'maintenance_report'))

class FuelReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'fuel_report'))

class ConsultantReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'consultant_report'))

class StaffReportPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.has_module_permission('reports', 'staff_report'))

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
