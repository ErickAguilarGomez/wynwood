from django.conf import settings
from django.utils import timezone

from properties.forms import PropertySearchForm
from properties.models import Country, Destination


def site_context(request):
    destinations = list(Destination.objects.order_by("country_code", "sort_order", "name_es"))
    default_destination = next((destination for destination in destinations if destination.slug == "lima"), None)
    if default_destination is None:
        default_destination = min(destinations, key=lambda destination: (destination.sort_order, destination.name_es), default=None)
    countries = list(Country.objects.all())
    country_names = {country.code: country.name for country in countries}
    destinations_by_country = {}
    for destination in destinations:
        name = country_names.get(destination.country_code.upper(), destination.country_code)
        destinations_by_country.setdefault(name, []).append(destination)

    return {
        "booking_currency": settings.BOOKING_CURRENCY,
        "local_today": timezone.localdate().isoformat(),
        "footer_search_form": PropertySearchForm(initial={"destination": default_destination, "guests": 2}),
        "footer_destination": default_destination,
        "footer_destinations_by_country": destinations_by_country,
        "footer_countries": [country for country in countries if country.is_active and country.show_on_home],
        "whatsapp_url": settings.WYNWOOD_WHATSAPP_URL,
    }
