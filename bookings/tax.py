











from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings


TAX_RATES = {
    "AR": Decimal("0.21"),
    "CL": Decimal("0.19"),
    "CO": Decimal("0.19"),
    "EC": Decimal("0.15"),
    "ES": Decimal("0.21"),
    "MX": Decimal("0.16"),
    "PA": Decimal("0.07"),
    "PE": Decimal("0.18"),
}


def resolve_tax_rate(property):

    country_code = (property.destination.country_code or "").upper()
    return TAX_RATES.get(country_code, Decimal(str(settings.BOOKING_TAX_RATE)))


def included_tax_amount(total, rate):

    rate = Decimal(rate)
    if rate <= 0:
        return Decimal("0.00")
    total = Decimal(total)
    return (total - total / (Decimal("1") + rate)).quantize(Decimal("0.01"), ROUND_HALF_UP)
