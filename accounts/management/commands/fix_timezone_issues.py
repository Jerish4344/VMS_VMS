from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from datetime import datetime
import pytz


class Command(BaseCommand):
    help = 'Fix timezone issues in the database'

    def handle(self, *args, **options):
        self.stdout.write('Checking and fixing timezone issues...')
        
        with connection.cursor() as cursor:
            # Check if timezone tables exist
            try:
                cursor.execute("SELECT COUNT(*) FROM mysql.time_zone")
                timezone_count = cursor.fetchone()[0]
                self.stdout.write(f'MySQL timezone tables loaded: {timezone_count > 0}')
                
                if timezone_count == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            'MySQL timezone tables are not loaded. You may need to run:\n'
                            'mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root -p mysql'
                        )
                    )
                
                # Set the session timezone
                cursor.execute("SET time_zone = '+05:30'")
                self.stdout.write('Set session timezone to +05:30 (Asia/Kolkata)')
                
                # Check current timezone setting
                cursor.execute("SELECT @@session.time_zone, @@global.time_zone")
                session_tz, global_tz = cursor.fetchone()
                self.stdout.write(f'Session timezone: {session_tz}')
                self.stdout.write(f'Global timezone: {global_tz}')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error checking timezone: {e}')
                )
        
        # Test Django timezone functionality
        try:
            now = timezone.now()
            self.stdout.write(f'Current Django timezone: {timezone.get_current_timezone()}')
            self.stdout.write(f'Current time: {now}')
            
            # Test conversion to local timezone
            local_tz = pytz.timezone('Asia/Kolkata')
            local_time = now.astimezone(local_tz)
            self.stdout.write(f'Local time (Asia/Kolkata): {local_time}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error with Django timezone: {e}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Timezone check completed!')
        )
