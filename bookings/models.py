import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields.ranges import RangeOperators
from django.contrib.staticfiles.finders import find
from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, connections, models
from django.db.models import F, Func, Q
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _


def default_currency():
    return settings.BOOKING_CURRENCY


class ReservationOverlapConstraint(ExclusionConstraint):
    def deconstruct(self):
        _, args, kwargs = super().deconstruct()
        return "django.contrib.postgres.constraints.ExclusionConstraint", args, kwargs

    def validate(self, model, instance, exclude=None, using=DEFAULT_DB_ALIAS):
        if connections[using].vendor != "sqlite":
            return super().validate(model, instance, exclude=exclude, using=using)
        if exclude and {"property", "check_in", "check_out", "status"}.intersection(exclude):
            return
        if (
            instance.status not in model.blocking_statuses()
            or not instance.property_id
            or not instance.check_in
            or not instance.check_out
        ):
            return
        overlaps = model._default_manager.using(using).filter(
            property_id=instance.property_id,
            status__in=model.blocking_statuses(),
            check_in__lt=instance.check_out,
            check_out__gt=instance.check_in,
        ).exclude(pk=instance.pk)
        if overlaps.exists():
            raise ValidationError(self.get_violation_error_message(), code=self.violation_error_code)


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
            ReservationOverlapConstraint(
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


class ServiceCatalog(models.Model):
    configuration_kinds = {
        "flexible_checkin": ReservationCharge.Kind.EARLY_CHECK_IN,
        "transport": ReservationCharge.Kind.TRANSPORT,
        "groceries": ReservationCharge.Kind.GROCERY,
        "crib": ReservationCharge.Kind.CRIB,
    }

    class Category(models.TextChoices):
        SERVICE = "service", _("Service")
        VEHICLE = "vehicle", _("Vehicle")
        GROCERY = "grocery", _("Grocery pack")

    key = models.SlugField(max_length=48, primary_key=True)
    group_key = models.SlugField(max_length=48, blank=True, db_index=True)
    category = models.CharField(max_length=16, choices=Category.choices)
    kind = models.CharField(max_length=24, blank=True, choices=ReservationCharge.Kind.choices)
    name_es = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    description_es = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    detail_es = models.TextField(blank=True)
    detail_en = models.TextField(blank=True)
    detail_key = models.SlugField(max_length=32, blank=True)
    image = models.CharField(max_length=160, blank=True)
    checkout_image = models.CharField(max_length=160, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    secondary_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    passengers = models.PositiveSmallIntegerField(default=0)
    bags = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name_es")
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name="service_catalog_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(secondary_price__gte=0), name="service_catalog_secondary_nonnegative"),
        ]

    def __str__(self):
        return self.name_es

    def clean(self):
        super().clean()
        if self.category == self.Category.SERVICE and self.is_active:
            if self.detail_key not in self.configuration_kinds:
                raise ValidationError({
                    "detail_key": _("Select a supported service configuration before activating this service.")
                })
            if self.kind != self.configuration_kinds[self.detail_key]:
                raise ValidationError({
                    "kind": _("Choose the charge type that matches the service configuration.")
                })
            if ServiceCatalog.objects.filter(category=self.Category.SERVICE, kind=self.kind, is_active=True).exclude(
                pk=self.pk
            ).exists():
                raise ValidationError({"kind": _("An active service already uses this charge type.")})
            for field in ("image", "checkout_image"):
                image = getattr(self, field)
                if field == "image" or image:
                    asset = find(image) if image else None
                    if not asset or not Path(asset).is_file():
                        raise ValidationError({field: _("Select an existing image for this service.")})

    @property
    def name(self):
        return self.name_en if get_language() == "en" else self.name_es

    @property
    def description(self):
        return self.description_en if get_language() == "en" else self.description_es

    @property
    def detail_description(self):
        return self.detail_en if get_language() == "en" else self.detail_es

    @property
    def detail(self):
        return self.detail_key

    @property
    def base_price(self):
        return self.price

    @property
    def starting_price(self):
        if self.detail_key in {"transport", "groceries"}:
            category = self.Category.VEHICLE if self.detail_key == "transport" else self.Category.GROCERY
            price = ServiceCatalog.objects.filter(
                category=category, group_key=self.detail_key, is_active=True
            ).order_by("price").values_list("price", flat=True).first()
            if price is not None:
                return price
        return self.price

    @property
    def one_way_price(self):
        return self.price

    @property
    def round_trip_price(self):
        return self.secondary_price or self.price * 2

    @property
    def price_label(self):
        amount = self.starting_price
        currency = settings.BOOKING_CURRENCY
        if self.detail_key in {"transport", "groceries"}:
            return _("From %(currency)s %(amount)s") % {"currency": currency, "amount": f"{amount:.2f}"}
        if self.detail_key == "crib":
            return _("%(currency)s %(amount)s / night") % {"currency": currency, "amount": f"{amount:.2f}"}
        return f"{currency} {amount:.2f}"
