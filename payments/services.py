import logging
import uuid

from django.db import transaction
from django.utils import timezone

from bookings.models import Reservation
from bookings.tasks import send_confirmation_email

from .models import Payment

logger = logging.getLogger(__name__)


class PaymentService:
    provider = "wynwood_simulator"

    @classmethod
    def start_checkout(cls, reservation):
        payment, _ = Payment.objects.get_or_create(reservation=reservation)
        snapshot = payment.provider_snapshot or {}
        history = list(snapshot.get("attempt_history", []))
        if (
            payment.status != Payment.Status.CREATED
            or payment.transaction_id
            or payment.checkout_reference_id
            or payment.provider != cls.provider
        ):
            history.append(
                {
                    "provider": payment.provider,
                    "status": payment.status,
                    "transaction_id": payment.transaction_id,
                    "checkout_reference_id": payment.checkout_reference_id,
                    "status_detail": payment.status_detail,
                    "provider_snapshot": snapshot,
                }
            )
        payment.provider = cls.provider
        payment.status = Payment.Status.PENDING
        payment.transaction_id = None
        payment.checkout_reference_id = None
        payment.status_detail = ""
        payment.provider_snapshot = {"attempt_history": history}
        payment.save(
            update_fields=(
                "provider",
                "status",
                "transaction_id",
                "checkout_reference_id",
                "status_detail",
                "provider_snapshot",
                "updated_at",
            )
        )
        return payment

    @classmethod
    @transaction.atomic
    def process_simulated_payment(cls, reservation, outcome):
        reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
        payment = Payment.objects.select_for_update().get(reservation=reservation)
        if reservation.status != Reservation.Status.PAYMENT_PENDING:
            raise ValueError("This reservation is not awaiting payment.")
        if reservation.expires_at <= timezone.now():
            raise ValueError("The reservation hold has expired.")

        payment.provider = cls.provider
        payment.status = Payment.Status.APPROVED if outcome == "approved" else Payment.Status.REJECTED
        payment.transaction_id = f"WYN-{uuid.uuid4().hex[:16].upper()}"
        payment.status_detail = "Approved" if outcome == "approved" else "Declined"
        payment.provider_snapshot = {
            "attempt_history": (payment.provider_snapshot or {}).get("attempt_history", []),
            "amount": str(reservation.total),
            "currency": reservation.currency,
            "outcome": outcome,
        }
        payment.save(
            update_fields=("provider", "status", "transaction_id", "status_detail", "provider_snapshot", "updated_at")
        )

        if payment.status == Payment.Status.APPROVED:
            reservation.status = Reservation.Status.CONFIRMED
            reservation.confirmed_at = timezone.now()
            reservation.save(update_fields=("status", "confirmed_at", "updated_at"))
            transaction.on_commit(lambda: cls.enqueue_confirmation(reservation.pk))
        return payment

    @staticmethod
    def enqueue_confirmation(reservation_id):
        try:
            send_confirmation_email.apply_async(args=(reservation_id,), retry=True, retry_policy={"max_retries": 3})
        except Exception:
            logger.exception("confirmation_email_enqueue_failed", extra={"reservation_id": reservation_id})
