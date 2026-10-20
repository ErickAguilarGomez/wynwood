import io
import tempfile
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
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


class SearchRegressionTests(TestCase):
    def setUp(self):
        self.property = create_property()

    def test_unfiltered_search_shows_available_properties(self):
        response = self.client.get(reverse("properties:results"))
        self.assertContains(response, self.property.title_es)

    def test_country_search_accepts_both_languages_and_country_codes(self):
        for country in ("ES", "España", "Spain"):
            with self.subTest(country=country):
                response = self.client.get(reverse("properties:results"), {"country": country})
                self.assertContains(response, self.property.title_es)
                response = self.client.get(reverse("properties:location_cities"), {"country": country})
                self.assertEqual(response.json()["cities"][0]["id"], self.property.destination_id)

    def test_malformed_dates_and_numeric_identifiers_do_not_raise_server_errors(self):
        self.client.force_login(create_user())
        cases = [
            (reverse("properties:results"), {"destination": "9" * 100}),
            (reverse("properties:results"), {"check_in": "2027-02-30", "check_out": "2027-03-02"}),
            (self.property.get_absolute_url(), {"check_in": "2027-02-30"}),
            (reverse("properties:location_districts"), {"destination": "9" * 100}),
            (reverse("bookings:checkout", kwargs={"slug": self.property.slug}), {"reservation_id": "invalid"}),
            (reverse("bookings:checkout", kwargs={"slug": self.property.slug}), {"check_in": "2027-02-30", "email": "guest@example.com", "phone": "987654321"}),
        ]
        for url, data in cases:
            with self.subTest(url=url, data=data):
                self.assertIn(self.client.get(url, data).status_code, (200, 302, 404))


class PropertyImageIntegrityTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.media_settings = override_settings(MEDIA_ROOT=self.directory.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.property = create_property()

    def test_disguised_or_corrupt_webp_uploads_are_rejected(self):
        for content in (b"<svg onload=alert(1)></svg>", b"RIFF0000WEBPVP8 corrupted"):
            with self.subTest(content=content[:4]):
                upload = SimpleUploadedFile("room.webp", content, content_type="image/webp")
                with self.assertRaises(ValidationError):
                    PropertyImage.objects.create(property=self.property, image=upload, alt_es="Interior", alt_en="Interior")
        self.assertEqual(PropertyImage.objects.count(), 0)

    def test_exif_rotation_is_applied_before_resizing(self):
        source = Image.new("RGB", (1600, 800), "blue")
        exif = Image.Exif()
        exif[274] = 6
        data = io.BytesIO()
        source.save(data, "JPEG", exif=exif)
        image = PropertyImage.objects.create(
            property=self.property, image=SimpleUploadedFile("room.jpg", data.getvalue()), alt_es="Interior", alt_en="Interior"
        )
        self.assertEqual((image.width, image.height), (600, 1200))
        with image.image.open("rb") as stream:
            result = Image.open(stream)
            self.assertEqual(result.format, "WEBP")
            result.verify()

    def test_editing_alt_text_does_not_replace_an_existing_image(self):
        data = io.BytesIO()
        Image.new("RGB", (900, 600), "red").save(data, "WEBP")
        image = PropertyImage.objects.create(
            property=self.property, image=SimpleUploadedFile("room.webp", data.getvalue()), alt_es="Interior", alt_en="Interior"
        )
        name = image.image.name
        image.image.open("rb")
        image.alt_es = "Habitación"
        image.save(update_fields=("alt_es",))
        image.refresh_from_db()
        self.assertEqual(image.image.name, name)
        self.assertEqual(image.alt_es, "Habitación")


class ExhaustiveSearchTests(TestCase):
    def setUp(self):
        from .models import Destination

        self.wifi = Amenity.objects.create(name_es="Wifi", name_en="Wifi")
        self.parking = Amenity.objects.create(name_es="Estacionamiento", name_en="Parking")
        self.central = create_property(slug="exact-centro")
        self.central.amenities.set([self.wifi, self.parking])
        self.historic = create_property(slug="historic-centro", district="Centro Histórico", price_per_night="175.25", max_guests=2)
        self.historic.amenities.add(self.wifi)
        lima = Destination.objects.create(name_es="Lima", name_en="Lima", slug="lima", country_code="PE")
        self.coastal = create_property(slug="coastal-home", destination=lima, country="Perú", province="Lima", district="Miraflores", price_per_night="75.00", max_guests=6)
        self.url = reverse("properties:results")

    def ids(self, query):
        response = self.client.get(self.url, query)
        self.assertEqual(response.status_code, 200)
        return {item.pk for item in response.context["properties"]}

    def test_combined_location_capacity_price_and_amenity_filters(self):
        all_ids = {self.central.pk, self.historic.pk, self.coastal.pk}
        madrid = {self.central.pk, self.historic.pk}
        cases = [
            ({}, all_ids), ({"country": "Spain"}, madrid), ({"country": "España"}, madrid),
            ({"country": "ES"}, madrid), ({"country": "PE"}, {self.coastal.pk}),
            ({"destination": self.central.destination_id}, madrid), ({"destination": "madrid"}, madrid),
            ({"district": "Centro"}, {self.central.pk}),
            ({"district": ["Centro", "Centro Histórico"]}, madrid),
            ({"province": "Lima"}, {self.coastal.pk}),
            ({"guests": 3}, {self.central.pk, self.coastal.pk}), ({"guests": 5}, {self.coastal.pk}),
            ({"min_price": "100", "max_price": "175.25"}, madrid),
            ({"min_price": "100.01"}, {self.historic.pk}), ({"max_price": "0"}, set()),
            ({"min_price": "175.25", "max_price": "175.25"}, {self.historic.pk}),
            ({"amenities": [self.wifi.pk, self.parking.pk]}, {self.central.pk}),
            ({"country": "ES", "guests": 3, "district": "Centro", "max_price": "100", "amenities": [self.wifi.pk]}, {self.central.pk}),
            ({"destination": "lima", "district": "Centro"}, set()),
        ]
        for query, expected in cases:
            with self.subTest(query=query):
                self.client = Client()
                self.assertEqual(self.ids(query), expected)

    def test_invalid_filters_fail_closed_without_server_errors(self):
        cases = [
            {"guests": value} for value in ("0", "-1", "51", "not-a-number", "9" * 100)
        ] + [
            {"min_price": value} for value in ("NaN", "Infinity", "-1", "9" * 100, "not-a-price")
        ] + [
            {"max_price": "1", "min_price": "2"}, {"destination": "9" * 100},
            {"amenities": "not-an-id"}, {"district": ["Centro"] * 21},
            {"check_in": "9999-12-31", "check_out": "2027-01-01"},
        ]
        for query in cases:
            with self.subTest(query=query):
                self.assertEqual(self.ids(query), set())

    def test_old_saved_dates_do_not_hide_all_search_results(self):
        session = self.client.session
        session["search_check_in"] = (timezone.localdate() - timedelta(days=2)).isoformat()
        session["search_check_out"] = (timezone.localdate() + timedelta(days=2)).isoformat()
        session.save()
        self.assertIn(self.central.pk, self.ids({}))
        self.assertNotIn("search_check_in", self.client.session)

    def test_explicitly_clearing_dates_removes_the_saved_availability_filter(self):
        check_in, check_out = future_dates()
        from bookings.services import ReservationService

        ReservationService.create(user=create_user(), property_id=self.central.pk, check_in=check_in, check_out=check_out, guests=2)
        self.assertNotIn(self.central.pk, self.ids({"check_in": check_in, "check_out": check_out}))
        self.assertIn(self.central.pk, self.ids({"check_in": "", "check_out": ""}))
        self.assertNotIn("search_check_in", self.client.session)

    def test_location_identifiers_handle_unicode_and_extreme_values(self):
        for value in ("²", "①", "9" * 5000, "9223372036854775808", "-1", "1.2"):
            with self.subTest(value=value[:30]):
                response = self.client.get(reverse("properties:location_districts"), {"destination": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["districts"], [])

    def test_pagination_preserves_filters_and_does_not_repeat_properties(self):
        for number in range(13):
            create_property(slug=f"page-property-{number}")
        query = {"country": "ES", "guests": 2}
        first = self.client.get(self.url, query)
        second = self.client.get(self.url, {**query, "page": 2, "partial": "1"})
        self.assertTemplateUsed(second, "properties/_results_list.html")
        first_ids = {item.pk for item in first.context["properties"]}
        second_ids = {item.pk for item in second.context["properties"]}
        self.assertFalse(first_ids & second_ids)
        self.assertEqual(len(first_ids | second_ids), 15)
        self.assertContains(first, "country=ES")
