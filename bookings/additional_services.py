from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Exists, OuterRef, Q

from .models import ServiceCatalog

MONEY = Decimal("0.01")


def to_money(value):
    return Decimal(str(value)).quantize(MONEY, ROUND_HALF_UP)


def get_services():
    configurations = Q()
    for detail, kind in ServiceCatalog.configuration_kinds.items():
        configurations |= Q(detail_key=detail, kind=kind)
    variants = ServiceCatalog.objects.filter(group_key=OuterRef("detail_key"), is_active=True).filter(
        Q(category=ServiceCatalog.Category.VEHICLE, group_key="transport")
        | Q(category=ServiceCatalog.Category.GROCERY, group_key="groceries")
    )
    return ServiceCatalog.objects.filter(configurations, category=ServiceCatalog.Category.SERVICE, is_active=True).annotate(
        has_variants=Exists(variants)
    ).filter(~Q(detail_key__in=("transport", "groceries")) | Q(has_variants=True))


def get_service(key):
    return get_services().filter(key=key).first()


def get_vehicles():
    return ServiceCatalog.objects.filter(category=ServiceCatalog.Category.VEHICLE, group_key="transport", is_active=True)


def get_grocery_packs():
    return ServiceCatalog.objects.filter(category=ServiceCatalog.Category.GROCERY, group_key="groceries", is_active=True)


def service_for_kind(kind):
    return ServiceCatalog.objects.filter(category=ServiceCatalog.Category.SERVICE, kind=kind).order_by(
        "-is_active", "sort_order", "key"
    ).first()


def vehicle_choices():
    return tuple((vehicle.key, vehicle.name) for vehicle in get_vehicles())


def transport_quote(*, trip_type, vehicle_key, quantity):
    vehicle = get_vehicles().get(key=vehicle_key)
    unit_price = vehicle.round_trip_price if trip_type == "round_trip" else vehicle.price
    amount = to_money(unit_price * quantity)
    details = {
        "trip_type": trip_type,
        "vehicle": vehicle.key,
        "quantity": quantity,
        "passengers": vehicle.passengers * quantity,
        "bags": vehicle.bags * quantity,
    }
    return amount, details


def grocery_quote(*, pack_key):
    pack = get_grocery_packs().get(key=pack_key)
    return to_money(pack.price), {"pack": pack.key}


def crib_quote(*, quantity, service=None):
    service = service or get_services().get(kind=ServiceCatalog.configuration_kinds["crib"])
    return to_money(service.price * quantity), {"quantity": quantity}


def flexible_checkin_quote(*, check_in_time, service=None):
    service = service or get_services().get(kind=ServiceCatalog.configuration_kinds["flexible_checkin"])
    details = {"check_in_time": check_in_time.strftime("%H:%M") if check_in_time else ""}
    return to_money(service.price), details
