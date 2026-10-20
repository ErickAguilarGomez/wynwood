import re
from datetime import time, timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from properties.models import Country

from .additional_services import (
    crib_quote,
    flexible_checkin_quote,
    get_grocery_packs,
    grocery_quote,
    transport_quote,
    vehicle_choices,
)


def parse_phone(phone_str, country=None, default_prefix="+51"):

    phone_raw = (phone_str or "").strip()
    matched_prefix = None
    number = phone_raw
    for prefix in sorted(phone_prefixes(), key=len, reverse=True):
        if phone_raw.startswith(prefix):
            matched_prefix = prefix
            number = phone_raw[len(prefix) :].strip()
            break
    if not matched_prefix:
        matched_prefix = Country.objects.filter(code=country, is_active=True).values_list("phone_prefix", flat=True).first() or default_prefix
    return matched_prefix, number


def phone_prefixes():
    return tuple(Country.objects.filter(is_active=True).exclude(phone_prefix="").values_list("phone_prefix", flat=True).distinct())


def country_phone_prefix(country_code, default="+51"):
    return Country.objects.filter(code=country_code, is_active=True).values_list("phone_prefix", flat=True).first() or default


PHONE_ALLOWED = re.compile(r"^[0-9+()\s.-]+$")


def country_choices():

    return [(country.code, country.name) for country in Country.objects.filter(is_active=True)]


class ReservationForm(forms.Form):
    check_in = forms.DateField(label=_("Check-in"), widget=forms.DateInput(attrs={"type": "date"}))
    check_out = forms.DateField(label=_("Check-out"), widget=forms.DateInput(attrs={"type": "date"}))
    guests = forms.IntegerField(label=_("Guests"), min_value=1)
    booking_type = forms.CharField(required=False, initial="daily")
    terms = forms.BooleanField(label=_("I accept the booking terms"))

    def __init__(self, *args, property, **kwargs):
        self.property = property
        super().__init__(*args, **kwargs)
        self.fields["guests"].widget.attrs["max"] = property.max_guests

    def clean(self):
        data = super().clean()
        check_in = data.get("check_in")
        check_out = data.get("check_out")
        guests = data.get("guests")
        if check_in and check_in < timezone.localdate():
            self.add_error("check_in", _("Check-in cannot be in the past."))
        if check_out and check_out < timezone.localdate():
            self.add_error("check_out", _("Check-out cannot be in the past."))
        if check_in and check_out and check_out <= check_in:
            self.add_error("check_out", _("Check-out must be after check-in."))
        if check_in and check_out and (check_out - check_in).days > 32767:
            self.add_error("check_out", _("Choose a shorter stay."))
        booking_type = data.get("booking_type") or "daily"
        if booking_type == "monthly" and check_in and check_out:
            if (check_out - check_in).days < 30:
                self.add_error("check_out", _("Monthly stays require a minimum of 30 nights."))
        if guests and guests > self.property.max_guests:
            self.add_error("guests", _("This property cannot accommodate that many guests."))
        return data


class MonthlyInquiryForm(forms.Form):
    email = forms.EmailField(label=_("Email address"))
    full_name = forms.CharField(label=_("Full name"), max_length=150)
    phone_code = forms.ChoiceField(
        label=_("Indicator"),
        choices=(),
    )
    phone = forms.CharField(label=_("Phone"), max_length=32)

    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()
        if not full_name:
            raise forms.ValidationError(_("Enter your full name."))
        return full_name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_code"].choices = [(prefix, prefix) for prefix in phone_prefixes()]

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not PHONE_ALLOWED.match(phone) or len(re.sub(r"\D", "", phone)) < 6:
            raise forms.ValidationError(_("Enter a valid phone number."))
        return phone


