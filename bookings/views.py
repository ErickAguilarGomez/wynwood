from datetime import time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from smtplib import SMTPException
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView

from payments.services import PaymentService
from properties.models import Property

from .additional_services import (
    GROCERY_PACKS,
    SERVICES,
    SERVICES_BY_KEY,
    VEHICLES,
    crib_quote,
    grocery_quote,
    service_for_kind,
    transport_quote,
)
from .currencies import currency_symbol
from .forms import COUNTRY_PHONE_PREFIXES, SERVICE_FORMS, CheckoutForm, MonthlyInquiryForm, parse_phone
from .models import Reservation, ReservationCharge
from .services import PropertyUnavailable, ReservationService, ReservationValidationError
from .tasks import SUPPORT_EMAIL


def money(value):
    return Decimal(value).quantize(Decimal("0.01"), ROUND_HALF_UP)


def _service_is_configured(charge, service):
    details = charge.details or {}
    if not details.get("configured"):
        return False
    if service.detail == "transport":
        departure = (details.get("departure") or "").partition(" ")[0]
        try:
            quantity = int(details.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        return bool(
            parse_date(departure)
            and " " in (details.get("departure") or "")
            and details.get("departure_end")
            and quantity > 0
            and details.get("vehicle")
            and details.get("airport")
            and (
                details.get("trip_type") != "round_trip"
                or (
                    parse_date((details.get("return") or "").partition(" ")[0])
                    and " " in (details.get("return") or "")
                    and details.get("return_end")
                )
            )
        )
    if service.detail == "flexible_checkin":
        return bool(parse_date(details.get("service_date", "")) and details.get("check_in_time"))
    if service.detail == "groceries":
        return bool(parse_date(details.get("delivery_date", "")) and details.get("pack"))
    if service.detail == "crib":
        try:
            quantity = int(details.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        return bool(
            parse_date(details.get("start_date", ""))
            and parse_date(details.get("end_date", ""))
            and quantity > 0
        )
    return False


class MonthlyInquiryView(View):
    def post(self, request, *args, **kwargs):
        property = get_object_or_404(Property, slug=kwargs["slug"], is_active=True)
        form = MonthlyInquiryForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Enter your name, email address and phone number."))
            return redirect(property.get_absolute_url())

        data = form.cleaned_data
        phone = f"{data['phone_code']} {data['phone']}"
        subject = _("Monthly stay inquiry: %(property)s") % {"property": property.title}
        body = "\n".join(
            (
                f"{_('Property')}: {property.title}",
                f"{_('Name')}: {data['full_name']}",
                f"{_('Email address')}: {data['email']}",
                f"{_('Phone')}: {phone}",
                f"{_('Property link')}: {request.build_absolute_uri(property.get_absolute_url())}",
            )
        )
        try:
            sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [SUPPORT_EMAIL])
        except (OSError, SMTPException):
            sent = 0

        if sent:
            messages.success(request, _("Your information was sent to our reservations team."))
        else:
            messages.error(request, _("We could not send your request. Please try again."))
        return redirect(property.get_absolute_url())


class CheckoutView(FormView):









    template_name = "bookings/checkout.html"
    form_class = CheckoutForm

    def dispatch(self, request, *args, **kwargs):
        self.property = get_object_or_404(
            Property.objects.select_related("destination").prefetch_related("images"),
            slug=kwargs["slug"],
            is_active=True,
        )
        self.edit_reservation = None
        reservation_source = request.GET if request.method == "GET" else request.POST
        reservation_id = reservation_source.get("reservation_id")
        if reservation_id:
            if not request.user.is_authenticated:
                raise Http404
            self.edit_reservation = get_object_or_404(
                Reservation.objects.select_related("property"),
                public_id=reservation_id,
                property=self.property,
                user=request.user,
                status=Reservation.Status.PAYMENT_PENDING,
                expires_at__gt=timezone.now(),
            )
        if request.method == "GET":
            booking_type = (request.GET.get("booking_type") or "daily").strip().lower()
            if booking_type == "monthly" and self.edit_reservation is None:
                messages.error(request, _("Monthly stays are handled by our reservations team."))
                return redirect(self.property.get_absolute_url())
            if booking_type != "daily":
                booking_type = "daily"
            email = (request.GET.get("email") or getattr(request.user, "email", "")).strip()
            phone = (request.GET.get("phone") or getattr(request.user, "phone", "")).strip()
            check_in = parse_date((request.GET.get("check_in") or "").strip())
            check_out = parse_date((request.GET.get("check_out") or "").strip())
            if self.edit_reservation is None and (not email or not phone or not check_in or not check_out):
                messages.error(
                    request,
                    _("Complete your email address, phone number, arrival date and departure date to continue."),
                )
                return redirect(self.property.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def selected_booking(self):

        source = self.request.POST if self.request.method == "POST" else self.request.GET
        today = timezone.localdate()
        reservation = self.edit_reservation
        booking_type = (source.get("booking_type") or "daily").strip().lower()
        if booking_type not in ("daily", "monthly"):
            booking_type = reservation.booking_type if reservation else "daily"
        check_in = parse_date((source.get("check_in") or "").strip()) or (
            reservation.check_in if reservation else today + timedelta(days=1)
        )
        default_days = 30 if booking_type == "monthly" else 3
        check_out = parse_date((source.get("check_out") or "").strip()) or (
            reservation.check_out if reservation else check_in + timedelta(days=default_days)
        )
        if check_out <= check_in:
            check_out = check_in + timedelta(days=default_days)
        try:
            guests = int(source.get("guests") or (reservation.guests if reservation else 2))
        except (TypeError, ValueError):
            guests = 2
        return check_in, check_out, min(max(guests, 1), self.property.max_guests), booking_type

    def get_initial(self):
        check_in, check_out, guests, booking_type = self.selected_booking()
        initial = {
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "booking_type": booking_type,
        }
        dest_country = getattr(getattr(self.property, "destination", None), "country_code", None)
        fallback_prefix = COUNTRY_PHONE_PREFIXES.get(dest_country, "+51")

        if self.request.GET.get("email"):
            initial["email"] = self.request.GET.get("email", "").strip()
        if self.request.GET.get("phone"):
            initial["phone"] = self.request.GET.get("phone", "").strip()
        if self.request.GET.get("phone_code"):
            initial["phone_code"] = self.request.GET.get("phone_code", "").strip()

        user = self.request.user
        if user.is_authenticated:
            if user.email:
                initial["email"] = user.email
            full_name = user.get_full_name().strip()
            if not full_name:
                full_name = f"{user.first_name} {user.last_name}".strip()
            if full_name:
                initial["full_name"] = full_name
            if user.country:
                initial["nationality"] = user.country
            if user.birth_date:
                initial["birth_date"] = user.birth_date

            phone_code, phone_number = parse_phone(
                user.phone,
                country=user.country or dest_country,
                default_prefix=fallback_prefix,
            )
            initial["phone_code"] = phone_code
            if phone_number:
                initial["phone"] = phone_number
        else:
            if "phone_code" not in initial:
                initial["phone_code"] = fallback_prefix
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["property"] = self.property
        kwargs["user"] = self.request.user
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        check_in, check_out, guests, booking_type = self.selected_booking()
        nights = (check_out - check_in).days
        if booking_type == "monthly":
            monthly_rate = self.property.effective_price_per_month
            subtotal = money((monthly_rate / Decimal("30")) * Decimal(nights))
            effective_nightly = money(subtotal / Decimal(nights))
        else:
            monthly_rate = None
            effective_nightly = self.property.price_per_night
            subtotal = money(self.property.price_per_night * nights)
        cleaning_fee = money(self.property.cleaning_fee)
        discount = Decimal("0.00")
        total = money(subtotal + cleaning_fee - discount)
        if self.edit_reservation:
            selected_service_keys = (
                self.request.POST.getlist("selected_services")
                if self.request.method == "POST"
                else [
                    service.key
                    for service in SERVICES
                    if self.edit_reservation.charges.filter(kind=service.kind).exists()
                ]
            )
        elif self.request.method == "POST" and context["form"].errors:
            selected_service_keys = []
        else:
            selected_service_keys = (
                self.request.POST.getlist("selected_services")
                if self.request.method == "POST"
                else self.request.GET.getlist("selected_services")
            )
        context.update(
            {
                "detail_view": True,
                "property": self.property,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
                "booking_type": booking_type,
                "monthly_rate": monthly_rate,
                "nights": nights,
                "nightly_rate": effective_nightly,
                "subtotal": subtotal,
                "cleaning_fee": cleaning_fee,
                "discount_amount": discount,
                "total": total,
                "points": max(round(float(total) * settings.WYNWOOD_POINTS_RATE), 0),
                "currency_symbol": currency_symbol(settings.BOOKING_CURRENCY),
                "points_rate": settings.WYNWOOD_POINTS_RATE,
                "hide_password": getattr(context.get("form"), "hide_password", False),
                "selected_service_keys": selected_service_keys,
                "edit_reservation": self.edit_reservation,
            }
        )
        return context

    def form_invalid(self, form):
        email_errors = form.errors.as_data().get("email", [])
        if any(error.code == "account_exists" for error in email_errors):
            messages.info(self.request, _("An account with this email already exists. Log in to continue."))
            checkout_params = []
            for key in ("check_in", "check_out", "guests", "booking_type"):
                value = form.cleaned_data.get(key)
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                value = value or self.request.POST.get(key)
                if value:
                    checkout_params.append((key, value))
            checkout_params.extend(
                ("selected_services", key) for key in self.request.POST.getlist("selected_services")
            )
            checkout_url = reverse("bookings:checkout", kwargs={"slug": self.property.slug})
            checkout_url = f"{checkout_url}?{urlencode(checkout_params)}"
            email = (self.request.POST.get("email") or "").strip().lower()
            login_params = urlencode({"next": checkout_url, "email": email})
            return redirect(f"{reverse('accounts:login')}?{login_params}")
        return super().form_invalid(form)

    def form_valid(self, form):
        user = self.request.user
        if not user.is_authenticated:
            user = self._create_guest_account(form)
            if user is None:
                return self.form_invalid(form)
        else:
            self._update_user_profile(user, form.cleaned_data)
        if self.edit_reservation:
            try:
                reservation = ReservationService.update_stay(
                    reservation=self.edit_reservation,
                    check_in=form.cleaned_data["check_in"],
                    check_out=form.cleaned_data["check_out"],
                    guests=form.cleaned_data["guests"],
                    booking_type=form.cleaned_data.get("booking_type") or "daily",
                    selected_services=self.request.POST.getlist("selected_services"),
                )
            except (PropertyUnavailable, ReservationValidationError, IntegrityError) as error:
                form.add_error(None, error)
                return self.form_invalid(form)
            return redirect("bookings:services", public_id=reservation.public_id)
        try:
            reservation = ReservationService.create(
                user=user,
                property_id=self.property.pk,
                language_code=self.request.LANGUAGE_CODE,
                check_in=form.cleaned_data["check_in"],
                check_out=form.cleaned_data["check_out"],
                guests=form.cleaned_data["guests"],
                booking_type=form.cleaned_data.get("booking_type") or "daily",
            )
        except (PropertyUnavailable, ReservationValidationError) as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        selected_services = self.request.POST.getlist("selected_services")
        for key in selected_services:
            if key == "flexible-checkin":
                ReservationService.add_service(
                    reservation=reservation,
                    kind=ReservationCharge.Kind.EARLY_CHECK_IN,
                    amount=Decimal("26.00"),
                    details={"configured": False},
                )
            elif key == "baby-crib":
                nights = max((reservation.check_out - reservation.check_in).days, 1)
                ReservationService.add_service(
                    reservation=reservation,
                    kind=ReservationCharge.Kind.CRIB,
                    amount=Decimal("15.00") * nights,
                    details={"configured": False},
                )
            elif key == "transport":
                ReservationService.add_service(
                    reservation=reservation,
                    kind=ReservationCharge.Kind.TRANSPORT,
                    amount=Decimal("13.00"),
                    details={"configured": False},
                )
            elif key == "groceries":
                ReservationService.add_service(
                    reservation=reservation,
                    kind=ReservationCharge.Kind.GROCERY,
                    amount=Decimal("18.00"),
                    details={"configured": False},
                )

        next_service = next((key for key in selected_services if key in SERVICES_BY_KEY), None)
        if next_service:
            return redirect(
                "bookings:service_detail",
                public_id=reservation.public_id,
                service_key=next_service,
            )

        return redirect("bookings:services", public_id=reservation.public_id)

    def _create_guest_account(self, form):

        data = form.cleaned_data
        first_name, _, last_name = data["full_name"].strip().partition(" ")
        phone_code = (data.get("phone_code") or "").strip()
        phone_num = (data.get("phone") or "").strip()
        if phone_num:
            phone = f"{phone_code} {phone_num}".strip() if phone_code and not phone_num.startswith("+") else phone_num
        else:
            phone = ""
        nationality = (data.get("nationality") or "").strip()
        birth_date = data.get("birth_date")
        try:
            user = get_user_model().objects.create_user(
                email=data["email"],
                password=data["password"],
                first_name=first_name[:150],
                last_name=last_name[:150],
                phone=phone[:32],
                country=nationality,
                birth_date=birth_date,
            )
        except IntegrityError:
            form.add_error(
                "email",
                ValidationError(
                    _("An account with this email already exists. Log in to continue."),
                    code="account_exists",
                ),
            )
            return None
        login(self.request, user)
        return user

    def _update_user_profile(self, user, data):

        updated_fields = []
        full_name = (data.get("full_name") or "").strip()
        if full_name:
            first_name, _, last_name = full_name.partition(" ")
            first_name = first_name[:150]
            last_name = last_name[:150]
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated_fields.append("first_name")
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated_fields.append("last_name")
        nationality = (data.get("nationality") or "").strip()
        if nationality and user.country != nationality:
            user.country = nationality
            updated_fields.append("country")
        birth_date = data.get("birth_date")
        if birth_date and user.birth_date != birth_date:
            user.birth_date = birth_date
            updated_fields.append("birth_date")
        phone_num = (data.get("phone") or "").strip()
        phone_code = (data.get("phone_code") or "").strip()
        if phone_num:
            full_phone = f"{phone_code} {phone_num}".strip() if phone_code and not phone_num.startswith("+") else phone_num
            if user.phone != full_phone[:32]:
                user.phone = full_phone[:32]
                updated_fields.append("phone")
        if updated_fields:
            user.save(update_fields=updated_fields)


class ReservationServicesView(LoginRequiredMixin, TemplateView):


    template_name = "bookings/services.html"

    def dispatch(self, request, *args, **kwargs):
        self.reservation = get_object_or_404(
            Reservation.objects.select_related("property", "property__destination").prefetch_related(
                "charges", "property__images"
            ),
            public_id=kwargs["public_id"],
            user=request.user,
        )
        if self.reservation.status == Reservation.Status.CONFIRMED:
            return redirect(self.reservation)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        added = {charge.kind: charge for charge in self.reservation.charges.all()}
        context.update(
            _reservation_context(self.reservation),
            services=[
                {"service": service, "charge": added.get(service.kind)}
                for service in SERVICES
            ],
            editable=self.reservation.status == Reservation.Status.PAYMENT_PENDING,
        )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "update_stay":
            try:
                check_in = parse_date(request.POST.get("check_in", ""))
                check_out = parse_date(request.POST.get("check_out", ""))
                guests = int(request.POST.get("guests", ""))
                if check_in is None or check_out is None:
                    raise ReservationValidationError(_("Select valid check-in and check-out dates."))
                selected_services = [
                    service.key
                    for service in SERVICES
                    if self.reservation.charges.filter(kind=service.kind).exists()
                ]
                ReservationService.update_stay(
                    reservation=self.reservation,
                    check_in=check_in,
                    check_out=check_out,
                    guests=guests,
                    booking_type=self.reservation.booking_type,
                    selected_services=selected_services,
                )
            except (TypeError, ValueError, ReservationValidationError, PropertyUnavailable, IntegrityError) as error:
                messages.error(request, str(error) or _("Unable to update this stay."))
            else:
                messages.success(request, _("Your stay details were updated."))
            return redirect("bookings:services", public_id=self.reservation.public_id)

        if (
            self.reservation.status != Reservation.Status.PAYMENT_PENDING
            or self.reservation.expires_at <= timezone.now()
        ):
            if self.reservation.status == Reservation.Status.PAYMENT_PENDING:
                Reservation.objects.filter(pk=self.reservation.pk).update(status=Reservation.Status.EXPIRED)
            messages.error(request, _("The reservation hold has expired. Please start a new reservation."))
            return redirect(self.reservation.property.get_absolute_url())

        for charge in ReservationCharge.objects.filter(reservation=self.reservation).order_by("id"):
            service = service_for_kind(charge.kind)
            if service and not _service_is_configured(charge, service):
                messages.warning(
                    request,
                    _("Complete the configuration for %(service)s before continuing to payment.")
                    % {"service": service.name},
                )
                return redirect(
                    "bookings:service_detail",
                    public_id=self.reservation.public_id,
                    service_key=service.key,
                )
        PaymentService.start_checkout(self.reservation)
        return redirect("payments:checkout", public_id=self.reservation.public_id)


class ServiceDetailView(LoginRequiredMixin, FormView):


    template_name = "bookings/service_detail.html"

    def dispatch(self, request, *args, **kwargs):
        self.reservation = get_object_or_404(
            Reservation.objects.select_related("property", "property__destination").prefetch_related(
                "charges", "property__images"
            ),
            public_id=kwargs["public_id"],
            user=request.user,
        )
        self.service = SERVICES_BY_KEY.get(kwargs["service_key"])
        if self.service is None:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        return SERVICE_FORMS[self.service.detail]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["reservation"] = self.reservation
        return kwargs

    def get_initial(self):
        charge = self.reservation.charges.filter(kind=self.service.kind).first()
        if charge is None or not (charge.details or {}).get("configured"):
            return super().get_initial()
        details = charge.details or {}
        if self.service.detail == "transport":
            initial = {
                "trip_type": details.get("trip_type", "one_way"),
                "vehicle": details.get("vehicle", "suv"),
                "quantity": details.get("quantity", 1),
                **({"airport": details["airport"]} if details.get("airport") else {}),
            }
            for key, field_date, field_time in (
                ("departure", "departure_date", "departure_time"),
                ("return", "return_date", "return_time"),
            ):
                day, _, moment = details.get(key, "").partition(" ")
                initial[field_date] = parse_date(day) if day else None
                initial[field_time] = time.fromisoformat(moment) if moment else None
            for key, field in (("departure_end", "departure_time_end"), ("return_end", "return_time_end")):
                initial[field] = time.fromisoformat(details[key]) if details.get(key) else None
            return initial
        if self.service.detail == "groceries":
            return {
                "pack": details.get("pack", GROCERY_PACKS[0].key),
                "delivery_date": parse_date(details.get("delivery_date", "")),
            }
        if self.service.detail == "crib":
            return {
                "quantity": details.get("quantity", 1),
                "start_date": parse_date(details.get("start_date", "")),
                "end_date": parse_date(details.get("end_date", "")),
            }
        if self.service.detail == "flexible_checkin":
            initial = {
                "service_date": parse_date(details.get("service_date", "")),
            }
            if details.get("check_in_time"):
                initial["check_in_time"] = time.fromisoformat(details["check_in_time"])
            return initial
        return super().get_initial()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = kwargs.get("form") or self.get_form()
        context.update(
            _reservation_context(self.reservation),
            services=[
                {"service": service, "charge": self.reservation.charges.filter(kind=service.kind).first()}
                for service in SERVICES
            ],
            service=self.service,
            service_key=self.service.key,
            return_to_payment=self.request.GET.get("next") == "payment",
            config_template=f"bookings/config/{self.service.detail}.html",
            existing_charge=self.reservation.charges.filter(kind=self.service.kind).first(),
            vehicles=VEHICLES,
            grocery_packs=GROCERY_PACKS,
            quote=self._quote(form),
        )
        context["existing_service_amount"] = context["existing_charge"].amount if context["existing_charge"] else 0
        context["service_configured"] = bool(
            context["existing_charge"] and _service_is_configured(context["existing_charge"], self.service)
        )
        return context

    def _quote(self, form):
        values = form.cleaned_data if form.is_bound and form.is_valid() else {}
        if self.service.detail == "transport":
            amount, details = transport_quote(
                trip_type=values.get("trip_type") or "one_way",
                vehicle_key=values.get("vehicle") or "suv",
                quantity=values.get("quantity") or 1,
            )
            return {"amount": amount, **details}
        if self.service.detail == "crib":
            amount = crib_quote(quantity=values.get("quantity") or 1)[0]
            start_date = values.get("start_date") or self.reservation.check_in
            end_date = values.get("end_date") or self.reservation.check_out
            nights = max((end_date - start_date).days, 1) if start_date and end_date else self.reservation.nights
            return {"amount": amount * nights}
        if self.service.detail == "groceries":
            pack = values.get("pack") or GROCERY_PACKS[0].key
            return {"amount": grocery_quote(pack_key=pack)[0], "pack": pack}
        return {"amount": self.service.base_price}

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "remove":
            return self._remove()
        if request.POST.get("action") == "configure":
            return redirect(
                "bookings:service_detail",
                public_id=self.reservation.public_id,
                service_key=self.service.key,
            )
        return super().post(request, *args, **kwargs)

    def _remove(self):
        try:
            ReservationService.remove_service(reservation=self.reservation, kind=self.service.kind)
            messages.success(self.request, _("Service removed from your reservation."))
        except ReservationValidationError as error:
            messages.error(self.request, error)
        if self.request.GET.get("next") == "payment" or self.request.POST.get("next") == "payment":
            return redirect("payments:checkout", public_id=self.reservation.public_id)
        return redirect("bookings:services", public_id=self.reservation.public_id)

    def form_valid(self, form):
        try:
            amount, details = form.build_charge()
            details["configured"] = True
            ReservationService.add_service(
                reservation=self.reservation,
                kind=self.service.kind,
                amount=amount,
                details=details,
            )
        except ReservationValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, _("Service added to your reservation."))
        for charge in ReservationCharge.objects.filter(reservation=self.reservation).order_by("id"):
            service = service_for_kind(charge.kind)
            if service and not _service_is_configured(charge, service):
                messages.info(
                    self.request,
                    _("Complete the configuration for %(service)s before continuing to payment.")
                    % {"service": service.name},
                )
                return redirect(
                    "bookings:service_detail",
                    public_id=self.reservation.public_id,
                    service_key=service.key,
                )
        if self.request.GET.get("next") == "payment" or self.request.POST.get("next") == "payment":
            return redirect("payments:checkout", public_id=self.reservation.public_id)
        return redirect("bookings:services", public_id=self.reservation.public_id)


def _reservation_context(reservation):

    charges = list(reservation.charges.all())
    for charge in charges:
        service = service_for_kind(charge.kind)
        charge.label = service.name if service else charge.get_kind_display()
    return {
        "reservation": reservation,
        "property": reservation.property,
        "currency_symbol": currency_symbol(reservation.currency),
        "charges": charges,
        "points": reservation.points_earned,
        "detail_view": True,
        "whatsapp_url": settings.WYNWOOD_WHATSAPP_URL,
    }


class ConfirmationView(LoginRequiredMixin, DetailView):
    model = Reservation
    template_name = "bookings/confirmation.html"
    context_object_name = "reservation"
    slug_field = "public_id"
    slug_url_kwarg = "public_id"

    def get_queryset(self):
        return (
            Reservation.objects.filter(user=self.request.user, status=Reservation.Status.CONFIRMED)
            .select_related("property", "property__destination")
            .prefetch_related("charges", "property__images")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservation = context["reservation"]
        context.update(
            {
                "detail_view": True,
                "points": reservation.points_earned,
                "currency_symbol": currency_symbol(reservation.currency),
                "charges": reservation.charges.all(),
                "whatsapp_url": settings.WYNWOOD_WHATSAPP_URL,
            }
        )
        return context


class MyBookingsView(LoginRequiredMixin, TemplateView):
    template_name = "bookings/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reservations"] = self.request.user.reservations.select_related("property").all()
        return context
