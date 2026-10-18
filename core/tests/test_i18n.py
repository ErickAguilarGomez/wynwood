from tempfile import TemporaryDirectory

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
