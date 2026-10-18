from django.conf import settings
from django.utils import timezone

from properties.forms import PropertySearchForm
from properties.models import Destination


def site_context(request):
    default_destination = (
        Destination.objects.filter(slug="lima").first()
        or Destination.objects.order_by("sort_order", "name_es").first()
    )
    destinations_by_country = {}
    for destination in Destination.objects.order_by("country_code", "sort_order", "name_es"):
        destinations_by_country.setdefault(destination.country, []).append(destination)

    return {
        "booking_currency": settings.BOOKING_CURRENCY,
        "local_today": timezone.localdate().isoformat(),
        "footer_search_form": PropertySearchForm(initial={"destination": default_destination, "guests": 2}),
        "footer_destination": default_destination,
        "footer_destinations_by_country": destinations_by_country,
        "whatsapp_url": settings.WYNWOOD_WHATSAPP_URL,
    }
