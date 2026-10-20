import bookings.models
import django.contrib.postgres.constraints
import django.db.models.deletion
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


def overlap_constraint():
    return django.contrib.postgres.constraints.ExclusionConstraint(condition=models.Q(('status__in', ('payment_pending', 'confirmed'))), expressions=[(models.F('property'), '='), (models.Func(models.F('check_in'), models.F('check_out'), function='DATERANGE'), '&&')], name='reservation_no_overlap')


def install_overlap_protection(apps, schema_editor):
    Reservation = apps.get_model("bookings", "Reservation")
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        schema_editor.add_constraint(Reservation, overlap_constraint())
    elif schema_editor.connection.vendor == "sqlite":
        table = schema_editor.quote_name(Reservation._meta.db_table)
        condition = "NEW.status IN ('payment_pending', 'confirmed')"
        overlap = (
            "existing.property_id = NEW.property_id "
            "AND existing.status IN ('payment_pending', 'confirmed') "
            "AND NEW.check_in < existing.check_out "
            "AND NEW.check_out > existing.check_in"
        )
        schema_editor.execute(
            f"CREATE TRIGGER reservation_no_overlap_insert BEFORE INSERT ON {table} "
            f"WHEN {condition} AND EXISTS (SELECT 1 FROM {table} AS existing WHERE {overlap}) "
            "BEGIN SELECT RAISE(ABORT, 'reservation_no_overlap'); END"
        )
        schema_editor.execute(
            f"CREATE TRIGGER reservation_no_overlap_update BEFORE UPDATE OF property_id, check_in, check_out, status ON {table} "
            f"WHEN {condition} AND EXISTS (SELECT 1 FROM {table} AS existing "
            f"WHERE existing.id != NEW.id AND {overlap}) "
            "BEGIN SELECT RAISE(ABORT, 'reservation_no_overlap'); END"
        )


def remove_overlap_protection(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        Reservation = apps.get_model("bookings", "Reservation")
        schema_editor.remove_constraint(Reservation, overlap_constraint())
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS reservation_no_overlap_insert")
        schema_editor.execute("DROP TRIGGER IF EXISTS reservation_no_overlap_update")


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('properties', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
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
                ('booking_type', models.CharField(choices=[('daily', 'Daily'), ('monthly', 'Monthly')], default='daily', max_length=10)),
                ('nightly_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('monthly_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
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
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='ReservationCharge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('late_check_in', 'Late check-in'), ('early_check_in', 'Early check-in'), ('pet_fee', 'Pet fee'), ('extra_guest', 'Extra guest'), ('transport', 'Transport service'), ('grocery', 'Grocery pack'), ('crib', 'Baby crib'), ('other', 'Other')], default='other', max_length=24)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='charges', to='bookings.reservation')),
            ],
            options={
                'ordering': ('id',),
            },
        ),
        migrations.CreateModel(
            name='ServiceCatalog',
            fields=[
                ('key', models.SlugField(max_length=48, primary_key=True, serialize=False)),
                ('group_key', models.SlugField(blank=True, max_length=48)),
                ('category', models.CharField(choices=[('service', 'Service'), ('vehicle', 'Vehicle'), ('grocery', 'Grocery pack')], max_length=16)),
                ('kind', models.CharField(blank=True, choices=[('late_check_in', 'Late check-in'), ('early_check_in', 'Early check-in'), ('pet_fee', 'Pet fee'), ('extra_guest', 'Extra guest'), ('transport', 'Transport service'), ('grocery', 'Grocery pack'), ('crib', 'Baby crib'), ('other', 'Other')], max_length=24)),
                ('name_es', models.CharField(max_length=120)),
                ('name_en', models.CharField(max_length=120)),
                ('description_es', models.TextField(blank=True)),
                ('description_en', models.TextField(blank=True)),
                ('detail_es', models.TextField(blank=True)),
                ('detail_en', models.TextField(blank=True)),
                ('detail_key', models.SlugField(blank=True, max_length=32)),
                ('image', models.CharField(blank=True, max_length=160)),
                ('checkout_image', models.CharField(blank=True, max_length=160)),
                ('price', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=10)),
                ('secondary_price', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=10)),
                ('passengers', models.PositiveSmallIntegerField(default=0)),
                ('bags', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'ordering': ('sort_order', 'name_es'),
                'constraints': [models.CheckConstraint(condition=models.Q(('price__gte', 0)), name='service_catalog_price_nonnegative'), models.CheckConstraint(condition=models.Q(('secondary_price__gte', 0)), name='service_catalog_secondary_nonnegative')],
            },
        ),
        migrations.AddIndex(
            model_name='reservation',
            index=models.Index(fields=['property', 'check_in', 'check_out'], name='reservation_dates_idx'),
        ),
        migrations.AddIndex(
            model_name='reservation',
            index=models.Index(fields=['status', 'expires_at'], name='reservation_status_expiry_idx'),
        ),
        migrations.AddIndex(
            model_name='reservation',
            index=models.Index(fields=['user', 'created_at'], name='reservation_user_created_idx'),
        ),
        migrations.AddConstraint(
            model_name='reservation',
            constraint=models.CheckConstraint(condition=models.Q(('check_out__gt', models.F('check_in'))), name='reservation_valid_dates'),
        ),
        migrations.AddConstraint(
            model_name='reservation',
            constraint=models.CheckConstraint(condition=models.Q(('guests__gte', 1)), name='reservation_guests_positive'),
        ),
        migrations.AddConstraint(
            model_name='reservation',
            constraint=models.CheckConstraint(condition=models.Q(('total__gte', 0)), name='reservation_total_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='reservation',
            constraint=models.CheckConstraint(condition=models.Q(('tax_amount__gte', 0)), name='reservation_tax_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='reservation',
            constraint=models.CheckConstraint(condition=models.Q(('discount_amount__gte', 0)), name='reservation_discount_nonnegative'),
        ),
        migrations.AddIndex(
            model_name='reservationcharge',
            index=models.Index(fields=['reservation', 'kind'], name='charge_reservation_kind_idx'),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(install_overlap_protection, remove_overlap_protection)],
            state_operations=[migrations.AddConstraint(model_name="reservation", constraint=overlap_constraint())],
        ),
    ]
