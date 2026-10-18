import re

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from bookings.forms import country_choices

APPROVED_TEST_CARD = "4242424242424242"
REJECTED_TEST_CARD = "4000000000000002"


class SimulatedPaymentForm(forms.Form):
    card_number = forms.CharField(
        label=_("Card number"),
        max_length=23,
        widget=forms.TextInput(
            attrs={"autocomplete": "cc-number", "inputmode": "numeric", "placeholder": "0000 0000 0000 0000"}
        ),
    )
    expiration = forms.CharField(
        label=_("Expiration date"),
        max_length=7,
        widget=forms.TextInput(attrs={"autocomplete": "cc-exp", "placeholder": _("MM/YYYY")}),
    )
    security_code = forms.CharField(
        label=_("Security code (CVV)"),
        max_length=4,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "cc-csc", "inputmode": "numeric", "placeholder": "000"}, render_value=False
        ),
    )
    installments = forms.ChoiceField(
        label=_("Installments"),
        choices=(("", _("Select number of installments")), ("1", "1"), ("2", "2"), ("3", "3"), ("6", "6")),
    )
    address = forms.CharField(label=_("Address"), max_length=160)
    address_2 = forms.CharField(label=_("Address 2 (optional)"), max_length=160, required=False)
    country = forms.ChoiceField(label=_("Country"))
    region = forms.CharField(label=_("State / Region"), max_length=100)
    city = forms.CharField(label=_("City"), max_length=100)
    postal_code = forms.CharField(label=_("Postal code"), max_length=20)
    cardholder_confirmation = forms.BooleanField(
        label=_("The cardholder is the person making this reservation."), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].choices = [("", _("Select your country")), *country_choices()]
        placeholders = {
            "address": _("Enter your address"),
            "address_2": _("Enter your address"),
            "region": _("Enter your state"),
            "city": _("Enter city name"),
            "postal_code": "00000",
        }
        for name, placeholder in placeholders.items():
            self.fields[name].widget.attrs["placeholder"] = placeholder
        for field in self.fields.values():
            field.widget.attrs["class"] = "payment-input"
        self.fields["cardholder_confirmation"].widget.attrs["class"] = "payment-checkbox"

    def clean_card_number(self):
        card_number = re.sub(r"[\s-]", "", self.cleaned_data["card_number"])
        if card_number not in {APPROVED_TEST_CARD, REJECTED_TEST_CARD}:
            raise forms.ValidationError(_("Enter a valid test card number."))
        return card_number

    def clean_expiration(self):
        expiration = self.cleaned_data["expiration"].strip()
        match = re.fullmatch(r"(0[1-9]|1[0-2])/(\d{4})", expiration)
        if not match:
            raise forms.ValidationError(_("Enter the expiration date as MM/YYYY."))
        month, year = map(int, match.groups())
        today = timezone.localdate()
        if (year, month) < (today.year, today.month):
            raise forms.ValidationError(_("The card has expired."))
        return expiration

    def clean_security_code(self):
        code = self.cleaned_data["security_code"]
        if not re.fullmatch(r"\d{3,4}", code):
            raise forms.ValidationError(_("Enter a valid security code."))
        return code

    @property
    def payment_outcome(self):
        return "approved" if self.cleaned_data["card_number"] == APPROVED_TEST_CARD else "rejected"
