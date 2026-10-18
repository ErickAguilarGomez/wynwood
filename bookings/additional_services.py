










from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.utils.translation import get_language

from .models import ReservationCharge

MONEY = Decimal("0.01")


def to_money(value):

    return Decimal(str(value)).quantize(MONEY, ROUND_HALF_UP)


def _pick(spanish, english):
    return english if get_language() == "en" else spanish


@dataclass(frozen=True)
class VehicleType:
    key: str
    name_es: str
    name_en: str
    passengers: int
    bags: int
    one_way_price: Decimal

    @property
    def name(self):
        return _pick(self.name_es, self.name_en)

    @property
    def round_trip_price(self):
        return to_money(self.one_way_price * 2)


VEHICLES = (
    VehicleType("suv", "Suv", "SUV", 4, 3, Decimal("13.00")),
    VehicleType("van", "Van", "Van", 7, 6, Decimal("18.00")),
)
VEHICLES_BY_KEY = {vehicle.key: vehicle for vehicle in VEHICLES}


@dataclass(frozen=True)
class GroceryPack:
    key: str
    name_es: str
    name_en: str
    description_es: str
    description_en: str
    price: Decimal

    @property
    def name(self):
        return _pick(self.name_es, self.name_en)

    @property
    def description(self):
        return _pick(self.description_es, self.description_en)


GROCERY_PACKS = (
    GroceryPack(
        key="breakfast",
        name_es="Pack desayuno",
        name_en="Breakfast pack",
        description_es="Café, jugo, frutas, pan y huevos para empezar el día sin salir.",
        description_en="Coffee, juice, fruit, bread and eggs to start the day in.",
        price=Decimal("18.00"),
    ),
    GroceryPack(
        key="dinner",
        name_es="Pack cena",
        name_en="Dinner pack",
        description_es="Una cena lista para preparar con productos locales y una botella de vino.",
        description_en="A ready-to-cook dinner with local produce and a bottle of wine.",
        price=Decimal("24.00"),
    ),
    GroceryPack(
        key="celebration",
        name_es="Pack celebración",
        name_en="Celebration pack",
        description_es="Burbujas, tabla de quesos y dulces para sorprender a quien viaja contigo.",
        description_en="Bubbles, a cheese board and sweets to surprise your travel companions.",
        price=Decimal("32.00"),
    ),
)
GROCERY_PACKS_BY_KEY = {pack.key: pack for pack in GROCERY_PACKS}


@dataclass(frozen=True)
class AdditionalService:
    key: str
    kind: str
    name_es: str
    name_en: str
    description_es: str
    description_en: str
    detail_es: str
    detail_en: str
    image: str
    detail: str
    base_price: Decimal = Decimal("0.00")

    @property
    def name(self):
        return _pick(self.name_es, self.name_en)

    @property
    def description(self):
        return _pick(self.description_es, self.description_en)

    @property
    def detail_description(self):
        return _pick(self.detail_es, self.detail_en)

    @property
    def price_label(self):
        if self.key == "flexible-checkin":
            return _pick("USD 26", "USD 26")
        elif self.key == "transport":
            return _pick("Desde USD 13", "From USD 13")
        elif self.key == "groceries":
            return _pick("Desde USD 18", "From USD 18")
        elif self.key == "baby-crib":
            return _pick("USD 15 / noche", "USD 15 / night")
        if self.base_price > 0:
            return f"USD {self.base_price:.2f}"
        return ""


