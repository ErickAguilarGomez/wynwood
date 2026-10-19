import logging
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone, translation

from .currencies import currency_symbol
from .email_backends import ResendEmailError
from .models import Reservation

logger = logging.getLogger(__name__)

SUPPORT_EMAIL = "sales@wynwoodhouse.com"


def _tax_percent(rate):

    value = Decimal(rate) * 100
    if value == value.to_integral_value():
        value = value.to_integral_value()
    return str(value)


def _absolute_url(url):
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return f"{settings.PUBLIC_BASE_URL}{url}"


def _hero_image_url(reservation):
    image = reservation.property.primary_image
    if not image:
        return ""
    try:
        return _absolute_url(image.image.url)
    except ValueError:
        return ""


def _email_context(reservation):
    return {
        "reservation": reservation,
        "first_name": reservation.user.first_name or reservation.user.email.split("@")[0],
        "hero_image_url": _hero_image_url(reservation),
        "site_url": settings.PUBLIC_BASE_URL,
        "email_static_url": _absolute_url(settings.STATIC_URL),
        "logo_url": settings.EMAIL_LOGO_URL or f"{_absolute_url(settings.STATIC_URL)}design/figma/ui/logo.svg",
        "support_url": f"mailto:{SUPPORT_EMAIL}",
        "benefits_url": settings.PUBLIC_BASE_URL,
        "language_code": reservation.language_code,
        "currency_symbol": currency_symbol(reservation.currency),
        "tax_percent": _tax_percent(reservation.tax_rate),
        "charges": reservation.charges.all(),
        "points": reservation.points_earned or round(float(reservation.total) * settings.WYNWOOD_POINTS_RATE),
    }


@shared_task(
    bind=True,
    autoretry_for=(OSError, ResendEmailError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def send_confirmation_email(self, reservation_id):
    with transaction.atomic():
        reservation = (
            Reservation.objects.select_for_update()
            .select_related("user", "property", "property__destination")
            .prefetch_related("charges")
            .get(pk=reservation_id)
        )
        if reservation.status != Reservation.Status.CONFIRMED or reservation.confirmation_sent_at:
            return
        with translation.override(reservation.language_code):
            context = _email_context(reservation)
            subject = render_to_string("bookings/email/confirmation_subject.txt", context).strip()
            text_body = render_to_string("bookings/email/confirmation.txt", context)
            html_body = render_to_string("bookings/email/confirmation.html", context)
            message = EmailMultiAlternatives(
                subject, text_body, settings.DEFAULT_FROM_EMAIL, [reservation.user.email]
            )
            message.attach_alternative(html_body, "text/html")
            message.send(fail_silently=False)
        reservation.confirmation_sent_at = timezone.now()
        reservation.save(update_fields=("confirmation_sent_at", "updated_at"))
        logger.info("reservation_confirmation_sent", extra={"reservation_id": reservation_id})
