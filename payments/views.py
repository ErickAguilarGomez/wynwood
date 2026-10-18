from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views import View

from bookings.additional_services import SERVICES, service_for_kind
from bookings.models import Reservation
from bookings.views import _reservation_context, _service_is_configured

from .forms import SimulatedPaymentForm
from .models import Payment
from .services import PaymentService


class PaymentCheckoutView(LoginRequiredMixin, View):
    template_name = "payments/checkout.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.reservation = get_object_or_404(
            Reservation.objects.select_related("property", "property__destination").prefetch_related(
                "charges", "property__images"
            ),
            public_id=kwargs["public_id"],
            user=request.user,
        )
        if self.reservation.status == Reservation.Status.CONFIRMED:
            return redirect(self.reservation)
        if self.reservation.status != Reservation.Status.PAYMENT_PENDING:
            return redirect("bookings:services", public_id=self.reservation.public_id)
        if self.reservation.expires_at <= timezone.now():
            self.reservation.status = Reservation.Status.EXPIRED
            self.reservation.save(update_fields=("status", "updated_at"))
            messages.error(request, _("The reservation hold has expired. Please start a new reservation."))
            return redirect(self.reservation.property.get_absolute_url())
        self.payment = Payment.objects.filter(reservation=self.reservation).first()
        if self.payment is None:
            return redirect("bookings:services", public_id=self.reservation.public_id)
        for charge in self.reservation.charges.all():
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
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, form=None):
        added = {charge.kind: charge for charge in self.reservation.charges.all()}
        country_code = (self.reservation.property.destination.country_code or "").upper()
        if get_language() == "en":
            tax_label = _("VAT")
        else:
            tax_label = {"PE": _("IGV"), "PA": _("ITBMS")}.get(country_code, _("IVA"))
        checkout_images = {
            "flexible-checkin": "design/figma/checkout/service-checkin.jpg",
            "transport": "design/figma/checkout/service-transport.jpg",
            "groceries": "design/figma/checkout/service-fridge.jpg",
            "baby-crib": "design/figma/checkout/service-crib.jpg",
        }
        return {
            **_reservation_context(self.reservation),
            "form": form or SimulatedPaymentForm(),
            "services": [
                {
                    "service": service,
                    "charge": added.get(service.kind),
                    "checkout_image": checkout_images[service.key],
                }
                for service in SERVICES
            ],
            "test_approved_card": "4242 4242 4242 4242",
            "test_rejected_card": "4000 0000 0000 0002",
            "payment_checkout": True,
            "tax_label": tax_label,
            "tax_percent": self.reservation.tax_rate * 100,
            "payment_form_open": self.request.GET.get("method") == "card" or bool(form and form.errors),
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, *args, **kwargs):
        form = SimulatedPaymentForm(request.POST)
        if not form.is_valid():
            form.data = request.POST.copy()
            form.data["card_number"] = ""
            form.data["security_code"] = ""
            return render(request, self.template_name, self.get_context_data(form), status=400)
        try:
            payment = PaymentService.process_simulated_payment(self.reservation, form.payment_outcome)
        except ValueError:
            self.reservation.refresh_from_db()
            if self.reservation.status == Reservation.Status.PAYMENT_PENDING:
                self.reservation.status = Reservation.Status.EXPIRED
                self.reservation.save(update_fields=("status", "updated_at"))
            messages.error(request, _("The reservation hold has expired. Please start a new reservation."))
            return redirect(self.reservation.property.get_absolute_url())
        if payment.status == Payment.Status.APPROVED:
            return redirect(self.reservation.get_absolute_url())
        messages.error(request, _("The test card was declined. Use the approved test card or try again."))
        return redirect(f"{reverse('payments:checkout', kwargs={'public_id': self.reservation.public_id})}?method=card")