SERVICES = (
    AdditionalService(
        key="flexible-checkin",
        kind=ReservationCharge.Kind.EARLY_CHECK_IN,
        name_es="Check-in & Check-out flexible",
        name_en="Flexible check-in & check-out",
        description_es=(
            "Ofrecemos flexibilidad para early check-in o late check-out. "
            "¡Nos adaptamos a tus necesidades!"
        ),
        description_en=(
            "We offer flexibility for early check-in or late check-out. "
            "We adapt to what you need!"
        ),
        detail_es=(
            "Disfruta de la comodidad de tu espacio desde que llegas a tu destino "
            "y aprovecha cada momento de tu estadía."
        ),
        detail_en=(
            "Enjoy the comfort of your space from the moment you arrive at your destination "
            "and make the most of every moment of your stay."
        ),
        image="design/figma/home/service-checkin.png",
        detail="flexible_checkin",
        base_price=Decimal("26.00"),
    ),
    AdditionalService(
        key="transport",
        kind=ReservationCharge.Kind.TRANSPORT,
        name_es="Servicio de transporte",
        name_en="Transport service",
        description_es=(
            "No te preocupes por tu llegada a la ciudad, queremos ayudarte a sentirte seguro "
            "y como en casa. Agenda con nosotros los transportes que necesites para tu estadía "
            "y muévete seguro."
        ),
        description_en=(
            "Do not worry about arriving in the city; we want you to feel safe and at home. "
            "Book with us the transfers you need for your stay and move around safely."
        ),
        detail_es=(
            "Organiza tu transporte con Wynwood House y disfruta de un viaje seguro y cómodo "
            "desde el momento en que llegas hasta que te despides de tu destino."
        ),
        detail_en=(
            "Organise your transport with Wynwood House and enjoy a safe, comfortable trip "
            "from the moment you arrive until you say goodbye to your destination."
        ),
        image="design/figma/confirmation/service-transport.jpg",
        detail="transport",
    ),
    AdditionalService(
        key="groceries",
        kind=ReservationCharge.Kind.GROCERY,
        name_es="Llena tu nevera",
        name_en="Stock your fridge",
        description_es=(
            "Queremos que te sientas en la comodidad de tu hogar, por eso, organizamos unos "
            "packs especiales para que te acompañen en la ocasión perfecta. Explora nuestras "
            "opciones y cuéntanos que te gustaría tener en tu nevera."
        ),
        description_en=(
            "We want you to feel at home, so we prepare special packs for the perfect occasion. "
            "Explore our options and tell us what you would like in your fridge."
        ),
        detail_es=(
            "Elige el pack que mejor acompañe tu ocasión y nosotros lo dejamos listo en tu "
            "nevera antes de que llegues."
        ),
        detail_en=(
            "Choose the pack that best suits your occasion and we will have it ready in your "
            "fridge before you arrive."
        ),
        image="design/figma/home/service-kitchen.png",
        detail="groceries",
    ),
    AdditionalService(
        key="baby-crib",
        kind=ReservationCharge.Kind.CRIB,
        name_es="Cuna para bebé",
        name_en="Baby crib",
        description_es=(
            "Ofrecemos flexibilidad para early check-in o late check-out. "
            "¡Nos adaptamos a tus necesidades!"
        ),
        description_en=(
            "We offer flexibility for early check-in or late check-out. "
            "We adapt to what you need!"
        ),
        detail_es=(
            "Viaja con bebés sin cargar con todo: dejamos una cuna lista y preparada en tu "
            "habitación antes de tu llegada."
        ),
        detail_en=(
            "Travel with babies without carrying everything: we set up a crib ready in your "
            "room before you arrive."
        ),
        image="design/figma/home/service-bed.png",
        detail="crib",
        base_price=Decimal("15.00"),
    ),
)
SERVICES_BY_KEY = {service.key: service for service in SERVICES}


def service_for_kind(kind):

    for service in SERVICES:
        if service.kind == kind:
            return service
    return None


def vehicle_choices():
    return tuple((vehicle.key, vehicle.name) for vehicle in VEHICLES)


def transport_quote(*, trip_type, vehicle_key, quantity):

    vehicle = VEHICLES_BY_KEY[vehicle_key]
    trips = 2 if trip_type == "round_trip" else 1
    amount = to_money(vehicle.one_way_price * trips * quantity)
    details = {
        "trip_type": trip_type,
        "vehicle": vehicle.key,
        "quantity": quantity,
        "passengers": vehicle.passengers * quantity,
        "bags": vehicle.bags * quantity,
    }
    return amount, details


def grocery_quote(*, pack_key):
    pack = GROCERY_PACKS_BY_KEY[pack_key]
    return to_money(pack.price), {"pack": pack.key}


def crib_quote(*, quantity):
    service = SERVICES_BY_KEY["baby-crib"]
    return to_money(service.base_price * quantity), {"quantity": quantity}


def flexible_checkin_quote(*, check_in_time):
    service = SERVICES_BY_KEY["flexible-checkin"]
    details = {"check_in_time": check_in_time.strftime("%H:%M") if check_in_time else ""}
    return to_money(service.base_price), details
