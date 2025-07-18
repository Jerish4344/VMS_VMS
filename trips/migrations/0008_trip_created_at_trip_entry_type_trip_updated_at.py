# Generated by Django 5.2.1 on 2025-06-05 05:46

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0007_alter_trip_driver'),
    ]

    operations = [
        migrations.AddField(
            model_name='trip',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='trip',
            name='entry_type',
            field=models.CharField(choices=[('real_time', 'Real-time'), ('manual', 'Manual Entry')], default='real_time', help_text='How this trip was entered into the system', max_length=20),
        ),
        migrations.AddField(
            model_name='trip',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
