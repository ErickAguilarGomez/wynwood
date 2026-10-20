from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from properties.models import Country

from .models import User


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"autocomplete": "email"}))


class RegistrationForm(UserCreationForm):


    first_name = forms.CharField(label=_("First name"), max_length=150)
    last_name = forms.CharField(label=_("Last name"), max_length=150)
    birth_date = forms.DateField(
        label=_("Date of birth"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    phone = forms.CharField(label=_("Phone"), max_length=32, required=False)
    country = forms.ChoiceField(
        label=_("Country"),
        required=False,
        choices=(),
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "birth_date", "phone", "email", "country", "password1", "password2")
        widgets = {"email": forms.EmailInput(attrs={"autocomplete": "email"})}

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].choices = [("", _("Select")), *[(country.code, country.name) for country in Country.objects.filter(is_active=True)]]
        self.fields["birth_date"].widget = forms.HiddenInput()

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        if birth_date and birth_date > timezone.localdate():
            raise forms.ValidationError(_("The date of birth cannot be in the future."))
        return birth_date
