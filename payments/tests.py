from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Reservation
from bookings.services import ReservationService
from core.demo_data import seed_catalogs
from core.tests.factories import create_property, create_user, future_dates

from .forms import SimulatedPaymentForm
from .models import Payment
from .services import PaymentService


def payment_data(card_number):
    today = timezone.localdate()
    return {
        "card_number": card_number,
        "expiration": f"{today.month:02d}/{today.year + 1}",
        "security_code": "123",
        "installments": "1",
        "address": "10 Main Street",
        "address_2": "",
        "country": "PE",
        "region": "Lima",
        "city": "Lima",
        "postal_code": "15001",
        "cardholder_confirmation": "on",
    }


class SimulatedPaymentFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_catalogs()

    def test_approved_test_card_is_normalized_and_accepted(self):
        form = SimulatedPaymentForm(payment_data("4242 4242 4242 4242"))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.payment_outcome, "approved")

    def test_rejected_test_card_is_accepted_as_a_decline_scenario(self):
        form = SimulatedPaymentForm(payment_data("4000 0000 0000 0002"))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.payment_outcome, "rejected")

    def test_other_card_numbers_are_rejected(self):
        form = SimulatedPaymentForm(payment_data("4111 1111 1111 1111"))

        self.assertFalse(form.is_valid())
        self.assertIn("card_number", form.errors)


class SimulatedPaymentFlowTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.property = create_property()
        check_in, check_out = future_dates()
        self.reservation = ReservationService.create(
            user=self.user,
            property_id=self.property.pk,
            check_in=check_in,
            check_out=check_out,
            guests=2,
        )
        PaymentService.start_checkout(self.reservation)
        self.client.force_login(self.user)
        self.url = reverse("payments:checkout", kwargs={"public_id": self.reservation.public_id})

    def test_approved_test_card_confirms_reservation_without_storing_card_data(self):
        with patch.object(PaymentService, "enqueue_confirmation") as enqueue_confirmation:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url, payment_data("4242 4242 4242 4242"))

        self.assertRedirects(response, self.reservation.get_absolute_url(), fetch_redirect_response=False)
        enqueue_confirmation.assert_called_once_with(self.reservation.pk)
        self.reservation.refresh_from_db()
        payment = Payment.objects.get(reservation=self.reservation)
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(payment.provider, "wynwood_simulator")
        self.assertEqual(set(payment.provider_snapshot), {"attempt_history", "amount", "currency", "outcome"})
        self.assertNotIn("4242424242424242", str(payment.provider_snapshot))

    def test_rejected_test_card_keeps_hold_and_allows_approved_retry(self):
        rejected_response = self.client.post(self.url, payment_data("4000 0000 0000 0002"))

        self.assertEqual(rejected_response.status_code, 302)
        self.assertEqual(rejected_response.url, f"{self.url}?method=card")
        self.reservation.refresh_from_db()
        payment = Payment.objects.get(reservation=self.reservation)
        self.assertEqual(self.reservation.status, Reservation.Status.PAYMENT_PENDING)
        self.assertEqual(payment.status, Payment.Status.REJECTED)

        approved_response = self.client.post(self.url, payment_data("4242 4242 4242 4242"))

        self.assertRedirects(approved_response, self.reservation.get_absolute_url(), fetch_redirect_response=False)
        self.reservation.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)
        self.assertEqual(payment.status, Payment.Status.APPROVED)