class CheckoutForm(forms.Form):


    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={"class": "registro-input", "autocomplete": "email", "data-required": "true"}),
    )
    password = forms.CharField(
        label=_("Create password"),
        widget=forms.PasswordInput(
            render_value=True,
            attrs={
                "class": "registro-input",
                "autocomplete": "new-password",
                "placeholder": _("Enter a new password"),
                "data-password-input": "true",
            },
        ),
    )
    full_name = forms.CharField(
        label=_("Full name"),
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "registro-input",
                "autocomplete": "name",
                "placeholder": _("Enter your full name"),
                "data-required": "true",
            }
        ),
    )
    nationality = forms.ChoiceField(
        label=_("Nationality"),
        widget=forms.Select(attrs={"class": "registro-input registro-select", "data-required": "true"}),
    )
    phone_code = forms.ChoiceField(
        label=_("Indicator"),
        choices=(),
        initial="+51",
        widget=forms.Select(attrs={"class": "registro-input registro-select registro-code"}),
    )
    phone = forms.CharField(
        label=_("Phone"),
        widget=forms.TextInput(
            attrs={
                "class": "registro-input",
                "autocomplete": "tel-national",
                "inputmode": "tel",
                "placeholder": _("Enter your phone number"),
                "data-required": "true",
            }
        ),
    )
    birth_date = forms.DateField(
        label=_("Date of birth"),
        input_formats=("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"),
        widget=forms.HiddenInput(attrs={"autocomplete": "bday", "data-required": "true"}),
    )

    newsletter = forms.BooleanField(label=_("I do not wish to subscribe to the Wynwood House newsletter"), required=False)
    check_in = forms.DateField(widget=forms.HiddenInput)
    check_out = forms.DateField(widget=forms.HiddenInput)
    guests = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    booking_type = forms.ChoiceField(
        choices=(("daily", _("Daily")),), widget=forms.HiddenInput, required=False, initial="daily"
    )

    def __init__(self, *args, property, user=None, request=None, **kwargs):
        self.property = property
        self.user = user
        self.request = request
        super().__init__(*args, **kwargs)
        self.fields["guests"].max_value = property.max_guests
        self.fields["guests"].validators.append(MaxValueValidator(property.max_guests))
        self.fields["nationality"].choices = [("", _("Select your country")), *country_choices()]
        self.fields["phone_code"].choices = [(prefix, prefix) for prefix in phone_prefixes()]

        self.hide_password = bool(user and user.is_authenticated)
        if self.hide_password:
            self.fields.pop("password", None)
            self.fields["email"].widget.attrs["readonly"] = True
        else:
            self.fields["email"].widget.attrs["data-unique"] = "true"
        self.fields["check_in"].required = True
        self.fields["check_out"].required = True

    def clean_email(self):
        if self.user and self.user.is_authenticated:
            return self.user.email
        return self.cleaned_data["email"].strip().lower()

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not PHONE_ALLOWED.match(phone) or len(re.sub(r"\D", "", phone)) < 6:
            raise forms.ValidationError(_("Enter a valid phone number."))
        return phone

    def clean_birth_date(self):
        birth_date = self.cleaned_data["birth_date"]
        if birth_date > timezone.localdate():
            raise forms.ValidationError(_("The date of birth cannot be in the future."))
        return birth_date

    def clean(self):
        data = super().clean()
        email = data.get("email")
        password = data.get("password")
        if email and not self.hide_password:
            existing_user = get_user_model().objects.filter(email__iexact=email).first()
            if existing_user:
                self.add_error(
                    "email",
                    ValidationError(
                        _("An account with this email already exists. Log in to continue."),
                        code="account_exists",
                    ),
                )

        check_in = data.get("check_in")
        check_out = data.get("check_out")
        guests = data.get("guests")
        if check_in and check_in < timezone.localdate():
            self.add_error("check_in", _("Check-in cannot be in the past."))
        if check_out and check_out < timezone.localdate():
            self.add_error("check_out", _("Check-out cannot be in the past."))
        if check_in and check_out and check_out <= check_in:
            self.add_error("check_out", _("Check-out must be after check-in."))
        if check_in and check_out and (check_out - check_in).days > 32767:
            self.add_error("check_out", _("Choose a shorter stay."))
        booking_type = data.get("booking_type") or "daily"
        if booking_type == "monthly" and check_in and check_out:
            if (check_out - check_in).days < 30:
                self.add_error("check_out", _("Monthly stays require a minimum of 30 nights."))
        if guests and guests > self.property.max_guests:
            self.add_error("guests", _("This property cannot accommodate that many guests."))
        if password:
            name_parts = (data.get("full_name") or "").partition(" ")
            password_user = get_user_model()(
                email=data.get("email", ""),
                first_name=name_parts[0],
                last_name=name_parts[2],
            )
            try:
                validate_password(password, password_user)
            except ValidationError as error:
                for message in error.messages:
                    self.add_error("password", message)
        return data


class ServiceForm(forms.Form):


    service = None

    def __init__(self, *args, reservation=None, service=None, **kwargs):
        self.reservation = reservation
        self.service = service
        super().__init__(*args, **kwargs)

    def build_charge(self):
        raise NotImplementedError


