from django.contrib import admin

from .models import Reservation, ReservationCharge, ServiceCatalog


class ReservationChargeInline(admin.TabularInline):
    model = ReservationCharge
    extra = 0
    fields = ("kind", "amount")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("public_id", "property", "user", "check_in", "check_out", "status", "total")
    list_filter = ("status", "check_in", "property__destination")
    search_fields = ("public_id", "user__email", "property__title_es")
    readonly_fields = (
        "public_id",
        "currency",
        "tax_rate",
        "tax_amount",
        "points_earned",
        "created_at",
        "updated_at",
        "confirmed_at",
        "confirmation_sent_at",
    )
    inlines = (ReservationChargeInline,)


@admin.register(ServiceCatalog)
class ServiceCatalogAdmin(admin.ModelAdmin):
    list_display = ("key", "name_es", "name_en", "category", "price", "is_active", "sort_order")
    list_filter = ("category", "is_active", "group_key")
    search_fields = ("key", "name_es", "name_en", "description_es", "description_en")
