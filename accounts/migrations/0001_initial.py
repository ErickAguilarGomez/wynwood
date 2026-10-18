import accounts.managers
import django.db.models.functions.text
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):


    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, verbose_name='superuser status')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('groups', models.ManyToManyField(blank=True, related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='Date of birth')),
                ('country', models.CharField(blank=True, choices=[('AR', 'Argentina'), ('CL', 'Chile'), ('CO', 'Colombia'), ('EC', 'Ecuador'), ('ES', 'Spain'), ('IT', 'Italy'), ('MX', 'Mexico'), ('PA', 'Panama'), ('PE', 'Peru'), ('US', 'United States')], max_length=2, verbose_name='Country')),
                ('phone', models.CharField(blank=True, max_length=32, verbose_name='Phone')),
            ],
            options={
                'abstract': False,
                'constraints': [models.UniqueConstraint(django.db.models.functions.text.Lower('email'), name='user_email_case_insensitive_unique')],
            },
            managers=[
                ('objects', accounts.managers.UserManager()),
            ],
        ),
    ]
