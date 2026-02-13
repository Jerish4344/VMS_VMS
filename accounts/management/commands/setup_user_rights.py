from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Module, Permission


class Command(BaseCommand):
    help = 'Setup initial modules and permissions for user rights system'

    def handle(self, *args, **options):
        self.stdout.write('Setting up modules and permissions...')
        
        with transaction.atomic():
            # Define modules with their permissions
            modules_data = [
                {
                    'name': 'dashboard',
                    'display_name': 'Dashboard',
                    'description': 'Main dashboard with overview and statistics',
                    'icon': 'fas fa-tachometer-alt',
                    'order': 1,
                    'permissions': [
                        {
                            'action': 'company_dashboard', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': True, 'personal_vehicle_staff_default': True, 'company_vehicle_staff_default': True, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'staff_dashboard', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': True, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'vehicles',
                    'display_name': 'Vehicles',
                    'description': 'Vehicle management and information',
                    'icon': 'fas fa-car',
                    'order': 2,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': True, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': True, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'add', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'edit', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'delete', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'manage', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'trips',
                    'display_name': 'Trips',
                    'description': 'Trip management and tracking',
                    'icon': 'fas fa-route',
                    'order': 3,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': True, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': True, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'add', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': True, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': True, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'edit', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'delete', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'manage', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'fuel',
                    'display_name': 'Fuel',
                    'description': 'Fuel transactions and management',
                    'icon': 'fas fa-gas-pump',
                    'order': 4,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'add', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'edit', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'delete', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'manage', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'maintenance',
                    'display_name': 'Maintenance',
                    'description': 'Vehicle maintenance and service records',
                    'icon': 'fas fa-tools',
                    'order': 5,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'add', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'edit', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'delete', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'manage', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'generators',
                    'display_name': 'Generators',
                    'description': 'Generator management and tracking',
                    'icon': 'fas fa-dharmachakra',
                    'order': 6,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': True, 'sor_default': False
                        },
                        {
                            'action': 'add', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'edit', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'delete', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'manage', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'documents',
                    'display_name': 'Documents',
                    'description': 'Document management and storage',
                    'icon': 'fas fa-file-alt',
                    'order': 7,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'add', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'edit', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'delete', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'manage', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'accidents',
                    'display_name': 'Accidents',
                    'description': 'Accident reporting and management',
                    'icon': 'fas fa-car-crash',
                    'order': 8,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': True, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': True, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'add', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': True, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': True, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'edit', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'delete', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'tracking',
                    'display_name': 'Vehicle Tracking',
                    'description': 'GPS tracking and location monitoring',
                    'icon': 'fas fa-satellite-dish',
                    'order': 9,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'manage', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'reports',
                    'display_name': 'Reports',
                    'description': 'System reports and analytics',
                    'icon': 'fas fa-chart-bar',
                    'order': 10,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'export', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'vehicle_report', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'firm_report', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'driver_report', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'maintenance_report', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'fuel_report', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'consultant_report', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'department_report', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'daily_usage_cost', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'users',
                    'display_name': 'User Management',
                    'description': 'User management and administration',
                    'icon': 'fas fa-users',
                    'order': 11,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'add', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'edit', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'delete', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'manage', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'user_rights', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'sor',
                    'display_name': 'SOR (Security Outward Register)',
                    'description': 'Security outward register management',
                    'icon': 'fas fa-clipboard-list',
                    'order': 12,
                    'permissions': [
                        {
                            'action': 'view', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': False,
                            'driver_default': True, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': True
                        },
                        {
                            'action': 'add', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': True
                        },
                        {
                            'action': 'edit', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': True
                        },
                        {
                            'action': 'delete', 
                            'admin_default': True, 'manager_default': False, 'vehicle_manager_default': False,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'employee_management',
                    'display_name': 'Employee Management and Approvals',
                    'description': 'Employee Management and Approvals',
                    'icon': 'fas fa-user-tie',
                    'order': 13,
                    'permissions': [
                        {
                            'action': 'pending_approvals', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'all_employees', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
                {
                    'name': 'generator_management',
                    'display_name': 'Generator User Management',
                    'description': 'Generator User Management',
                    'icon': 'fas fa-users-cog',
                    'order': 14,
                    'permissions': [
                        {
                            'action': 'all_generator_users', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                        {
                            'action': 'store_access', 
                            'admin_default': True, 'manager_default': True, 'vehicle_manager_default': True,
                            'driver_default': False, 'personal_vehicle_staff_default': False, 'company_vehicle_staff_default': False, 'generator_default': False, 'sor_default': False
                        },
                    ]
                },
            ]

            # Create modules and permissions
            for module_data in modules_data:
                # Create or update module
                module, created = Module.objects.get_or_create(
                    name=module_data['name'],
                    defaults={
                        'display_name': module_data['display_name'],
                        'description': module_data['description'],
                        'icon': module_data['icon'],
                        'order': module_data['order'],
                        'is_active': True,
                    }
                )
                
                if created:
                    self.stdout.write(f'Created module: {module.display_name}')
                else:
                    # Update existing module
                    module.display_name = module_data['display_name']
                    module.description = module_data['description']
                    module.icon = module_data['icon']
                    module.order = module_data['order']
                    module.save()
                    self.stdout.write(f'Updated module: {module.display_name}')

                # Create permissions for this module
                for perm_data in module_data['permissions']:
                    permission, created = Permission.objects.get_or_create(
                        module=module,
                        action=perm_data['action'],
                        defaults={
                            'name': f"{perm_data['action'].title()} {module_data['display_name']}",
                            'description': f"Permission to {perm_data['action']} {module_data['display_name']}",
                            'is_default_for_admin': perm_data.get('admin_default', False),
                            'is_default_for_manager': perm_data.get('manager_default', False),
                            'is_default_for_vehicle_manager': perm_data.get('vehicle_manager_default', False),
                            'is_default_for_driver': perm_data.get('driver_default', False),
                            'is_default_for_personal_vehicle_staff': perm_data.get('personal_vehicle_staff_default', False),
                            'is_default_for_generator_user': perm_data.get('generator_default', False),
                            'is_default_for_sor_team': perm_data.get('sor_default', False),
                        }
                    )
                    
                    if created:
                        self.stdout.write(f"    Created permission: {permission.name}")
                    else:
                        # Update default permissions if they've changed
                        updated = False
                        field_mappings = {
                            'is_default_for_admin': 'admin_default',
                            'is_default_for_manager': 'manager_default',
                            'is_default_for_vehicle_manager': 'vehicle_manager_default',
                            'is_default_for_driver': 'driver_default',
                            'is_default_for_company_vehicle_staff': 'company_vehicle_staff_default',
                            'is_default_for_personal_vehicle_staff': 'personal_vehicle_staff_default',
                            'is_default_for_generator_user': 'generator_default',
                            'is_default_for_sor_team': 'sor_default',
                        }
                        
                        for field_name, data_key in field_mappings.items():
                            new_value = perm_data.get(data_key, False)
                            if getattr(permission, field_name) != new_value:
                                setattr(permission, field_name, new_value)
                                updated = True
                        
                        if updated:
                            permission.save()
                            self.stdout.write(f"    Updated permission: {permission.name}")
                        
                        for field_name, data_key in field_mappings.items():
                            new_value = perm_data.get(data_key, False)
                            if getattr(permission, field_name) != new_value:
                                setattr(permission, field_name, new_value)
                                updated = True
                        
                        if updated:
                            permission.save()
                            self.stdout.write(f"    Updated permission: {permission.name}")

        self.stdout.write(
            self.style.SUCCESS('Successfully setup modules and permissions!')
        )
        
        # Assign default permissions to existing users
        self.stdout.write('Assigning default permissions to existing users...')
        
        from accounts.models import CustomUser, UserPermission
        
        # Get all active users
        users = CustomUser.objects.filter(is_active=True)
        total_users = users.count()
        
        for i, user in enumerate(users, 1):
            self.stdout.write(f'Processing user {i}/{total_users}: {user.username} ({user.user_type})')
            
            # Skip user types that don't have permission fields
            permission_field = f'is_default_for_{user.user_type}'
            if not hasattr(Permission, permission_field):
                self.stdout.write(f'    Skipping - no permission field for user type: {user.user_type}')
                continue
            
            # Get all permissions that should be default for this user type
            default_permissions = Permission.objects.filter(**{
                permission_field: True
            })
            
            assigned_count = 0
            for permission in default_permissions:
                # Check if user already has this permission
                user_permission, created = UserPermission.objects.get_or_create(
                    user=user,
                    permission=permission,
                    defaults={'granted': True}
                )
                
                if created:
                    assigned_count += 1
                    self.stdout.write(f'    Assigned: {permission.name}')
                elif not user_permission.granted:
                    # If permission exists but was not granted, grant it now
                    user_permission.granted = True
                    user_permission.save()
                    assigned_count += 1
                    self.stdout.write(f'    Granted: {permission.name}')
            
            if assigned_count > 0:
                self.stdout.write(f'    Total permissions assigned to {user.username}: {assigned_count}')
            else:
                self.stdout.write(f'    No new permissions assigned to {user.username}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully processed {total_users} users!')
        )
