from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.dates import parse_date
from properties.models import Property

from .additional_services import get_services
from .models import Reservation, ReservationCharge, ServiceCatalog
from .tax import included_tax_amount, resolve_tax_rate


class PropertyUnavailable(Exception):
    pass


class ReservationValidationError(Exception):
    pass


def service_is_configured(charge, service=None):
    detail = service.detail if service else next(
        (detail for detail, kind in ServiceCatalog.configuration_kinds.items() if kind == charge.kind), None
    )
    if detail is None:
        return service is None
    details = charge.details or {}
    if not details.get("configured"):
        return False
    if detail == "transport":
        departure = (details.get("departure") or "").partition(" ")[0]
        try:
            quantity = int(details.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        return bool(
            parse_date(departure)
            and " " in (details.get("departure") or "")
            and details.get("departure_end")
            and quantity > 0
            and details.get("vehicle")
            and details.get("airport")
            and (
                details.get("trip_type") != "round_trip"
                or (
                    parse_date((details.get("return") or "").partition(" ")[0])
                    and " " in (details.get("return") or "")
                    and details.get("return_end")
                )
            )
        )
    if detail == "flexible_checkin":
        return bool(parse_date(details.get("service_date", "")) and details.get("check_in_time"))
    if detail == "groceries":
        return bool(parse_date(details.get("delivery_date", "")) and details.get("pack"))
    if detail == "crib":
        try:
            quantity = int(details.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        return bool(
            parse_date(details.get("start_date", ""))
            and parse_date(details.get("end_date", ""))
            and quantity > 0
        )
    return False


def _validate_amounts(model=Reservation, **amounts):
    try:
        for name, amount in amounts.items():
            model._meta.get_field(name).run_validators(amount)
    except ValidationError as error:
        raise ReservationValidationError(_("The reservation amount exceeds the supported limit.")) from error


def _normalize_charges(charges):

    normalized = []
    valid_kinds = {choice.value for choice in ReservationCharge.Kind}
    for charge in charges or []:
        kind = charge.get("kind", ReservationCharge.Kind.OTHER)
        if kind not in valid_kinds:
            raise ReservationValidationError(_("The extra charge type is invalid."))
        amount = Decimal(str(charge["amount"])).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if amount < 0:
            raise ReservationValidationError(_("The extra charge amount cannot be negative."))
        _validate_amounts(model=ReservationCharge, amount=amount)
        normalized.append((kind, amount))
    return normalized


class ReservationService:
    hold_minutes = 20

    @staticmethod
    def _ensure_editable(reservation):

        if reservation.status != Reservation.Status.PAYMENT_PENDING:
            raise ReservationValidationError(_("This reservation can no longer be modified."))
        if reservation.expires_at <= timezone.now():
            raise ReservationValidationError(_("The reservation hold has expired."))

    @classmethod
    def _recalculate(cls, reservation):


        charges_total = sum((charge.amount for charge in reservation.charges.all()), Decimal("0.00"))
        total = (reservation.subtotal + reservation.cleaning_fee + charges_total - reservation.discount_amount).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        if total < 0:
            raise ReservationValidationError(_("The reservation total cannot be negative."))
        _validate_amounts(total=total)
        reservation.total = total
        reservation.tax_amount = included_tax_amount(total, reservation.tax_rate)
        reservation.points_earned = max(round(float(total) * settings.WYNWOOD_POINTS_RATE), 0)
        reservation.save(update_fields=("total", "tax_amount", "points_earned", "updated_at"))
        return reservation

    @classmethod
    @transaction.atomic
    def add_service(cls, *, reservation, kind, amount, details=None):
        reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
        cls._ensure_editable(reservation)
        valid_kinds = {choice.value for choice in ReservationCharge.Kind}
        if kind not in valid_kinds:
            raise ReservationValidationError(_("The extra charge type is invalid."))
        amount = Decimal(str(amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if amount < 0:
            raise ReservationValidationError(_("The reservation total cannot be negative."))
        _validate_amounts(model=ReservationCharge, amount=amount)
        reservation.charges.filter(kind=kind).delete()
        ReservationCharge.objects.create(reservation=reservation, kind=kind, amount=amount, details=details or {})
        return cls._recalculate(reservation)

    @classmethod
    @transaction.atomic
    def remove_service(cls, *, reservation, kind):
        reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
        cls._ensure_editable(reservation)
        reservation.charges.filter(kind=kind).delete()
        return cls._recalculate(reservation)

    @classmethod
    @transaction.atomic
    def update_stay(cls, *, reservation, check_in, check_out, guests, booking_type="daily", selected_services=None):
        reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
        cls._ensure_editable(reservation)
        if check_in < timezone.localdate() or check_out <= check_in:
            raise ReservationValidationError(_("The selected dates are invalid."))
        nights = (check_out - check_in).days
        if nights > 32767:
            raise ReservationValidationError(_("Choose a shorter stay."))
        if booking_type == Reservation.BookingType.MONTHLY and nights < 30:
            raise ReservationValidationError(_("Monthly stays require a minimum of 30 nights."))

        property = Property.objects.select_for_update().get(pk=reservation.property_id, is_active=True)
        if guests < 1 or guests > property.max_guests:
            raise ReservationValidationError(_("The number of guests is invalid."))
        now = timezone.now()
        Reservation.objects.filter(
            property=property,
            status=Reservation.Status.PAYMENT_PENDING,
            expires_at__lte=now,
        ).exclude(pk=reservation.pk).update(status=Reservation.Status.EXPIRED)
        conflict = Reservation.objects.filter(
            property=property,
            status__in=Reservation.blocking_statuses(),
            check_in__lt=check_out,
            check_out__gt=check_in,
        ).exclude(pk=reservation.pk).exists()
        if conflict:
            raise PropertyUnavailable(_("Those dates are no longer available."))

        if booking_type == Reservation.BookingType.MONTHLY:
            monthly_rate = property.effective_price_per_month
            subtotal = ((monthly_rate / Decimal("30")) * Decimal(nights)).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
            nightly_rate = (subtotal / Decimal(nights)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        else:
            booking_type = Reservation.BookingType.DAILY
            monthly_rate = None
            nightly_rate = property.price_per_night
            subtotal = (nightly_rate * nights).quantize(Decimal("0.01"), ROUND_HALF_UP)

        dates_changed = reservation.check_in != check_in or reservation.check_out != check_out
        services = list(get_services())
        service_kinds = {service.key: service.kind for service in services}
        requested_keys = set(selected_services or [])
        selected_keys = [service.key for service in services if service.key in requested_keys]
        selected_kinds = {service_kinds[key] for key in selected_keys}
        reservation.charges.filter(
            kind__in=set(service_kinds.values()) - selected_kinds
        ).delete()
        if dates_changed:
            reservation.charges.filter(kind__in=ServiceCatalog.configuration_kinds.values()).delete()

        _validate_amounts(subtotal=subtotal)
        reservation.check_in = check_in
        reservation.check_out = check_out
        reservation.guests = guests
        reservation.booking_type = booking_type
        reservation.nightly_rate = nightly_rate
        reservation.monthly_rate = monthly_rate
        reservation.nights = nights
        reservation.subtotal = subtotal
        reservation.cleaning_fee = property.cleaning_fee
        reservation.save(
            update_fields=(
                "check_in", "check_out", "guests", "booking_type", "nightly_rate", "monthly_rate",
                "nights", "subtotal", "cleaning_fee", "updated_at",
            )
        )

        for service in services:
            if service.key not in selected_keys or reservation.charges.filter(kind=service.kind).exists():
                continue
            amount = service.starting_price * (nights if service.detail == "crib" else 1)
            _validate_amounts(model=ReservationCharge, amount=amount)
            ReservationCharge.objects.create(
                reservation=reservation,
                kind=service.kind,
                amount=amount,
                details={"configured": False},
            )

        return cls._recalculate(reservation)

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        user,
        property_id,
        check_in,
        check_out,
        guests,
        language_code="es",
        charges=None,
        discount=Decimal("0"),
        booking_type="daily",
    ):
        if check_in < timezone.localdate() or check_out <= check_in:
            raise ReservationValidationError(_("The selected dates are invalid."))
        nights = (check_out - check_in).days
        if nights > 32767:
            raise ReservationValidationError(_("Choose a shorter stay."))
        if booking_type == Reservation.BookingType.MONTHLY:
            if nights < 30:
                raise ReservationValidationError(_("Monthly stays require a minimum of 30 nights."))
        property = (
            Property.objects.select_for_update()
            .select_related("destination")
            .get(pk=property_id, is_active=True)
        )
        if guests < 1 or guests > property.max_guests:
            raise ReservationValidationError(_("The number of guests is invalid."))
        normalized_charges = _normalize_charges(charges)
        now = timezone.now()
        Reservation.objects.filter(
            property=property,
            status=Reservation.Status.PAYMENT_PENDING,
            expires_at__lte=now,
        ).update(status=Reservation.Status.EXPIRED)
        conflict = Reservation.objects.filter(
            property=property,
            status__in=Reservation.blocking_statuses(),
            check_in__lt=check_out,
            check_out__gt=check_in,
        ).exists()
        if conflict:
            raise PropertyUnavailable(_("Those dates are no longer available."))
        if booking_type == Reservation.BookingType.MONTHLY:
            monthly_rate = property.effective_price_per_month
            subtotal = ((monthly_rate / Decimal("30")) * Decimal(nights)).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
            nightly_rate = (subtotal / Decimal(nights)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        else:
            booking_type = Reservation.BookingType.DAILY
            monthly_rate = None
            nightly_rate = property.price_per_night
            subtotal = (property.price_per_night * nights).quantize(Decimal("0.01"), ROUND_HALF_UP)
        charges_total = sum((amount for _, amount in normalized_charges), Decimal("0.00"))
        discount_amount = Decimal(str(discount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if discount_amount < 0:
            raise ReservationValidationError(_("The discount cannot be negative."))
        total = (subtotal + property.cleaning_fee + charges_total - discount_amount).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        if total < 0:
            raise ReservationValidationError(_("The reservation total cannot be negative."))


        _validate_amounts(subtotal=subtotal, total=total)
        tax_rate = resolve_tax_rate(property)
        tax_amount = included_tax_amount(total, tax_rate)
        points = round(float(total) * settings.WYNWOOD_POINTS_RATE)
        try:
            reservation = Reservation.objects.create(
                user=user,
                property=property,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                language_code=language_code,
                booking_type=booking_type,
                nightly_rate=nightly_rate,
                monthly_rate=monthly_rate,
                nights=nights,
                subtotal=subtotal,
                cleaning_fee=property.cleaning_fee,
                discount_amount=discount_amount,
                currency=settings.BOOKING_CURRENCY,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total=total,
                points_earned=max(points, 0),
                expires_at=now + timedelta(minutes=cls.hold_minutes),
            )
        except IntegrityError as error:
            raise PropertyUnavailable(_("Those dates are no longer available.")) from error
        ReservationCharge.objects.bulk_create(
            [
                ReservationCharge(reservation=reservation, kind=kind, amount=amount)
                for kind, amount in normalized_charges
            ]
        )
        return reservation
