from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import CustomUser, UserPermission, Permission, Module


class Command(BaseCommand):
    help = 'Remove maintenance access from all drivers and update default permissions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Actually perform the removal (without this, it will only show what would be removed)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Updating maintenance permissions for drivers...')
        
        try:
            # Get maintenance module and all its permissions
            maintenance_module = Module.objects.get(name='maintenance')
            maintenance_permissions = Permission.objects.filter(module=maintenance_module)
            
            if not options['confirm']:
                self.stdout.write(self.style.WARNING('\nDRY RUN - No changes will be made. Use --confirm to apply changes.\n'))
            
            # Step 1: Update default permissions to remove driver access
            self.stdout.write('\n1. Updating default permissions for maintenance module:')
            for permission in maintenance_permissions:
                old_value = permission.is_default_for_driver
                if old_value:
                    self.stdout.write(f'   - {permission.action}: is_default_for_driver = {old_value} -> False')
                    if options['confirm']:
                        permission.is_default_for_driver = False
                        permission.save()
            
            # Step 2: Find all drivers with any maintenance permissions
            drivers_with_maintenance = UserPermission.objects.filter(
                user__user_type='driver',
                user__is_active=True,
                permission__module=maintenance_module,
                granted=True
            ).select_related('user', 'permission').order_by('user__username', 'permission__action')
            
            if not drivers_with_maintenance.exists():
                self.stdout.write(self.style.SUCCESS('\n2. No drivers have explicit maintenance permissions to remove.'))
            else:
                # Group by user
                drivers_dict = {}
                for up in drivers_with_maintenance:
                    if up.user.username not in drivers_dict:
                        drivers_dict[up.user.username] = {
                            'user': up.user,
                            'permissions': [],
                            'user_perms': []
                        }
                    drivers_dict[up.user.username]['permissions'].append(up.permission.action)
                    drivers_dict[up.user.username]['user_perms'].append(up)
                
                self.stdout.write(f'\n2. Found {len(drivers_dict)} drivers with explicit maintenance permissions:')
                
                for username, data in drivers_dict.items():
                    permissions_str = ', '.join(data['permissions'])
                    self.stdout.write(f'   - {data["user"].get_full_name()} ({username}): {permissions_str}')
                
                if options['confirm']:
                    with transaction.atomic():
                        for username, data in drivers_dict.items():
                            for up in data['user_perms']:
                                up.granted = False
                                up.save()
                    self.stdout.write(self.style.SUCCESS(f'\n   Removed maintenance permissions from {len(drivers_dict)} drivers.'))
            
            if options['confirm']:
                self.stdout.write(self.style.SUCCESS('\n✅ Maintenance permissions successfully updated for drivers!'))
                self.stdout.write('   Drivers will no longer see the Maintenance menu in the web app.')
            else:
                self.stdout.write(self.style.WARNING('\n⚠️  No changes made. Run with --confirm to apply these changes.'))
                
        except Module.DoesNotExist:
            self.stdout.write(self.style.ERROR('Maintenance module not found. Please run setup_user_rights first.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
