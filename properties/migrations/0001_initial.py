import django.core.validators
import django.db.models.deletion
import properties.models
from django.db import migrations, models

class Migration(migrations.Migration):


    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Amenity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name_es', models.CharField(max_length=80)),
                ('name_en', models.CharField(max_length=80)),
                ('icon', models.CharField(default='check', max_length=40)),
            ],
            options={
                'ordering': ('name_es',),
            },
        ),
        migrations.CreateModel(
            name='Destination',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name_es', models.CharField(max_length=120)),
                ('name_en', models.CharField(max_length=120)),
                ('slug', models.SlugField(unique=True)),
                ('country_code', models.CharField(default='ES', max_length=2)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'ordering': ('sort_order', 'name_es'),
            },
        ),
        migrations.CreateModel(
            name='Property',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(unique=True)),
                ('title_es', models.CharField(max_length=180)),
                ('title_en', models.CharField(max_length=180)),
                ('summary_es', models.CharField(max_length=240)),
                ('summary_en', models.CharField(max_length=240)),
                ('description_es', models.TextField()),
                ('description_en', models.TextField()),
                ('address', models.CharField(max_length=240)),
                ('price_per_night', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('cleaning_fee', models.DecimalField(decimal_places=2, default=0, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('max_guests', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('bedrooms', models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
                ('beds', models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
                ('bathrooms', models.DecimalField(decimal_places=1, default=1, max_digits=3, validators=[django.core.validators.MinValueValidator(0.5)])),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('is_featured', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('amenities', models.ManyToManyField(blank=True, related_name='properties', to='properties.amenity')),
                ('destination', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='properties', to='properties.destination')),
            ],
            options={
                'ordering': ('-is_featured', 'title_es'),
            },
        ),
        migrations.CreateModel(
            name='PropertyImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(height_field='height', upload_to=properties.models.property_image_path, width_field='width')),
                ('alt_es', models.CharField(max_length=180)),
                ('alt_en', models.CharField(max_length=180)),
                ('width', models.PositiveIntegerField(default=0, editable=False)),
                ('height', models.PositiveIntegerField(default=0, editable=False)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='properties.property')),
            ],
            options={
                'ordering': ('sort_order', 'id'),
            },
        ),
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['destination', 'is_active'], name='prop_dest_active_idx'),
        ),
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['is_featured', 'is_active'], name='prop_featured_active_idx'),
        ),
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['price_per_night', 'max_guests'], name='prop_price_guests_idx'),
        ),
        migrations.AddConstraint(
            model_name='property',
            constraint=models.CheckConstraint(condition=models.Q(('price_per_night__gte', 0)), name='property_price_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='property',
            constraint=models.CheckConstraint(condition=models.Q(('cleaning_fee__gte', 0)), name='property_cleaning_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='property',
            constraint=models.CheckConstraint(condition=models.Q(('max_guests__gte', 1)), name='property_guests_positive'),
        ),
        migrations.AddConstraint(
            model_name='propertyimage',
            constraint=models.UniqueConstraint(fields=('property', 'sort_order'), name='unique_property_image_order'),
        ),
        migrations.AlterField(
            model_name='propertyimage',
            name='image',
            field=models.ImageField(height_field='height', upload_to=properties.models.property_image_path, validators=[properties.models.validate_image_size], width_field='width'),
        ),
        migrations.AlterModelOptions(
            name='amenity',
            options={'ordering': ('sort_order', 'name_es')},
        ),
        migrations.AddField(
            model_name='amenity',
            name='sort_order',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='property',
            name='country',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='property',
            name='province',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='property',
            name='district',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['country', 'is_active'], name='prop_country_active_idx'),
        ),
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['district', 'is_active'], name='prop_district_active_idx'),
        ),
        migrations.AddField(
            model_name='property',
            name='price_per_month',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddConstraint(
            model_name='property',
            constraint=models.CheckConstraint(condition=models.Q(('price_per_month__isnull', True), ('price_per_month__gte', 0), _connector='OR'), name='property_price_month_nonnegative'),
        ),
    ]
