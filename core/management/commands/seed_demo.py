import io
import json
import random
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageDraw

from bookings.models import Reservation
from bookings.tax import included_tax_amount
from properties.models import Amenity, Destination, Property, PropertyImage


class Command(BaseCommand):
    help = "Create deterministic demo destinations and properties"

    destinations = [
        ("Anapoima", "Anapoima", "anapoima", "CO"),
        ("Bogotá", "Bogota", "bogota", "CO"),
        ("Cartagena", "Cartagena", "cartagena", "CO"),
        ("Guatapé", "Guatape", "guatape", "CO"),
        ("Medellín", "Medellin", "medellin", "CO"),
        ("Madrid", "Madrid", "madrid", "ES"),
        ("Barcelona", "Barcelona", "barcelona", "ES"),
        ("Firenze", "Florence", "firenze", "IT"),
        ("Milano", "Milan", "milano", "IT"),
        ("CDMX", "Mexico City", "cdmx", "MX"),
        ("Ciudad de Panamá", "Panama City", "ciudad-de-panama", "PA"),
        ("Cusco", "Cusco", "cusco", "PE"),
        ("Lima", "Lima", "lima", "PE"),
        ("Máncora", "Mancora", "mancora", "PE"),
        ("Paracas", "Paracas", "paracas", "PE"),
        ("Miami", "Miami", "miami", "US"),
    ]
    properties = [
        (
            "anapoima",
            "Astonishing 4BR House w/ pool in Anapoima",
            "Astonishing 4BR House w/ pool in Anapoima",
            "Casa espectacular con piscina privada y hermosas zonas verdes",
            "Spectacular house with private pool and scenic gardens",
            1137,
            16,
            4,
            12,
            "Colombia",
            "Cundinamarca",
            "Anapoima",
            True,
            "images/busqueda 1.png",
        ),
        (
            "anapoima",
            "Astonishing 5BR House w/ pool in Anapoima",
            "Astonishing 5BR House w/ pool in Anapoima",
            "Hermosa residencia de descanso con piscina y amplios espacios",
            "Beautiful retreat residence with pool and spacious living areas",
            853,
            16,
            5,
            8,
            "Colombia",
            "Cundinamarca",
            "Anapoima",
            True,
            "images/busqueda 2.png",
        ),
        (
            "bogota",
            "Chicó Contemporary Loft",
            "Chico Contemporary Loft",
            "Diseño moderno y ubicación privilegiada en El Chicó",
            "Modern design and privileged location in El Chico",
            320,
            4,
            2,
            2,
            "Colombia",
            "Cundinamarca",
            "Chicó",
            False,
            "images/busqueda 3.png",
        ),
        (
            "medellin",
            "El Poblado Panoramic Flat",
            "El Poblado Panoramic Flat",
            "Balcón amplio y acabados de lujo cerca de Provenza",
            "Large balcony and luxury finishes near Provenza",
            295,
            4,
            2,
            3,
            "Colombia",
            "Antioquia",
            "El Poblado",
            False,
            "images/busqueda 4.png",
        ),
        (
            "cartagena",
            "Bocagrande Bay Apartment",
            "Bocagrande Bay Apartment",
            "Apartamento contemporáneo con vista a la bahía de Cartagena",
            "Contemporary apartment with views of Cartagena Bay",
            340,
            4,
            2,
            3,
            "Colombia",
            "Bolívar",
            "Bocagrande",
            False,
            None,
        ),
        (
            "guatape",
            "Guatapé Lakeside Retreat",
            "Guatapé Lakeside Retreat",
            "Casa tranquila a pocos pasos del malecón de Guatapé",
            "Quiet house steps from the Guatapé waterfront",
            410,
            6,
            3,
            4,
            "Colombia",
            "Antioquia",
            "El Peñol",
            False,
            None,
        ),
        (
            "madrid",
            "Gran Vía Skyline",
            "Gran Vía Skyline",
            "Loft luminoso en el corazón de Madrid",
            "Bright loft in the heart of Madrid",
            360,
            4,
            2,
            3,
            "España",
            "Madrid",
            "Centro",
            True,
            None,
        ),
        (
            "madrid",
            "Salamanca Collection",
            "Salamanca Collection",
            "Diseño contemporáneo y ubicación privilegiada",
            "Contemporary design in a privileged location",
            430,
            5,
            3,
            4,
            "España",
            "Madrid",
            "Salamanca",
            True,
            None,
        ),
        (
            "barcelona",
            "Eixample Living",
            "Eixample Living",
            "Arquitectura clásica junto al Passeig de Gràcia",
            "Classic architecture near Passeig de Gràcia",
            390,
            4,
            2,
            3,
            "España",
            "Barcelona",
            "Eixample",
            True,
            None,
        ),
        (
            "firenze",
            "Santa Croce Florentine Stay",
            "Santa Croce Florentine Stay",
            "Estadía elegante en el histórico barrio de Santa Croce",
            "Elegant stay in the historic Santa Croce district",
            375,
            4,
            2,
            3,
            "Italy",
            "Toscana",
            "Santa Croce",
            False,
            None,
        ),
        (
            "milano",
            "Brera Design Residence",
            "Brera Design Residence",
            "Residencia de diseño cerca de las galerías de Brera",
            "Design residence near Brera galleries",
            455,
            4,
            2,
            3,
            "Italy",
            "Lombardía",
            "Brera",
            False,
            None,
        ),
        (
            "cdmx",
            "Polanco City Residence",
            "Polanco City Residence",
            "Residencia amplia cerca de museos y restaurantes de Polanco",
            "Spacious residence near Polanco museums and restaurants",
            395,
            4,
            2,
            3,
            "México",
            "Ciudad de México",
            "Polanco",
            False,
            None,
        ),
        (
            "ciudad-de-panama",
            "Casco Viejo Terrace",
            "Casco Viejo Terrace",
            "Terraza privada en el casco histórico de Ciudad de Panamá",
            "Private terrace in Panama City's historic quarter",
            325,
            4,
            2,
            3,
            "Panamá",
            "Panamá",
            "Casco Viejo",
            False,
            None,
        ),
        (
            "cusco",
            "Cusco Historic Center Home",
            "Cusco Historic Center Home",
            "Hogar luminoso junto a las calles históricas de Cusco",
            "Bright home by Cusco's historic streets",
            270,
            4,
            2,
            3,
            "Perú",
            "Cusco",
            "Centro Histórico",
            False,
            None,
        ),
        (
            "barcelona",
            "Born Terrace",
            "Born Terrace",
            "Terraza privada y espacios llenos de luz",
            "Private terrace and light-filled spaces",
            315,
            3,
            1,
            2,
            "España",
            "Barcelona",
            "Born",
            False,
            None,
        ),
        (
            "lima",
            "Miraflores Ocean View",
            "Miraflores Ocean View",
            "Vistas al Pacífico a pasos del malecón",
            "Pacific views steps from the boardwalk",
            280,
            4,
            2,
            3,
            "Perú",
            "Lima",
            "Miraflores",
            True,
            None,
        ),
        (
            "mancora",
            "Las Pocitas Beach House",
            "Las Pocitas Beach House",
            "Casa frente al mar para descansar en Máncora",
            "Beachfront house for a relaxing stay in Mancora",
            310,
            5,
            2,
            4,
            "Perú",
            "Piura",
            "Las Pocitas",
            False,
            None,
        ),
        (
            "paracas",
            "Paracas El Chaco Escape",
            "Paracas El Chaco Escape",
            "Escape costero junto a la bahía de Paracas",
            "Coastal escape by Paracas Bay",
            285,
            4,
            2,
            3,
            "Perú",
            "Ica",
            "El Chaco",
            False,
            None,
        ),
        (
            "miami",
            "Brickell Skyline Apartment",
            "Brickell Skyline Apartment",
            "Apartamento contemporáneo con vistas al skyline de Miami",
            "Contemporary apartment with Miami skyline views",
            520,
            4,
            2,
            3,
            "Estados Unidos",
            "Florida",
            "Brickell",
            False,
            None,
        ),
        (
            "lima",
            "Barranco Art House",
            "Barranco Art House",
            "Un refugio creativo cerca del Puente de los Suspiros",
            "A creative retreat near the Bridge of Sighs",
            245,
            3,
            2,
            2,
            "Perú",
            "Lima",
            "Barranco",
            False,
            None,
        ),
    ]
    amenities = [
        ("Ascensor", "Elevator", "elevator"),
        ("Estacionamiento", "Indoor Parking", "parking"),
        ("Televisor", "TV", "tv"),
        ("Portero", "Doorman", "doorman"),
        ("Patio o balcón", "Patio or Balcony", "balcony"),
        ("Parrilla", "BBQ grill", "bbq"),
        ("Wifi", "Wi-Fi", "wifi"),
        ("Cocina equipada", "Equipped kitchen", "kitchen"),
        ("Lavadora", "Washer", "washer"),
        ("Espacio de trabajo", "Workspace", "workspace"),
        ("Aire acondicionado", "Air conditioning", "snowflake"),
    ]
    amenities_by_destination = {
        "anapoima": ("parking", "tv", "balcony", "bbq", "wifi", "kitchen"),
        "bogota": ("elevator", "parking", "tv", "doorman", "wifi", "workspace"),
        "cartagena": ("elevator", "parking", "tv", "balcony", "wifi", "snowflake"),
        "guatape": ("parking", "tv", "balcony", "bbq", "wifi", "kitchen"),
        "medellin": ("elevator", "parking", "tv", "balcony", "wifi", "workspace"),
        "madrid": ("elevator", "tv", "doorman", "wifi", "kitchen", "washer"),
        "barcelona": ("elevator", "tv", "balcony", "wifi", "kitchen", "washer"),
        "firenze": ("elevator", "tv", "wifi", "kitchen", "washer"),
        "milano": ("elevator", "tv", "doorman", "wifi", "workspace", "snowflake"),
        "cdmx": ("elevator", "parking", "tv", "doorman", "wifi", "workspace"),
        "ciudad-de-panama": ("elevator", "parking", "tv", "balcony", "wifi", "snowflake"),
        "cusco": ("tv", "wifi", "kitchen", "washer", "workspace"),
        "lima": ("elevator", "tv", "balcony", "wifi", "kitchen", "washer"),
        "mancora": ("parking", "tv", "balcony", "bbq", "wifi", "kitchen"),
        "paracas": ("parking", "tv", "balcony", "bbq", "wifi", "kitchen"),
        "miami": ("elevator", "parking", "tv", "balcony", "wifi", "snowflake"),
    }

    property_coordinates = {
        "Astonishing 4BR House w/ pool in Anapoima": (Decimal("4.551200"), Decimal("-74.536500")),
        "Astonishing 5BR House w/ pool in Anapoima": (Decimal("4.558000"), Decimal("-74.542000")),
        "Chico Contemporary Loft": (Decimal("4.678000"), Decimal("-74.048500")),
        "El Poblado Panoramic Flat": (Decimal("6.208500"), Decimal("-75.567000")),
        "Bocagrande Bay Apartment": (Decimal("10.399500"), Decimal("-75.556000")),
        "Guatapé Lakeside Retreat": (Decimal("6.233500"), Decimal("-75.161000")),
        "Gran Vía Skyline": (Decimal("40.420000"), Decimal("-3.705800")),
        "Salamanca Collection": (Decimal("40.428500"), Decimal("-3.682000")),
        "Eixample Living": (Decimal("41.392000"), Decimal("2.164500")),
        "Santa Croce Florentine Stay": (Decimal("43.768700"), Decimal("11.262500")),
        "Brera Design Residence": (Decimal("45.472000"), Decimal("9.187500")),
        "Polanco City Residence": (Decimal("19.433500"), Decimal("-99.191500")),
        "Casco Viejo Terrace": (Decimal("8.952500"), Decimal("-79.534000")),
        "Cusco Historic Center Home": (Decimal("-13.516000"), Decimal("-71.979000")),
        "Born Terrace": (Decimal("41.385500"), Decimal("2.182000")),
        "Miraflores Ocean View": (Decimal("-12.122000"), Decimal("-77.036000")),
        "Las Pocitas Beach House": (Decimal("-4.128000"), Decimal("-81.074000")),
        "Paracas El Chaco Escape": (Decimal("-13.834000"), Decimal("-76.251000")),
        "Brickell Skyline Apartment": (Decimal("25.761700"), Decimal("-80.191800")),
        "Barranco Art House": (Decimal("-12.148000"), Decimal("-77.021000")),
    }

    def add_arguments(self, parser):
        parser.add_argument("--refresh-images", action="store_true")
        parser.add_argument("--if-empty", action="store_true")

    def make_placeholder_image(self, seed, width=1200, height=800):
        random.seed(seed)
        palettes = [
            ((224, 215, 200), (123, 105, 88), (249, 246, 239)),
            ((205, 215, 214), (61, 82, 83), (243, 238, 229)),
            ((230, 219, 205), (142, 91, 69), (251, 246, 235)),
            ((211, 207, 198), (72, 68, 62), (239, 232, 216)),
        ]
        wall, accent, light = palettes[seed % len(palettes)]
        image = Image.new("RGB", (width, height), wall)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, height * 0.68, width, height), fill=(150, 125, 98))
        draw.rectangle((width * 0.08, height * 0.12, width * 0.43, height * 0.58), fill=light, outline=accent, width=10)
        draw.rectangle((width * 0.62, height * 0.2, width * 0.9, height * 0.72), fill=(104, 89, 76))
        draw.rectangle((width * 0.22, height * 0.56, width * 0.78, height * 0.75), fill=accent)
        draw.rectangle((width * 0.27, height * 0.48, width * 0.48, height * 0.62), fill=(246, 241, 232))
        draw.rectangle((width * 0.52, height * 0.48, width * 0.73, height * 0.62), fill=(235, 228, 216))
        draw.ellipse((width * 0.78, height * 0.06, width * 0.94, height * 0.3), fill=(72, 104, 72))
        output = io.BytesIO()
        image.save(output, "WEBP", quality=84, method=6)
        return output.getvalue()

    @transaction.atomic
    def handle(self, *args, **options):
        if options["if_empty"] and Property.objects.exists():
            self.stdout.write("Demo data already exists; skipping seed")
            return

        cloudinary_images = {}
        json_path = settings.BASE_DIR / "core" / "cloudinary_seed_images.json"
        cloudinary_storage = (
            settings.STORAGES["default"]["BACKEND"] == "cloudinary_storage.storage.MediaCloudinaryStorage"
        )
        if cloudinary_storage and json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                cloudinary_images = json.load(f)
        fallback_images = cloudinary_images.pop("_fallback_demo_images", [])

        destinations = {}
        for name_es, name_en, slug, country_code in self.destinations:
            destination, _ = Destination.objects.update_or_create(
                slug=slug,
                defaults={"name_es": name_es, "name_en": name_en, "country_code": country_code},
            )
            destinations[slug] = destination
        amenities = []
        for order, (name_es, name_en, icon) in enumerate(self.amenities):
            amenity, _ = Amenity.objects.update_or_create(
                name_es=name_es, defaults={"name_en": name_en, "icon": icon, "sort_order": order}
            )
            amenities.append(amenity)
        amenities_by_icon = {amenity.icon: amenity for amenity in amenities}
        for index, data in enumerate(self.properties):
            destination_slug, title_es, title_en, summary_es, summary_en, price, guests, bedrooms, beds, country, province, district, featured, custom_image = data
            slug = slugify(title_en)
            coords = self.property_coordinates.get(title_en, (None, None))
            property, _ = Property.objects.update_or_create(
                destination=destinations[destination_slug],
                title_en=title_en,
                defaults={
                    "slug": slug,
                    "title_es": title_es,
                    "title_en": title_en,
                    "summary_es": summary_es,
                    "summary_en": summary_en,
                    "description_es": (
                        f"Una residencia cuidadosamente seleccionada en {destinations[destination_slug].name_es}, "
                        "diseñada para estadías cómodas, largas y memorables. Espacios amplios y luminosos, acabados "
                        "contemporáneos y todas las comodidades para sentirte en casa desde el primer día. A pasos de "
                        "los mejores restaurantes, cafés y lugares de interés de la ciudad."
                    ),
                    "description_en": (
                        f"A carefully selected residence in {destinations[destination_slug].name_en}, designed for "
                        "comfortable, long and memorable stays. Bright, spacious rooms, contemporary finishes and every "
                        "comfort so you feel at home from day one. Steps from the best restaurants, cafés and landmarks "
                        "the city has to offer."
                    ),
                    "country": country,
                    "province": province,
                    "district": district,
                    "address": f"{index + 10} Central Avenue, {district}",
                    "price_per_night": price,
                    "price_per_month": (Decimal(str(price)) * Decimal("25.00")).quantize(Decimal("0.01")),
                    "cleaning_fee": 45,
                    "max_guests": guests,
                    "bedrooms": bedrooms,
                    "beds": beds,
                    "bathrooms": 2,
                    "latitude": coords[0],
                    "longitude": coords[1],
                    "is_featured": featured,
                    "is_active": True,
                },
            )
            property.amenities.set(
                [amenities_by_icon[icon] for icon in self.amenities_by_destination.get(destination_slug, ())]
            )
            if options["refresh_images"]:
                old_images = list(property.images.all())
                old_files = [(image.image.storage, image.image.name) for image in old_images]
                property.images.all().delete()
                for storage, name in old_files:
                    transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
            if not property.images.exists():
                prop_images = cloudinary_images.get(slug)
                if prop_images:
                    for img_data in prop_images:
                        PropertyImage.objects.create(
                            property=property,
                            image=img_data["name"],
                            alt_es=img_data.get("alt_es", f"Interior de {title_es}"),
                            alt_en=img_data.get("alt_en", f"Interior of {title_en}"),
                            sort_order=img_data.get("sort_order", 0),
                            width=img_data.get("width", 1200),
                            height=img_data.get("height", 800),
                        )
                else:
                    start_idx = 0
                    custom_image_path = settings.BASE_DIR / custom_image if custom_image else None
                    if custom_image_path and custom_image_path.exists():
                        img = Image.open(custom_image_path).convert("RGB")
                        output = io.BytesIO()
                        img.save(output, "WEBP", quality=86, method=6)
                        PropertyImage.objects.create(
                            property=property,
                            image=ContentFile(output.getvalue(), name=f"{slug}-0.webp"),
                            alt_es=f"Vista de {title_es}",
                            alt_en=f"View of {title_en}",
                            sort_order=0,
                        )
                        start_idx = 1
                    for image_index in range(start_idx, 4):
                        if cloudinary_storage and fallback_images:
                            fallback_image = fallback_images[(index + image_index) % len(fallback_images)]
                            PropertyImage.objects.create(
                                property=property,
                                image=fallback_image["name"],
                                alt_es=f"Interior de {title_es}",
                                alt_en=f"Interior of {title_en}",
                                sort_order=image_index,
                                width=fallback_image.get("width", 1200),
                                height=fallback_image.get("height", 800),
                            )
                        else:
                            content = ContentFile(
                                self.make_placeholder_image(index * 10 + image_index),
                                name=f"{slug}-{image_index}.webp",
                            )
                            PropertyImage.objects.create(
                                property=property,
                                image=content,
                                alt_es=f"Interior de {title_es}",
                                alt_en=f"Interior of {title_en}",
                                sort_order=image_index,
                            )
        self.create_demo_reservation()
        self.stdout.write(self.style.SUCCESS("Demo data created"))

    def create_demo_reservation(self):
        user, created = get_user_model().objects.get_or_create(
            email="demo@wynwoodhouse.com",
            defaults={"first_name": "Adolfo"},
        )
        if created:
            user.set_password("wynwood123")
            user.save(update_fields=["password"])
        property = Property.objects.filter(slug="miraflores-ocean-view").first()
        if property is None:
            return
        total = Decimal("182.00")
        tax_rate = Decimal("0.18")
        values = {
            "check_in": timezone.localdate() + timedelta(days=60),
            "check_out": timezone.localdate() + timedelta(days=64),
            "guests": 2,
            "language_code": "es",
            "status": Reservation.Status.CONFIRMED,
            "nightly_rate": Decimal("45.50"),
            "nights": 4,
            "subtotal": Decimal("182.00"),
            "cleaning_fee": Decimal("22.00"),
            "discount_amount": Decimal("22.00"),
            "currency": "USD",
            "tax_rate": tax_rate,
            "tax_amount": included_tax_amount(total, tax_rate),
            "total": total,
            "points_earned": round(float(total) * settings.WYNWOOD_POINTS_RATE),
            "expires_at": timezone.now(),
            "confirmed_at": timezone.now(),
            "confirmation_sent_at": timezone.now(),
        }
        reservation = Reservation.objects.filter(user=user, property=property).order_by("-created_at").first()
        if reservation is None:
            Reservation.objects.create(user=user, property=property, **values)
        else:
            Reservation.objects.filter(pk=reservation.pk).update(**values)
