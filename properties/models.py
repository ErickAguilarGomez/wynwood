import builtins
import io
import uuid
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.finders import find
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps, UnidentifiedImageError

from .storage import PropertyImageStorage


def property_image_path(instance, filename):
    return f"properties/{instance.property_id}/{uuid.uuid4().hex}.webp"


def validate_image_size(image):
    if image.size > 12 * 1024 * 1024:
        raise ValidationError(_("Image files cannot exceed 12 MB."))


class Country(models.Model):
    code = models.CharField(max_length=2, primary_key=True)
    name_es = models.CharField(max_length=80)
    name_en = models.CharField(max_length=80)
    phone_prefix = models.CharField(max_length=5, blank=True)
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    home_image = models.CharField(max_length=160, blank=True)
    show_on_home = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name_es")

    def __str__(self):
        return self.name_es

    def clean(self):
        super().clean()
        if self.is_active and self.show_on_home:
            asset = find(self.home_image) if self.home_image else None
            if not asset or not Path(asset).is_file():
                raise ValidationError({"home_image": _("Select an existing destination image before showing it on the home page.")})

    @property
    def name(self):
        return self.name_en if get_language() == "en" else self.name_es


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
        country = Country.objects.filter(code=self.country_code.upper()).first()
        return country.name if country else self.country_code


class Airport(models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="airports")
    code = models.CharField(max_length=8)
    name_es = models.CharField(max_length=160)
    name_en = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name_es")
        constraints = [models.UniqueConstraint(fields=("destination", "code"), name="unique_destination_airport")]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def name(self):
        return self.name_en if get_language() == "en" else self.name_es


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
    class Brand(models.TextChoices):
        STANDARD = "standard", _("Wynwood House")
        COLLECTION = "collection", _("The Collection")
        CASA_WYNWOOD = "casa_wynwood", _("Casa Wynwood")

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
    brand = models.CharField(max_length=20, choices=Brand.choices, default=Brand.STANDARD)
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
            country = Country.objects.filter(code=self.destination.country_code.upper()).first()
            self.country = country.name_es if country else self.destination.country_code
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
        return self.images.all().first()


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(
        upload_to=property_image_path,
        storage=PropertyImageStorage(),
        width_field="width",
        height_field="height",
        validators=(validate_image_size,),
    )
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
        if uploaded_file and not self.image._committed:
            validate_image_size(uploaded_file)
            try:
                source = Image.open(uploaded_file)
                if source.width * source.height > 40_000_000:
                    raise ValidationError({"image": _("Image dimensions are too large to process safely.")})
                source.verify()
                uploaded_file.seek(0)
                source = ImageOps.exif_transpose(Image.open(uploaded_file))
                source.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                if source.mode not in ("RGB", "RGBA"):
                    source = source.convert("RGBA" if "transparency" in source.info else "RGB")
                output = io.BytesIO()
                source.save(output, format="WEBP", quality=84, method=6)
                name = f"{Path(self.image.name).stem}.webp"
                self.image = ContentFile(output.getvalue(), name=name)
            except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
                raise ValidationError({"image": _("The uploaded file is not a valid image.")}) from error
        super().save(*args, **kwargs)

    @builtins.property
    def alt(self):
        return self.alt_en if get_language() == "en" else self.alt_es
