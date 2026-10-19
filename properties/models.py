import builtins
import io
import uuid
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError


def property_image_path(instance, filename):
    return f"properties/{instance.property_id}/{uuid.uuid4().hex}.webp"


COUNTRY_NAMES = {
    "AR": ("Argentina", "Argentina"),
    "CL": ("Chile", "Chile"),
    "CO": ("Colombia", "Colombia"),
    "EC": ("Ecuador", "Ecuador"),
    "ES": ("España", "Spain"),
    "IT": ("Italy", "Italy"),
    "MX": ("México", "Mexico"),
    "PA": ("Panamá", "Panama"),
    "PE": ("Perú", "Peru"),
    "US": ("Estados Unidos", "United States"),
}


def validate_image_size(image):
    if image.size > 12 * 1024 * 1024:
        raise ValidationError(_("Image files cannot exceed 12 MB."))


class Destination(models.Model):
    name_es = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    country_code = models.CharField(max_length=2, default="ES")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name_es")

    def __str__(self):
        return self.name_es

    @property
    def name(self):
        return self.name_en if get_language() == "en" else self.name_es

    @property
    def country(self):
        spanish, english = COUNTRY_NAMES.get(self.country_code.upper(), (self.country_code, self.country_code))
        return english if get_language() == "en" else spanish


class Amenity(models.Model):
    name_es = models.CharField(max_length=80)
    name_en = models.CharField(max_length=80)
    icon = models.CharField(max_length=40, default="check")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name_es")

    def __str__(self):
        return self.name_es

    @property
    def name(self):
        return self.name_en if get_language() == "en" else self.name_es


class Property(models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.PROTECT, related_name="properties")
    amenities = models.ManyToManyField(Amenity, related_name="properties", blank=True)
    slug = models.SlugField(unique=True)
    title_es = models.CharField(max_length=180)
    title_en = models.CharField(max_length=180)
    summary_es = models.CharField(max_length=240)
    summary_en = models.CharField(max_length=240)
    description_es = models.TextField()
    description_en = models.TextField()
    country = models.CharField(max_length=120, blank=True, default="")
    province = models.CharField(max_length=120, blank=True, default="")
    district = models.CharField(max_length=120, blank=True, default="")
    address = models.CharField(max_length=240)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    price_per_month = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    cleaning_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    max_guests = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    bedrooms = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    beds = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1, default=1, validators=[MinValueValidator(0.5)])
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_featured", "title_es")
        indexes = [
            models.Index(fields=("destination", "is_active"), name="prop_dest_active_idx"),
            models.Index(fields=("country", "is_active"), name="prop_country_active_idx"),
            models.Index(fields=("district", "is_active"), name="prop_district_active_idx"),
            models.Index(fields=("is_featured", "is_active"), name="prop_featured_active_idx"),
            models.Index(fields=("price_per_night", "max_guests"), name="prop_price_guests_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(price_per_night__gte=0), name="property_price_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(price_per_month__isnull=True) | models.Q(price_per_month__gte=0),
                name="property_price_month_nonnegative",
            ),
            models.CheckConstraint(condition=models.Q(cleaning_fee__gte=0), name="property_cleaning_nonnegative"),
            models.CheckConstraint(condition=models.Q(max_guests__gte=1), name="property_guests_positive"),
        ]

    def __str__(self):
        return self.title_es

    def save(self, *args, **kwargs):
        if not self.country and self.destination:
            self.country = COUNTRY_NAMES.get(self.destination.country_code.upper(), (self.destination.country_code,))[0]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("properties:detail", kwargs={"slug": self.slug})

    @property
    def title(self):
        return self.title_en if get_language() == "en" else self.title_es

    @property
    def summary(self):
        return self.summary_en if get_language() == "en" else self.summary_es

    @property
    def description(self):
        return self.description_en if get_language() == "en" else self.description_es

    @property
    def effective_price_per_month(self):
        if self.price_per_month is not None:
            return self.price_per_month
        return (self.price_per_night * Decimal("25.00")).quantize(Decimal("0.01"))

    @property
    def primary_image(self):
        return self.images.order_by("sort_order", "id").first()


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=property_image_path, width_field="width", height_field="height", validators=(validate_image_size,))
    alt_es = models.CharField(max_length=180)
    alt_en = models.CharField(max_length=180)
    width = models.PositiveIntegerField(default=0, editable=False)
    height = models.PositiveIntegerField(default=0, editable=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [models.UniqueConstraint(fields=("property", "sort_order"), name="unique_property_image_order")]

    def __str__(self):
        return f"{self.property} · {self.sort_order}"

    def save(self, *args, **kwargs):
        uploaded_file = getattr(self.image, "_file", None)
        if uploaded_file:
            validate_image_size(uploaded_file)
            try:
                source = Image.open(uploaded_file)
                source.verify()
                uploaded_file.seek(0)
                source = Image.open(uploaded_file)
                source.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                if source.mode not in ("RGB", "RGBA"):
                    source = source.convert("RGB")
                output = io.BytesIO()
                source.save(output, format="WEBP", quality=84, method=6)
                name = f"{Path(self.image.name).stem}.webp"
                self.image = ContentFile(output.getvalue(), name=name)
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
                raise ValidationError({"image": _("The uploaded file is not a valid image.")}) from error
        super().save(*args, **kwargs)

    @builtins.property
    def alt(self):
        return self.alt_en if get_language() == "en" else self.alt_es
