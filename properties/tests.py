import io
import tempfile
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from bookings.models import Reservation
from core.tests.factories import create_property, create_user, future_dates

from .models import Amenity, PropertyImage


class PropertySearchTests(TestCase):
    def setUp(self):
        self.property = create_property()
        self.check_in, self.check_out = future_dates()

    def search(self, **overrides):
        query = {
            "destination": self.property.destination_id,
            "check_in": self.check_in,
            "check_out": self.check_out,
            "guests": 2,
        }
        query.update(overrides)
        return self.client.get(reverse("properties:results"), query)

    def test_returns_available_property(self):
        response = self.search()
        self.assertContains(response, self.property.title_es)

    def test_excludes_property_with_overlapping_reservation(self):
        Reservation.objects.create(
            user=create_user(),
            property=self.property,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
            nightly_rate=100,
            nights=3,
            subtotal=300,
            cleaning_fee=25,
            total=325,
            expires_at=timezone.now() + timedelta(minutes=20),
        )
        response = self.search()
        self.assertNotContains(response, self.property.title_es)

    def test_ignores_expired_pending_reservation(self):
        Reservation.objects.create(
            user=create_user(),
            property=self.property,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
            nightly_rate=100,
            nights=3,
            subtotal=300,
            cleaning_fee=25,
            total=325,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        response = self.search()
        self.assertContains(response, self.property.title_es)

    def test_rejects_past_dates(self):
        response = self.search(check_in="2020-01-01", check_out="2020-01-03")
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertContains(response, "La fecha de llegada no puede estar en el pasado.")

    def test_filters_by_country_and_district(self):
        response = self.search(country="España", district="Centro")
        self.assertContains(response, self.property.title_es)

        response = self.search(country="Perú")
        self.assertNotContains(response, self.property.title_es)

    def test_filters_by_price_and_amenity(self):
        amenity = Amenity.objects.create(name_es="Ascensor", name_en="Elevator")
        self.property.amenities.add(amenity)

        response = self.search(min_price="90", max_price="110", amenities=[amenity.pk])
        self.assertContains(response, self.property.title_es)

        response = self.search(min_price="101")
        self.assertNotContains(response, self.property.title_es)

    def test_returns_partial_list_for_reactive_request(self):
        response = self.search(partial="1")
        self.assertTemplateUsed(response, "properties/_results_list.html")
        self.assertContains(response, self.property.title_es)

    def test_rejects_oversized_destination_query_without_server_error(self):
        response = self.client.get(reverse("properties:results"), {"destination": "9" * 5000})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_invalid_price_filter_does_not_return_unfiltered_properties(self):
        response = self.search(min_price="not-a-price")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_requires_both_search_dates(self):
        response = self.search(check_out="")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 0)


class PropertyImageTests(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_converts_uploaded_image_to_webp_and_limits_size(self):
        property = create_property()
        source = Image.new("RGB", (1600, 1400), "#a98b72")
        data = io.BytesIO()
        source.save(data, "PNG")
        upload = SimpleUploadedFile("room.png", data.getvalue(), content_type="image/png")
        image = PropertyImage.objects.create(
            property=property,
            image=upload,
            alt_es="Interior",
            alt_en="Interior",
        )
        self.assertTrue(image.image.name.endswith(".webp"))
        self.assertLessEqual(image.width, 1200)
        self.assertLessEqual(image.height, 1200)

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_rejects_oversized_image_without_form_validation(self):
        property = create_property()
        upload = SimpleUploadedFile("large.webp", b"0" * (12 * 1024 * 1024 + 1), content_type="image/webp")
        image = PropertyImage(property=property, image=upload, alt_es="Interior", alt_en="Interior")
        with self.assertRaises(ValidationError):
            image.save()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_resizes_uploaded_webp_images(self):
        property = create_property()
        source = Image.new("RGB", (1600, 1400), "#a98b72")
        data = io.BytesIO()
        source.save(data, "WEBP")
        upload = SimpleUploadedFile("room.webp", data.getvalue(), content_type="image/webp")
        image = PropertyImage.objects.create(
            property=property,
            image=upload,
            alt_es="Interior",
            alt_en="Interior",
        )
        self.assertLessEqual(image.width, 1200)
        self.assertLessEqual(image.height, 1200)
