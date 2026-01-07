from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import CustomUser, UserPermission, Permission, Module


class Command(BaseCommand):
    help = 'Remove tracking access from all drivers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Actually perform the removal (without this, it will only show what would be removed)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Checking tracking permissions for drivers...')
        
        try:
            # Get tracking module and all its permissions
            tracking_module = Module.objects.get(name='tracking')
            tracking_permissions = Permission.objects.filter(module=tracking_module)
            
            # Find all drivers with any tracking permissions
            drivers_with_tracking = UserPermission.objects.filter(
                user__user_type='driver',
                user__is_active=True,
                permission__module=tracking_module,
                granted=True
            ).select_related('user', 'permission').order_by('user__username', 'permission__action')
            
            if not drivers_with_tracking.exists():
                self.stdout.write(self.style.SUCCESS('No drivers have tracking permissions to remove.'))
                return
            
            # Group by user
            drivers_dict = {}
            for up in drivers_with_tracking:
                if up.user.username not in drivers_dict:
                    drivers_dict[up.user.username] = {
                        'user': up.user,
                        'permissions': []
                    }
                drivers_dict[up.user.username]['permissions'].append(up.permission.action)
            
            self.stdout.write(f'\nFound {len(drivers_dict)} drivers with tracking permissions:')
            total_permissions = 0
            
            for username, data in drivers_dict.items():
                permissions_str = ', '.join(data['permissions'])
                self.stdout.write(f'  - {username}: {permissions_str}')
                total_permissions += len(data['permissions'])
            
            self.stdout.write(f'\nTotal tracking permissions to remove: {total_permissions}')
            
            if not options['confirm']:
                self.stdout.write(self.style.WARNING('\nThis is a DRY RUN. Use --confirm to actually remove the permissions.'))
                self.stdout.write('Command to run: python manage.py remove_driver_tracking_access --confirm')
                return
            
            # Confirm removal
            self.stdout.write(self.style.WARNING(f'\nRemoving tracking access from {len(drivers_dict)} drivers...'))
            
            with transaction.atomic():
                removed_count = 0
                
                for username, data in drivers_dict.items():
                    user = data['user']
                    
                    # Remove all tracking permissions for this driver
                    user_tracking_perms = UserPermission.objects.filter(
                        user=user,
                        permission__module=tracking_module,
                        granted=True
                    )
                    
                    for up in user_tracking_perms:
                        up.granted = False
                        up.save()
                        removed_count += 1
                        self.stdout.write(f'  Removed {up.permission.action} from {user.username}')
                
                self.stdout.write(
                    self.style.SUCCESS(f'\nSuccessfully removed {removed_count} tracking permissions from {len(drivers_dict)} drivers!')
                )
                
        except Module.DoesNotExist:
            self.stdout.write(self.style.ERROR('Tracking module not found. Make sure the setup_user_rights command has been run.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))