class TransportForm(ServiceForm):
    trip_type = forms.ChoiceField(
        label=_("Trip type"),
        choices=(("round_trip", _("Round trip")), ("one_way", _("One way"))),
        initial="one_way",
        widget=forms.RadioSelect,
    )
    departure_date = forms.DateField(label=_("Departure date"), widget=forms.HiddenInput)
    departure_time = forms.TimeField(label=_("Departure time"), widget=forms.TimeInput(attrs={"type": "time"}))
    departure_time_end = forms.TimeField(
        label=_("Departure time end"), widget=forms.TimeInput(attrs={"type": "time"})
    )
    airport = forms.ChoiceField(label=_("Airport"), widget=forms.Select(attrs={"class": "svc-airport-select"}))
    return_date = forms.DateField(
        label=_("Return date"), required=False, widget=forms.HiddenInput
    )
    return_time = forms.TimeField(
        label=_("Return time"), required=False, widget=forms.TimeInput(attrs={"type": "time"})
    )
    return_time_end = forms.TimeField(
        label=_("Return time end"), required=False, widget=forms.TimeInput(attrs={"type": "time"})
    )
    vehicle = forms.ChoiceField(label=_("Vehicle type"), widget=forms.RadioSelect)
    quantity = forms.IntegerField(label=_("Vehicles"), min_value=1, max_value=5)

    def __init__(self, *args, reservation=None, **kwargs):
        super().__init__(*args, reservation=reservation, **kwargs)
        self.fields["vehicle"].choices = vehicle_choices()
        self.fields["vehicle"].initial = next((key for key, name in self.fields["vehicle"].choices), "")
        if reservation is not None:
            airports = tuple(
                (airport.code, str(airport))
                for airport in reservation.property.destination.airports.filter(is_active=True)
            )
            self.fields["airport"].choices = airports
            self.fields["airport"].initial = airports[0][0] if airports else ""
            min_date = max(reservation.check_in - timedelta(days=2), timezone.localdate())
            max_date = reservation.check_out + timedelta(days=2)
            self.date_min = min_date.isoformat()
            self.date_max = max_date.isoformat()
        self.fields["departure_time"].initial = time(13, 0)
        self.fields["departure_time_end"].initial = time(14, 0)
        self.fields["return_time"].initial = time(13, 0)
        self.fields["return_time_end"].initial = time(14, 0)

    def clean(self):
        data = super().clean()
        if self.reservation is not None:
            min_date = max(self.reservation.check_in - timedelta(days=2), timezone.localdate())
            max_date = self.reservation.check_out + timedelta(days=2)
            dep_date = data.get("departure_date")
            ret_date = data.get("return_date")
            if dep_date and (dep_date < min_date or dep_date > max_date):
                self.add_error(
                    "departure_date",
                    _("The transport date must be close to your stay (between %(min)s and %(max)s).")
                    % {"min": min_date.strftime("%d/%m/%Y"), "max": max_date.strftime("%d/%m/%Y")},
                )
            if ret_date and (ret_date < min_date or ret_date > max_date):
                self.add_error(
                    "return_date",
                    _("The return date must be close to your stay (between %(min)s and %(max)s).")
                    % {"min": min_date.strftime("%d/%m/%Y"), "max": max_date.strftime("%d/%m/%Y")},
                )
        round_trip = data.get("trip_type") == "round_trip"
        if round_trip:
            if not data.get("return_date"):
                self.add_error("return_date", _("Choose the return date."))
            if not data.get("return_time"):
                self.add_error("return_time", _("Choose the return time."))
            if not data.get("return_time_end"):
                self.add_error("return_time_end", _("Choose the end of the return time range."))
            if data.get("return_date") and data.get("departure_date") and data["return_date"] < data["departure_date"]:
                self.add_error("return_date", _("The return date cannot be before departure."))
            if (
                data.get("return_date") == data.get("departure_date")
                and data.get("return_time")
                and data.get("departure_time")
                and data["return_time"] <= data["departure_time"]
            ):
                self.add_error("return_time", _("The return time must be after departure."))
        else:
            data["return_date"] = None
            data["return_time"] = None
            data["return_time_end"] = None
        if data.get("departure_time") and data.get("departure_time_end"):
            if data["departure_time_end"] <= data["departure_time"]:
                self.add_error("departure_time_end", _("The end time must be after the start time."))
        if data.get("return_time") and data.get("return_time_end"):
            if data["return_time_end"] <= data["return_time"]:
                self.add_error("return_time_end", _("The end time must be after the start time."))
        return data

    def build_charge(self):
        amount, details = transport_quote(
            trip_type=self.cleaned_data["trip_type"],
            vehicle_key=self.cleaned_data["vehicle"],
            quantity=self.cleaned_data["quantity"],
        )
        details["departure"] = _slot(self.cleaned_data.get("departure_date"), self.cleaned_data.get("departure_time"))
        details["departure_end"] = _slot(None, self.cleaned_data.get("departure_time_end"))
        details["return"] = _slot(self.cleaned_data.get("return_date"), self.cleaned_data.get("return_time"))
        details["return_end"] = _slot(None, self.cleaned_data.get("return_time_end"))
        details["airport"] = self.cleaned_data["airport"]
        return amount, details


