from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0002_vehicle_assigned_driver_vehicle_average_mileage_and_more'), 
    ]

    operations = [
        # Increase driver_contact field length
        migrations.AlterField(
            model_name='vehicle',
            name='driver_contact',
            field=models.CharField(max_length=100, blank=True),
        ),
        # Also increase other potentially problematic fields
        migrations.AlterField(
            model_name='vehicle',
            name='assigned_driver',
            field=models.CharField(max_length=150, blank=True),
        ),
        migrations.AlterField(
            model_name='vehicle',
            name='owner_name',
            field=models.CharField(max_length=150, blank=True),
        ),
        migrations.AlterField(
            model_name='vehicle',
            name='purpose_of_vehicle',
            field=models.CharField(max_length=200, blank=True),
        ),
        migrations.AlterField(
            model_name='vehicle',
            name='used_by',
            field=models.CharField(max_length=150, blank=True),
        ),
        migrations.AlterField(
            model_name='vehicle',
            name='gps_name',
            field=models.CharField(max_length=100, blank=True),
        ),
    ]