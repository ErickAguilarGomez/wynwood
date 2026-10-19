from django.test import TestCase
from django.urls import reverse

from core.tests.factories import create_property
from properties.models import Property


class HomeFeaturedPropertyTests(TestCase):
    def setUp(self):
        self.collection = create_property(
            slug="collection-home",
            title_en="Collection Home",
            brand=Property.Brand.COLLECTION,
        )
        self.casa = create_property(
            slug="casa-wynwood-home",
            title_en="Casa Wynwood Home",
            brand=Property.Brand.CASA_WYNWOOD,
        )
        self.standard = create_property(
            slug="standard-home",
            title_en="Standard Home",
            brand=Property.Brand.STANDARD,
        )

    def test_category_tabs_filter_featured_properties(self):
        collection = self.client.get(reverse("core:home"), {"category": "collection"})
        self.assertContains(collection, "/properties/collection-home/")
        self.assertNotContains(collection, "/properties/casa-wynwood-home/")
        self.assertNotContains(collection, "/properties/standard-home/")

        casa = self.client.get(reverse("core:home"), {"category": "casa_wynwood"})
        self.assertContains(casa, "/properties/casa-wynwood-home/")
        self.assertNotContains(casa, "/properties/collection-home/")
        self.assertNotContains(casa, "/properties/standard-home/")

        all_properties = self.client.get(reverse("core:home"), {"category": "all"})
        self.assertContains(all_properties, "/properties/collection-home/")
        self.assertContains(all_properties, "/properties/casa-wynwood-home/")
        self.assertContains(all_properties, "/properties/standard-home/")

        invalid_category = self.client.get(reverse("core:home"), {"category": "unknown"})
        self.assertContains(invalid_category, "/properties/standard-home/")

    def test_spain_editorial_section_is_translated(self):
        spanish = self.client.get(reverse("core:home"), HTTP_ACCEPT_LANGUAGE="es")
        self.assertContains(spanish, "¿Por qué viajar a España?")

        self.client.post(reverse("set_language"), {"language": "en", "next": "/"})
        english = self.client.get(reverse("core:home"))
        self.assertContains(english, "Why travel to Spain?")
