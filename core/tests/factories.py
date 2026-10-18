from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from properties.models import Destination, Property


def create_user(email="guest@example.com"):
    return User.objects.create_user(email=email, password="Strong-pass-2048", first_name="Alex", last_name="Guest")


def create_property(slug="central-home", **overrides):
    destination, _ = Destination.objects.get_or_create(
        slug="madrid",
        defaults={"name_es": "Madrid", "name_en": "Madrid", "country_code": "ES"},
    )
    data = {
        "destination": destination,
        "slug": slug,
        "title_es": "Casa Central",
        "title_en": "Central Home",
        "summary_es": "Una casa cómoda",
        "summary_en": "A comfortable home",
        "description_es": "Descripción",
        "description_en": "Description",
        "country": "España",
        "province": "Madrid",
        "district": "Centro",
        "address": "Central Avenue 10",
        "price_per_night": 100,
        "cleaning_fee": 25,
        "max_guests": 4,
        "bedrooms": 2,
        "beds": 2,
        "bathrooms": 1,
        "is_active": True,
        "is_featured": True,
    }
    data.update(overrides)
    return Property.objects.create(**data)


def future_dates(offset=10, nights=3):
    check_in = timezone.localdate() + timedelta(days=offset)
    return check_in, check_in + timedelta(days=nights)
