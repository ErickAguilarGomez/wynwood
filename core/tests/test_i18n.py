from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from bookings.models import Reservation
from properties.models import Amenity, Destination, Property, PropertyImage


class LanguageTests(TestCase):
    def test_spanish_and_english_interface(self):
        spanish = self.client.get(reverse("core:home"), HTTP_ACCEPT_LANGUAGE="es")
        self.assertContains(spanish, "Propiedades destacadas")
        self.client.post(reverse("set_language"), {"language": "en", "next": "/"})
        english = self.client.get(reverse("core:home"))
        self.assertContains(english, "Featured homes")

    def test_seeded_home_renders(self):
        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            call_command("seed_demo", verbosity=0)
            response = self.client.get(reverse("core:home"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Gran Vía Skyline")
            images = PropertyImage.objects.all()
            self.assertTrue(images.exists())
            self.assertTrue(all(image.image.storage.exists(image.image.name) for image in images))

            counts = (
                Destination.objects.count(),
                Amenity.objects.count(),
                Property.objects.count(),
                images.count(),
                Reservation.objects.count(),
            )
            call_command("seed_demo", "--if-empty", verbosity=0)
            self.assertEqual(Property.objects.count(), counts[2])
            call_command("seed_demo", verbosity=0)
            self.assertEqual(
                counts,
                (
                    Destination.objects.count(),
                    Amenity.objects.count(),
                    Property.objects.count(),
                    PropertyImage.objects.count(),
                    Reservation.objects.count(),
                ),
            )

            old_names = [image.image.name for image in images]
            with self.captureOnCommitCallbacks(execute=True):
                call_command("seed_demo", "--refresh-images", verbosity=0)
            refreshed_images = PropertyImage.objects.all()
            self.assertEqual(refreshed_images.count(), counts[3])
            self.assertTrue(all(image.image.storage.exists(image.image.name) for image in refreshed_images))
            self.assertFalse(any(refreshed_images.first().image.storage.exists(name) for name in old_names))


class LanguageNavigationTests(TestCase):
    def test_switching_language_keeps_search_filters_and_translates_the_banner(self):
        from core.tests.factories import create_property, future_dates

        property = create_property()
        check_in, check_out = future_dates()
        target = f"/search/?country=ES&destination={property.destination_id}&check_in={check_in}&check_out={check_out}&guests=3"
        for language, heading, expected_banner in (
            ("en", "Central Home", "Hurry!"),
            ("es", "Casa Central", "Solo quedan"),
        ):
            with self.subTest(language=language):
                response = self.client.post(reverse("set_language"), {"language": language, "next": target})
                self.assertEqual(response.url, target)
                results = self.client.get(target)
                self.assertContains(results, heading)
                home = self.client.get(reverse("core:home"))
                self.assertContains(home, expected_banner)
                if language == "es":
                    self.assertNotContains(home, "Hurry!")
                self.assertEqual(home.context["LANGUAGE_CODE"], language)


class SeedCatalogTests(TestCase):
    def test_seed_initializes_all_catalogs_and_repairs_missing_entries(self):
        from bookings.models import ServiceCatalog
        from properties.models import Airport, Country

        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            call_command("seed_demo", verbosity=0)
            self.assertEqual(Country.objects.count(), 10)
            self.assertEqual(Airport.objects.count(), 18)
            self.assertEqual(ServiceCatalog.objects.count(), 9)
            self.assertEqual(Property.objects.count(), 20)
            self.assertEqual(PropertyImage.objects.count(), 80)
            self.assertEqual(Country.objects.get(code="ES").tax_rate, Decimal("0.21"))
            counts = (Property.objects.count(), Reservation.objects.count(), PropertyImage.objects.count())
            country = Country.objects.get(code="ES")
            country.name_en = "Custom Spain"
            country.save(update_fields=("name_en",))
            ServiceCatalog.objects.filter(key="flexible-checkin").update(price="39.75")
            ServiceCatalog.objects.filter(key="breakfast").delete()
            property = Property.objects.get(slug="gran-via-skyline")
            property.title_en = "Edited name"
            property.save(update_fields=("title_en",))
            call_command("seed_demo", verbosity=0)
            self.assertEqual(counts, (Property.objects.count(), Reservation.objects.count(), PropertyImage.objects.count()))
            country.refresh_from_db()
            self.assertEqual(country.name_en, "Custom Spain")
            self.assertEqual(ServiceCatalog.objects.get(key="flexible-checkin").price, Decimal("39.75"))
            self.assertTrue(ServiceCatalog.objects.filter(key="breakfast").exists())
            self.assertEqual(Property.objects.get(slug="gran-via-skyline").pk, property.pk)
            Country.objects.all().delete()
            ServiceCatalog.objects.all().delete()
            call_command("seed_demo", "--if-empty", verbosity=0)
            self.assertEqual(Country.objects.count(), 10)
            self.assertEqual(ServiceCatalog.objects.count(), 9)
            self.assertEqual(Property.objects.count(), 20)

    def test_refreshing_remote_images_preserves_cloudinary_originals(self):
        storage = PropertyImage._meta.get_field("image").storage
        storages = {"default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"}}
        with override_settings(STORAGES=storages), patch.object(storage, "delete") as delete:
            call_command("seed_demo", verbosity=0)
            before = set(PropertyImage.objects.values_list("image", flat=True))
            self.assertTrue(before)
            with self.captureOnCommitCallbacks(execute=True):
                call_command("seed_demo", "--refresh-images", verbosity=0)
            after = set(PropertyImage.objects.values_list("image", flat=True))
        self.assertEqual(before, after)
        delete.assert_not_called()

    def test_repeated_seed_does_not_reschedule_an_existing_demo_reservation(self):
        from datetime import timedelta

        from django.utils import timezone

        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            call_command("seed_demo", verbosity=0)
            reservation = Reservation.objects.get(user__email="demo@wynwoodhouse.com")
            original = (reservation.check_in, reservation.check_out)
            with patch("core.management.commands.seed_demo.timezone.localdate", return_value=timezone.localdate() + timedelta(days=1)):
                call_command("seed_demo", verbosity=0)
            reservation.refresh_from_db()
            self.assertEqual((reservation.check_in, reservation.check_out), original)
