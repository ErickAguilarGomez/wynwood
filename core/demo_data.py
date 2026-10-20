import json
from pathlib import Path

from bookings.models import ServiceCatalog
from properties.models import Country


def seed_catalogs():
    data = json.loads(Path(__file__).with_name("demo_catalogs.json").read_text())
    for country in data["countries"]:
        Country.objects.get_or_create(code=country["code"], defaults=country)
    for service in data["services"]:
        ServiceCatalog.objects.get_or_create(key=service["key"], defaults=service)
    return data
