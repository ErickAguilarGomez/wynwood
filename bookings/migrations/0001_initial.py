import bookings.models
import django.contrib.postgres.constraints
import django.contrib.postgres.operations
import django.db.models.deletion
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):


    initial = True

    dependencies = [
        ('properties', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        django.contrib.postgres.operations.BtreeGistExtension(
        ),
        migrations.CreateModel(
            name='Reservation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('check_in', models.DateField()),
                ('check_out', models.DateField()),
                ('guests', models.PositiveSmallIntegerField()),
                ('language_code', models.CharField(choices=[('es', 'Español'), ('en', 'English')], default='es', max_length=2)),
                ('status', models.CharField(choices=[('payment_pending', 'Payment pending'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('expired', 'Expired'), ('payment_failed', 'Payment failed')], default='payment_pending', max_length=24)),
                ('nightly_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('nights', models.PositiveSmallIntegerField()),
                ('subtotal', models.DecimalField(decimal_places=2, max_digits=10)),
                ('cleaning_fee', models.DecimalField(decimal_places=2, max_digits=10)),
                ('discount_amount', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=10)),
                ('currency', models.CharField(default=bookings.models.default_currency, max_length=3)),
                ('tax_rate', models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=5)),
                ('tax_amount', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=10)),
                ('total', models.DecimalField(decimal_places=2, max_digits=10)),
                ('points_earned', models.PositiveIntegerField(default=0)),
                ('expires_at', models.DateTimeField()),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('confirmation_sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reservations', to='properties.property')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reservations', to=settings.AUTH_USER_MODEL)),
                ('booking_type', models.CharField(choices=[('daily', 'Daily'), ('monthly', 'Monthly')], default='daily', max_length=10)),
                ('monthly_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
            ],
            options={
                'ordering': ('-created_at',),
                'indexes': [models.Index(fields=['property', 'check_in', 'check_out'], name='reservation_dates_idx'), models.Index(fields=['status', 'expires_at'], name='reservation_status_expiry_idx'), models.Index(fields=['user', 'created_at'], name='reservation_user_created_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(('check_out__gt', models.F('check_in'))), name='reservation_valid_dates'), models.CheckConstraint(condition=models.Q(('guests__gte', 1)), name='reservation_guests_positive'), models.CheckConstraint(condition=models.Q(('total__gte', 0)), name='reservation_total_nonnegative'), models.CheckConstraint(condition=models.Q(('tax_amount__gte', 0)), name='reservation_tax_nonnegative'), models.CheckConstraint(condition=models.Q(('discount_amount__gte', 0)), name='reservation_discount_nonnegative'), django.contrib.postgres.constraints.ExclusionConstraint(condition=models.Q(('status__in', ('payment_pending', 'confirmed'))), expressions=[(models.F('property'), '='), (models.Func(models.F('check_in'), models.F('check_out'), function='DATERANGE'), '&&')], name='reservation_no_overlap')],
            },
        ),
        migrations.CreateModel(
            name='ReservationCharge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('late_check_in', 'Late check-in'), ('early_check_in', 'Early check-in'), ('pet_fee', 'Pet fee'), ('extra_guest', 'Extra guest'), ('transport', 'Transport service'), ('grocery', 'Grocery pack'), ('crib', 'Baby crib'), ('other', 'Other')], default='other', max_length=24)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='charges', to='bookings.reservation')),
                ('details', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'ordering': ('id',),
                'indexes': [models.Index(fields=['reservation', 'kind'], name='charge_reservation_kind_idx')],
            },
        ),
    ]
