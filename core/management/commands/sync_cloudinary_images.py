import json
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from properties.models import Property, PropertyImage


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if settings.STORAGES["default"]["BACKEND"] != "cloudinary_storage.storage.MediaCloudinaryStorage":
            raise CommandError("Cloudinary media storage is not enabled.")

        cloud_name = settings.CLOUDINARY_STORAGE.get("CLOUD_NAME")
        if not isinstance(cloud_name, str) or not cloud_name:
            raise CommandError("The Cloudinary cloud name is not configured.")
        manifest_path = Path(settings.BASE_DIR) / "core" / "cloudinary_seed_images.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError("The Cloudinary image manifest could not be read.") from error

        if not isinstance(manifest, dict):
            raise CommandError("The Cloudinary image manifest has an invalid format.")
        manifest.pop("_fallback_demo_images", None)
        properties = {property.slug: property for property in Property.objects.filter(slug__in=manifest)}
        replacements = []
        for slug, images in manifest.items():
            property = properties.get(slug)
            if property is None:
                continue
            if not isinstance(images, list) or not images:
                raise CommandError(f"The image list for {slug} is empty or invalid.")
            for image in images:
                if not self._valid_image(image, cloud_name):
                    raise CommandError(f"The image manifest entry for {slug} is invalid.")
                if not self._remote_image_exists(image["url"]):
                    raise CommandError(f"A Cloudinary image for {slug} is unavailable; no database changes were made.")
            replacements.append((property, images))

        if not replacements:
            raise CommandError("No properties in the database match the Cloudinary image manifest.")
        image_count = sum(len(images) for _, images in replacements)
        if not options["apply"]:
            self.stdout.write(f"Validated {image_count} Cloudinary images for {len(replacements)} properties; no changes made.")
            self.stdout.write("Run with --apply to replace these property image references.")
            return

        with transaction.atomic():
            for property, images in replacements:
                PropertyImage.objects.filter(property=property).delete()
                PropertyImage.objects.bulk_create(
                    [
                        PropertyImage(
                            property=property,
                            image=image["name"],
                            alt_es=image["alt_es"],
                            alt_en=image["alt_en"],
                            width=image["width"],
                            height=image["height"],
                            sort_order=image["sort_order"],
                        )
                        for image in images
                    ]
                )
        self.stdout.write(self.style.SUCCESS(f"Updated {image_count} Cloudinary images for {len(replacements)} properties."))

    @staticmethod
    def _valid_image(image, cloud_name):
        if not isinstance(image, dict) or not all(
            key in image for key in ("name", "url", "alt_es", "alt_en", "width", "height", "sort_order")
        ):
            return False
        if any(not isinstance(image[key], str) or not image[key] for key in ("name", "url", "alt_es", "alt_en")):
            return False
        if any(type(image[key]) is not int for key in ("width", "height", "sort_order")):
            return False
        parsed_url = urlparse(image["url"])
        return (
            image["name"].startswith("media/properties/")
            and all(part not in ("", ".", "..") for part in image["name"].split("/"))
            and parsed_url.scheme == "https"
            and parsed_url.netloc == "res.cloudinary.com"
            and parsed_url.path.startswith(f"/{cloud_name}/image/upload/")
            and 0 < image["width"] <= 1200
            and 0 < image["height"] <= 1200
            and image["sort_order"] >= 0
            and bool(image["alt_es"])
            and bool(image["alt_en"])
        )

    @staticmethod
    def _remote_image_exists(url):
        try:
            with urlopen(Request(url, method="HEAD"), timeout=10) as response:
                return response.status == 200 and response.headers.get_content_type().startswith("image/")
        except (OSError, URLError, ValueError):
            return False
