import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('bookings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(default='wynwood_simulator', max_length=30)),
                ('status', models.CharField(choices=[('created', 'Created'), ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled'), ('error', 'Error')], default='created', max_length=20)),
                ('idempotency_key', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('checkout_reference_id', models.CharField(blank=True, max_length=160, null=True, unique=True)),
                ('transaction_id', models.CharField(blank=True, max_length=160, null=True, unique=True)),
                ('status_detail', models.CharField(blank=True, max_length=120)),
                ('provider_snapshot', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reservation', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='payment', to='bookings.reservation')),
            ],
            options={
                'indexes': [models.Index(fields=['status', 'created_at'], name='payment_status_created_idx')],
            },
        ),
    ]
