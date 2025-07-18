# Generated by Django 5.2.1 on 2025-05-13 10:15

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Accident',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_time', models.DateTimeField()),
                ('location', models.CharField(max_length=255)),
                ('latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('description', models.TextField()),
                ('damage_description', models.TextField()),
                ('third_party_involved', models.BooleanField(default=False)),
                ('police_report_number', models.CharField(blank=True, max_length=100)),
                ('injuries', models.BooleanField(default=False)),
                ('injuries_description', models.TextField(blank=True)),
                ('estimated_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('actual_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('insurance_claim_number', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(choices=[('reported', 'Reported'), ('under_investigation', 'Under Investigation'), ('repair_scheduled', 'Repair Scheduled'), ('repair_in_progress', 'Repair In Progress'), ('resolved', 'Resolved')], default='reported', max_length=20)),
                ('resolution_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['-date_time'],
            },
        ),
        migrations.CreateModel(
            name='AccidentImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='accident_images/')),
                ('caption', models.CharField(blank=True, max_length=255)),
            ],
        ),
    ]