class FlexibleCheckInForm(ServiceForm):
    service_date = forms.DateField(label=_("Service date"), widget=forms.HiddenInput)
    check_in_time = forms.TimeField(label=_("Check-in time"), widget=forms.TimeInput(attrs={"type": "time"}))

    def __init__(self, *args, reservation=None, **kwargs):
        super().__init__(*args, reservation=reservation, **kwargs)
        self.fields["check_in_time"].initial = time(7, 0)

    def clean_service_date(self):
        service_date = self.cleaned_data["service_date"]
        if self.reservation and not max(self.reservation.check_in, timezone.localdate()) <= service_date <= self.reservation.check_out:
            raise forms.ValidationError(_("Choose a date during your stay."))
        return service_date

    def build_charge(self):
        amount, details = flexible_checkin_quote(check_in_time=self.cleaned_data["check_in_time"], service=self.service)
        details["service_date"] = self.cleaned_data["service_date"].isoformat()
        return amount, details


class GroceryForm(ServiceForm):
    pack = forms.ChoiceField(label=_("Pack"), widget=forms.RadioSelect)
    delivery_date = forms.DateField(label=_("Delivery date"), widget=forms.HiddenInput)

    def __init__(self, *args, reservation=None, **kwargs):
        super().__init__(*args, reservation=reservation, **kwargs)
        packs = get_grocery_packs()
        self.fields["pack"].choices = tuple((pack.key, pack.name) for pack in packs)
        self.fields["pack"].initial = packs.first().key if packs.exists() else ""

    def clean_delivery_date(self):
        delivery_date = self.cleaned_data["delivery_date"]
        if self.reservation and not max(self.reservation.check_in, timezone.localdate()) <= delivery_date <= self.reservation.check_out:
            raise forms.ValidationError(_("Choose a delivery date during your stay."))
        return delivery_date

    def build_charge(self):
        amount, details = grocery_quote(pack_key=self.cleaned_data["pack"])
        details["delivery_date"] = self.cleaned_data["delivery_date"].isoformat()
        return amount, details


class CribForm(ServiceForm):
    quantity = forms.IntegerField(label=_("Cribs"), min_value=1, max_value=3)
    start_date = forms.DateField(label=_("First date"), widget=forms.HiddenInput)
    end_date = forms.DateField(label=_("Last date"), widget=forms.HiddenInput)

    def clean(self):
        data = super().clean()
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if self.reservation and start_date and end_date:
            if start_date < max(self.reservation.check_in, timezone.localdate()) or end_date > self.reservation.check_out:
                self.add_error("start_date", _("Choose dates within your stay."))
            if end_date <= start_date:
                self.add_error("end_date", _("The end date must be after the start date."))
        return data

    def build_charge(self):
        amount, details = crib_quote(quantity=self.cleaned_data["quantity"], service=self.service)
        if self.reservation:
            amount *= (self.cleaned_data["end_date"] - self.cleaned_data["start_date"]).days
        details["start_date"] = self.cleaned_data["start_date"].isoformat()
        details["end_date"] = self.cleaned_data["end_date"].isoformat()
        return amount, details


SERVICE_FORMS = {
    "transport": TransportForm,
    "flexible_checkin": FlexibleCheckInForm,
    "groceries": GroceryForm,
    "crib": CribForm,
}


def _slot(day, moment):

    if day and moment:
        return f"{day.isoformat()} {moment.strftime('%H:%M')}"
    if day:
        return day.isoformat()
    if moment:
        return moment.strftime("%H:%M")
    return ""
