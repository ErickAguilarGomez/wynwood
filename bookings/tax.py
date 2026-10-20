from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

from properties.models import Country


def resolve_tax_rate(property):

    country_code = (property.destination.country_code or "").upper()
    rate = Country.objects.filter(code=country_code).values_list("tax_rate", flat=True).first()
    return rate if rate is not None else Decimal(str(settings.BOOKING_TAX_RATE))


def included_tax_amount(total, rate):

    rate = Decimal(rate)
    if rate <= 0:
        return Decimal("0.00")
    total = Decimal(total)
    return (total - total / (Decimal("1") + rate)).quantize(Decimal("0.01"), ROUND_HALF_UP)
