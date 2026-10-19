from django.contrib import admin

from .models import Amenity, Destination, Property, PropertyImage


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "title_es",
        "destination",
        "country",
        "province",
        "district",
        "brand",
        "price_per_night",
        "max_guests",
        "is_featured",
        "is_active",
    )
    list_filter = ("country", "province", "district", "destination", "brand", "is_featured", "is_active")
    search_fields = ("title_es", "title_en", "country", "province", "district", "address")
    prepopulated_fields = {"slug": ("title_es",)}
    filter_horizontal = ("amenities",)
    inlines = (PropertyImageInline,)


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("name_es", "country_code", "sort_order")
    prepopulated_fields = {"slug": ("name_es",)}


admin.site.register(Amenity)
