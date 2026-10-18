import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields.ranges import RangeOperators
from django.db import models
from django.db.models import F, Func, Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


def default_currency():
    return settings.BOOKING_CURRENCY


class Reservation(models.Model):
    class Status(models.TextChoices):
        PAYMENT_PENDING = "payment_pending", _("Payment pending")
        CONFIRMED = "confirmed", _("Confirmed")
        CANCELLED = "cancelled", _("Cancelled")
        EXPIRED = "expired", _("Expired")
        PAYMENT_FAILED = "payment_failed", _("Payment failed")

    class BookingType(models.TextChoices):
        DAILY = "daily", _("Daily")
        MONTHLY = "monthly", _("Monthly")

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservations")
    property = models.ForeignKey("properties.Property", on_delete=models.PROTECT, related_name="reservations")
    check_in = models.DateField()
    check_out = models.DateField()
    guests = models.PositiveSmallIntegerField()
    language_code = models.CharField(max_length=2, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PAYMENT_PENDING)
    booking_type = models.CharField(max_length=10, choices=BookingType.choices, default=BookingType.DAILY)
    nightly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    nights = models.PositiveSmallIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    cleaning_fee = models.DecimalField(max_digits=10, decimal_places=2)

    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, default=default_currency)


    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    points_earned = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("property", "check_in", "check_out"), name="reservation_dates_idx"),
            models.Index(fields=("status", "expires_at"), name="reservation_status_expiry_idx"),
            models.Index(fields=("user", "created_at"), name="reservation_user_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(check_out__gt=F("check_in")), name="reservation_valid_dates"),
            models.CheckConstraint(condition=Q(guests__gte=1), name="reservation_guests_positive"),
            models.CheckConstraint(condition=Q(total__gte=0), name="reservation_total_nonnegative"),
            models.CheckConstraint(condition=Q(tax_amount__gte=0), name="reservation_tax_nonnegative"),
            models.CheckConstraint(condition=Q(discount_amount__gte=0), name="reservation_discount_nonnegative"),
            ExclusionConstraint(
                name="reservation_no_overlap",
                expressions=[
                    (F("property"), RangeOperators.EQUAL),
                    (Func(F("check_in"), F("check_out"), function="DATERANGE"), RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=("payment_pending", "confirmed")),
            ),
        ]

    def __str__(self):
        return str(self.public_id)

    def get_absolute_url(self):
        return reverse("bookings:confirmation", kwargs={"public_id": self.public_id})

    @classmethod
    def blocking_statuses(cls):
        return (cls.Status.PAYMENT_PENDING, cls.Status.CONFIRMED)


class ReservationCharge(models.Model):






    class Kind(models.TextChoices):
        LATE_CHECK_IN = "late_check_in", _("Late check-in")
        EARLY_CHECK_IN = "early_check_in", _("Early check-in")
        PET_FEE = "pet_fee", _("Pet fee")
        EXTRA_GUEST = "extra_guest", _("Extra guest")
        TRANSPORT = "transport", _("Transport service")
        GROCERY = "grocery", _("Grocery pack")
        CRIB = "crib", _("Baby crib")
        OTHER = "other", _("Other")

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="charges")
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.OTHER)
    amount = models.DecimalField(max_digits=10, decimal_places=2)


    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        indexes = [models.Index(fields=("reservation", "kind"), name="charge_reservation_kind_idx")]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.amount}"
