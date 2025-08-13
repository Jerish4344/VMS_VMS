from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='trip',
            name='is_deleted',
            field=models.BooleanField(default=False, help_text='Mark trip as deleted instead of removing from DB'),
        ),
        migrations.AddField(
            model_name='trip',
            name='deleted_by',
            field=models.ForeignKey(blank=True, help_text='User who deleted this trip', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deleted_trips', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='trip',
            name='deleted_at',
            field=models.DateTimeField(blank=True, help_text='When the trip was deleted', null=True),
        ),
    ]
