from django.core.management.base import BaseCommand
from django.db import connection
import subprocess
import os


class Command(BaseCommand):
    help = 'Load MySQL timezone tables and fix timezone issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--load-timezone-data',
            action='store_true',
            help='Load timezone data into MySQL (requires mysql command line tools)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Fixing MySQL timezone issues...')
        
        # First, try to set the session timezone
        with connection.cursor() as cursor:
            try:
                # Set session timezone
                cursor.execute("SET time_zone = '+05:30'")
                self.stdout.write('✅ Set session timezone to +05:30')
                
                # Check if timezone tables exist
                cursor.execute("SELECT COUNT(*) FROM mysql.time_zone_name")
                tz_count = cursor.fetchone()[0]
                
                if tz_count == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            '⚠️  MySQL timezone tables are empty'
                        )
                    )
                    
                    if options['load_timezone_data']:
                        self.load_timezone_data()
                    else:
                        self.stdout.write(
                            'To load timezone data, run:\n'
                            'python manage.py load_mysql_timezones --load-timezone-data'
                        )
                else:
                    self.stdout.write(f'✅ MySQL timezone tables loaded ({tz_count} timezones)')
                
                # Test timezone conversion
                cursor.execute("SELECT CONVERT_TZ(NOW(), 'SYSTEM', '+05:30')")
                result = cursor.fetchone()[0]
                if result:
                    self.stdout.write(f'✅ Timezone conversion working: {result}')
                else:
                    self.stdout.write('⚠️  Timezone conversion not working')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('✅ Timezone check completed!')
        )

    def load_timezone_data(self):
        """Load timezone data into MySQL"""
        try:
            # Get database connection details from Django settings
            from django.conf import settings
            db_config = settings.DATABASES['default']
            
            # Check if timezone data exists on the system
            timezone_paths = [
                '/usr/share/zoneinfo',
                '/usr/share/lib/zoneinfo',
                '/usr/local/share/zoneinfo'
            ]
            
            zoneinfo_path = None
            for path in timezone_paths:
                if os.path.exists(path):
                    zoneinfo_path = path
                    break
            
            if not zoneinfo_path:
                self.stdout.write(
                    self.style.ERROR(
                        '❌ Could not find timezone data on system. '
                        'Please install timezone data package.'
                    )
                )
                return
            
            # Try to load timezone data
            cmd = [
                'mysql_tzinfo_to_sql',
                zoneinfo_path
            ]
            
            mysql_cmd = [
                'mysql',
                '-h', db_config['HOST'],
                '-P', str(db_config['PORT']),
                '-u', db_config['USER'],
                f'-p{db_config["PASSWORD"]}',
                'mysql'
            ]
            
            self.stdout.write('Loading timezone data into MySQL...')
            
            # Run the command
            tzinfo_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            mysql_process = subprocess.Popen(mysql_cmd, stdin=tzinfo_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            tzinfo_process.stdout.close()
            output, error = mysql_process.communicate()
            
            if mysql_process.returncode == 0:
                self.stdout.write(
                    self.style.SUCCESS('✅ Successfully loaded timezone data into MySQL')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error loading timezone data: {error.decode()}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error loading timezone data: {e}')
            )
