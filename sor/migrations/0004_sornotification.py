from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('sor', '0003_sor_trip'),
    ]

    operations = [
        migrations.CreateModel(
            name='SORNotification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.CharField(max_length=255)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('driver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.CustomUser')),
                ('sor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='sor.sor')),
            ],
        ),
    ]
