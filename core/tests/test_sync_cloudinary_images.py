import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.tests.factories import create_property
from properties.models import PropertyImage


class SyncCloudinaryImagesTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        manifest_dir = self.base_dir / "core"
        manifest_dir.mkdir()
        self.image = {
            "sort_order": 0,
            "name": "media/properties/central/valid.webp",
            "url": "https://res.cloudinary.com/test-cloud/image/upload/v1/media/properties/central/valid.webp",
            "alt_es": "Interior",
            "alt_en": "Interior",
            "width": 1200,
            "height": 800,
        }
        (manifest_dir / "cloudinary_seed_images.json").write_text(
            json.dumps({"central-home": [self.image]}),
            encoding="utf-8",
        )
        self.property = create_property()
        self.old_image = PropertyImage.objects.create(
            property=self.property,
            image="media/properties/central/old.webp",
            alt_es="Anterior",
            alt_en="Previous",
            width=1200,
            height=800,
            sort_order=0,
        )
        self.settings = override_settings(
            BASE_DIR=self.base_dir,
            CLOUDINARY_STORAGE={"CLOUD_NAME": "test-cloud"},
            STORAGES={
                "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
            },
        )
        self.settings.enable()

    def tearDown(self):
        self.settings.disable()
        self.temp_dir.cleanup()

    @patch("core.management.commands.sync_cloudinary_images.Command._remote_image_exists", return_value=True)
    def test_dry_run_validates_assets_without_changing_references(self, remote_image_exists):
        call_command("sync_cloudinary_images")

        self.assertTrue(PropertyImage.objects.filter(pk=self.old_image.pk).exists())
        remote_image_exists.assert_called_once_with(self.image["url"])

    @patch("core.management.commands.sync_cloudinary_images.Command._remote_image_exists", return_value=True)
    def test_apply_replaces_only_manifest_property_images(self, remote_image_exists):
        call_command("sync_cloudinary_images", apply=True)

        images = list(self.property.images.all())
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].image.name, self.image["name"])
        self.assertFalse(PropertyImage.objects.filter(pk=self.old_image.pk).exists())
        remote_image_exists.assert_called_once_with(self.image["url"])

    @patch("core.management.commands.sync_cloudinary_images.Command._remote_image_exists", return_value=False)
    def test_unavailable_asset_aborts_without_changing_references(self, remote_image_exists):
        with self.assertRaisesMessage(CommandError, "no database changes were made"):
            call_command("sync_cloudinary_images", apply=True)

        self.assertTrue(PropertyImage.objects.filter(pk=self.old_image.pk).exists())
        remote_image_exists.assert_called_once_with(self.image["url"])

    @patch("core.management.commands.sync_cloudinary_images.Command._remote_image_exists")
    def test_invalid_manifest_entry_aborts_before_network_or_database_changes(self, remote_image_exists):
        self.image["width"] = "1200"
        (self.base_dir / "core" / "cloudinary_seed_images.json").write_text(
            json.dumps({"central-home": [self.image]}),
            encoding="utf-8",
        )

        with self.assertRaisesMessage(CommandError, "manifest entry for central-home is invalid"):
            call_command("sync_cloudinary_images", apply=True)

        self.assertTrue(PropertyImage.objects.filter(pk=self.old_image.pk).exists())
        remote_image_exists.assert_not_called()
