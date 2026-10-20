from django import forms
from django.contrib import admin

from .models import Airport, Amenity, Country, Destination, Property, PropertyImage


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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["country_code"] = forms.ChoiceField(
            label=form.base_fields["country_code"].label,
            choices=[(country.code, country.name) for country in Country.objects.filter(is_active=True)],
        )
        return form


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name_es", "name_en", "phone_prefix", "tax_rate", "show_on_home", "is_active", "sort_order")
    list_filter = ("is_active", "show_on_home")
    search_fields = ("code", "name_es", "name_en")


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ("code", "name_es", "destination", "is_active", "sort_order")
    list_filter = ("destination", "is_active")
    search_fields = ("code", "name_es", "name_en", "destination__name_es")


admin.site.register(Amenity)
