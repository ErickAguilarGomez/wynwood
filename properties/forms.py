from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Amenity, Destination


class DestinationField(forms.Field):


    def to_python(self, value):
        if not value:
            return None
        value = str(value).strip()
        if not value:
            return None
        if value.isdigit():
            dest = Destination.objects.filter(pk=int(value)).first()
            if dest:
                return dest
        dest = Destination.objects.filter(slug__iexact=value).first()
        if dest:
            return dest
        dest = Destination.objects.filter(name_es__iexact=value).first() or Destination.objects.filter(name_en__iexact=value).first()
        if dest:
            return dest
        return value


class PropertySearchForm(forms.Form):
    destination = DestinationField(required=False)
    country = forms.CharField(required=False, max_length=120)
    province = forms.CharField(required=False, max_length=120)
    district = forms.CharField(required=False, max_length=120)
    check_in = forms.DateField(
        label=_("Check-in"), required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    check_out = forms.DateField(
        label=_("Check-out"), required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    guests = forms.IntegerField(label=_("Guests"), min_value=1, max_value=50, initial=1, required=False)
    min_price = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=10, label=_("Minimum price"))
    max_price = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=10, label=_("Maximum price"))
    amenities = forms.ModelMultipleChoiceField(queryset=Amenity.objects.all(), required=False, label=_("Amenities"))

    def clean(self):
        data = super().clean()
        min_price = data.get("min_price")
        max_price = data.get("max_price")
        if min_price is not None and max_price is not None and max_price < min_price:
            self.add_error("max_price", _("The maximum price must be greater than the minimum price."))
        check_in = data.get("check_in")
        check_out = data.get("check_out")
        if check_in and check_in < timezone.localdate():
            self.add_error("check_in", _("Check-in cannot be in the past."))
        if check_out and check_out < timezone.localdate():
            self.add_error("check_out", _("Check-out cannot be in the past."))
        if check_in and check_out and check_out <= check_in:
            self.add_error("check_out", _("Check-out must be after check-in."))
        return data
