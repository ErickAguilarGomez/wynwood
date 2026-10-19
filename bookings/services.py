from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from properties.models import Property

from .additional_services import GROCERY_PACKS, SERVICES, SERVICES_BY_KEY, crib_quote, grocery_quote, transport_quote
from .models import Reservation, ReservationCharge
from .tax import included_tax_amount, resolve_tax_rate


class PropertyUnavailable(Exception):
    pass


class ReservationValidationError(Exception):
    pass


def _normalize_charges(charges):

    normalized = []
    valid_kinds = {choice.value for choice in ReservationCharge.Kind}
    for charge in charges or []:
        kind = charge.get("kind", ReservationCharge.Kind.OTHER)
        if kind not in valid_kinds:
            raise ReservationValidationError(_("The extra charge type is invalid."))
        amount = Decimal(str(charge["amount"])).quantize(Decimal("0.01"), ROUND_HALF_UP)
        normalized.append((kind, amount))
    return normalized


class ReservationService:
    hold_minutes = 20

    @staticmethod
    def _expire_own_overlapping_holds(*, user, property, check_in, check_out, exclude_id=None, now=None):
        reservations = Reservation.objects.filter(
            user=user,
            property=property,
            status=Reservation.Status.PAYMENT_PENDING,
            expires_at__gt=now or timezone.now(),
            check_in__lt=check_out,
            check_out__gt=check_in,
        )
        if exclude_id is not None:
            reservations = reservations.exclude(pk=exclude_id)
        reservations.update(status=Reservation.Status.EXPIRED)

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
        cls._expire_own_overlapping_holds(
            user=reservation.user,
            property=property,
            check_in=check_in,
            check_out=check_out,
            exclude_id=reservation.pk,
            now=now,
        )
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
        service_kinds = {service.key: service.kind for service in SERVICES}
        requested_keys = set(selected_services or [])
        selected_keys = [service.key for service in SERVICES if service.key in requested_keys]
        selected_kinds = {service_kinds[key] for key in selected_keys}
        reservation.charges.filter(
            kind__in=set(service_kinds.values()) - selected_kinds
        ).delete()
        if dates_changed:
            reservation.charges.filter(kind__in=selected_kinds).delete()

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

        for key in selected_keys:
            service = SERVICES_BY_KEY[key]
            if reservation.charges.filter(kind=service.kind).exists():
                continue
            if service.detail == "transport":
                amount, _ = transport_quote(trip_type="one_way", vehicle_key="suv", quantity=1)
            elif service.detail == "groceries":
                amount, _ = grocery_quote(pack_key=GROCERY_PACKS[0].key)
            elif service.detail == "crib":
                amount, _ = crib_quote(quantity=1)
                amount *= nights
            else:
                amount = service.base_price
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
        cls._expire_own_overlapping_holds(
            user=user,
            property=property,
            check_in=check_in,
            check_out=check_out,
            now=now,
        )
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
