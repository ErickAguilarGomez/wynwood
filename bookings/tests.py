from datetime import date, timedelta
from decimal import Decimal

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.tests.factories import create_property, create_user, future_dates
from properties.models import Destination

from .models import Reservation
from .services import PropertyUnavailable, ReservationService, ReservationValidationError
from .tasks import send_confirmation_email


class ReservationServiceTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.property = create_property()
        self.check_in, self.check_out = future_dates()

    def test_calculates_total_and_holds_dates(self):
        reservation = ReservationService.create(
            user=self.user,
            property_id=self.property.pk,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
        )
        self.assertEqual(reservation.nights, 3)
        self.assertEqual(reservation.total, 325)
        self.assertEqual(reservation.status, Reservation.Status.PAYMENT_PENDING)
        self.assertEqual(reservation.currency, "USD")

    def test_freezes_tax_rate_and_points_for_the_property_country(self):
        reservation = ReservationService.create(
            user=self.user,
            property_id=self.property.pk,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
        )
        self.assertEqual(reservation.tax_rate, Decimal("0.21"))
        self.assertEqual(reservation.tax_amount, Decimal("56.40"))
        self.assertEqual(reservation.total, Decimal("325.00"))
        self.assertEqual(reservation.points_earned, 133)

    def test_uses_country_tax_rate(self):
        lima = Destination.objects.create(
            slug="lima", name_es="Lima", name_en="Lima", country_code="PE"
        )
        peru_property = create_property(slug="lima-home", destination=lima)
        reservation = ReservationService.create(
            user=self.user,
            property_id=peru_property.pk,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
        )
        self.assertEqual(reservation.tax_rate, Decimal("0.18"))
        self.assertEqual(reservation.tax_amount, Decimal("49.58"))

    def test_adds_extra_charges_to_the_total(self):
        reservation = ReservationService.create(
            user=self.user,
            property_id=self.property.pk,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
            charges=[{"kind": "late_check_in", "amount": Decimal("57")}],
        )
        self.assertEqual(reservation.total, Decimal("382.00"))
        self.assertEqual(reservation.tax_amount, Decimal("66.30"))
        self.assertEqual(reservation.charges.count(), 1)
        charge = reservation.charges.get()
        self.assertEqual(charge.kind, "late_check_in")
        self.assertEqual(charge.amount, Decimal("57.00"))

    def test_rejects_unknown_charge_kind(self):
        with self.assertRaises(ReservationValidationError):
            ReservationService.create(
                user=self.user,
                property_id=self.property.pk,
                check_in=self.check_in,
                check_out=self.check_out,
                guests=2,
                charges=[{"kind": "bogus", "amount": 10}],
            )

    def test_subtracts_points_discount_from_the_total(self):
        reservation = ReservationService.create(
            user=self.user,
            property_id=self.property.pk,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
            discount=Decimal("22"),
        )
        self.assertEqual(reservation.discount_amount, Decimal("22.00"))
        self.assertEqual(reservation.total, Decimal("303.00"))
        self.assertEqual(reservation.tax_amount, Decimal("52.59"))
        self.assertEqual(reservation.points_earned, 124)

    def test_rejects_negative_discount(self):
        with self.assertRaises(ReservationValidationError):
            ReservationService.create(
                user=self.user,
                property_id=self.property.pk,
                check_in=self.check_in,
                check_out=self.check_out,
                guests=2,
                discount=Decimal("-1"),
            )

    def test_rejects_overlapping_dates(self):
        ReservationService.create(
            user=self.user,
            property_id=self.property.pk,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
        )
        other_user = create_user(email="another-guest@example.com")
        with self.assertRaises(PropertyUnavailable):
            ReservationService.create(
                user=other_user,
                property_id=self.property.pk,
                check_in=self.check_in + timedelta(days=1),
                check_out=self.check_out + timedelta(days=1),
                guests=2,
            )

    def test_releases_expired_hold(self):
        old = ReservationService.create(
            user=self.user,
            property_id=self.property.pk,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
        )
        Reservation.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        replacement = ReservationService.create(
            user=self.user,
            property_id=self.property.pk,
            check_in=self.check_in,
            check_out=self.check_out,
            guests=2,
        )
        old.refresh_from_db()
        self.assertEqual(old.status, Reservation.Status.EXPIRED)
        self.assertNotEqual(old.pk, replacement.pk)

    def test_rejects_invalid_domain_input(self):
        with self.assertRaises(ReservationValidationError):
            ReservationService.create(
                user=self.user,
                property_id=self.property.pk,
                check_in=timezone.localdate() - timedelta(days=1),
                check_out=timezone.localdate() + timedelta(days=1),
                guests=2,
            )


class ReservationConstraintTests(TransactionTestCase):
    reset_sequences = True

    def test_database_rejects_overlapping_blocking_reservations(self):
        user = create_user()
        property = create_property()
        check_in, check_out = future_dates()
        values = {
            "user": user,
            "property": property,
            "check_in": check_in,
            "check_out": check_out,
            "guests": 2,
            "nightly_rate": 100,
            "nights": 3,
            "subtotal": 300,
            "cleaning_fee": 25,
            "total": 325,
            "expires_at": timezone.now() + timedelta(minutes=20),
        }
        Reservation.objects.create(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reservation.objects.create(**values)


class SimulatedCheckoutStartTests(TestCase):
    def test_starts_simulated_checkout_without_releasing_reservation_hold(self):
        user = create_user()
        property = create_property()
        check_in, check_out = future_dates()
        reservation = ReservationService.create(
            user=user,
            property_id=property.pk,
            check_in=check_in,
            check_out=check_out,
            guests=2,
        )
        self.client.force_login(user)
        response = self.client.post(reverse("bookings:services", kwargs={"public_id": reservation.public_id}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("payments:checkout", kwargs={"public_id": reservation.public_id}),
            fetch_redirect_response=False,
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PAYMENT_PENDING)
        self.assertEqual(reservation.payment.provider, "wynwood_simulator")
        self.assertEqual(reservation.payment.status, "pending")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ConfirmationEmailTests(TestCase):
    def test_breaks_down_extra_charges_and_included_tax(self):
        user = create_user()
        property = create_property()
        check_in, check_out = future_dates()
        reservation = ReservationService.create(
            user=user,
            property_id=property.pk,
            check_in=check_in,
            check_out=check_out,
            guests=2,
            charges=[{"kind": "late_check_in", "amount": Decimal("57")}],
        )
        Reservation.objects.filter(pk=reservation.pk).update(status=Reservation.Status.CONFIRMED)
        send_confirmation_email(reservation.pk)

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Late check-in", html)
        self.assertIn("Monto facturado", html)
        self.assertIn("IVA (21%)", html)
        self.assertIn("US$ 382", html)
        self.assertIn("157 Wynwood Points", html)


class ConfirmationViewTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.client.force_login(self.user)
        self.property = create_property()
        check_in, check_out = future_dates()
        self.reservation = ReservationService.create(
            user=self.user,
            property_id=self.property.pk,
            check_in=check_in,
            check_out=check_out,
            guests=2,
            discount=Decimal("22"),
        )
        Reservation.objects.filter(pk=self.reservation.pk).update(
            status=Reservation.Status.CONFIRMED, confirmed_at=timezone.now()
        )

    def test_renders_the_confirmation_summary(self):
        response = self.client.get(
            reverse("bookings:confirmation", kwargs={"public_id": self.reservation.public_id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.property.title)
        self.assertContains(response, "Descuento Wynwood Points")
        self.assertContains(response, "124 Wynwood Points")
        self.assertContains(response, "US$ 303")


class CheckoutFlowTests(TestCase):
    def setUp(self):
        self.property = create_property()
        self.check_in, self.check_out = future_dates()

    def test_checkout_prefills_authenticated_user_profile(self):
        user = User.objects.create_user(
            email="carlos@example.com",
            password="Strong-pass-2048",
            first_name="Carlos",
            last_name="Mendoza",
            country="CO",
            phone="+57 3001234567",
            birth_date=date(1990, 5, 20),
        )
        self.client.force_login(user)
        url = reverse("bookings:checkout", kwargs={"slug": self.property.slug})
        response = self.client.get(
            f"{url}?booking_type=daily&check_in={self.check_in}&check_out={self.check_out}&email=&phone=&discount_code=&guests=2"
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial.get("email"), "carlos@example.com")
        self.assertEqual(form.initial.get("full_name"), "Carlos Mendoza")
        self.assertEqual(form.initial.get("nationality"), "CO")
        self.assertEqual(form.initial.get("phone_code"), "+57")
        self.assertEqual(form.initial.get("phone"), "3001234567")
        self.assertEqual(form.initial.get("birth_date"), date(1990, 5, 20))
        self.assertContains(response, 'value="carlos@example.com"')
        self.assertContains(response, 'value="Carlos Mendoza"')
        self.assertContains(response, 'value="3001234567"')
        self.assertContains(response, 'value="1990-05-20"')

    def test_unauthenticated_checkout_creates_user_with_all_fields(self):
        url = reverse("bookings:checkout", kwargs={"slug": self.property.slug})
        payload = {
            "email": "laura@example.com",
            "password": "Password123!",
            "full_name": "Laura Gomez",
            "nationality": "PE",
            "phone_code": "+51",
            "phone": "987654321",
            "birth_date": "1995-10-12",
            "check_in": self.check_in.isoformat(),
            "check_out": self.check_out.isoformat(),
            "guests": 2,
            "booking_type": "daily",
        }
        response = self.client.post(url, data=payload)
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email="laura@example.com")
        self.assertEqual(user.first_name, "Laura")
        self.assertEqual(user.last_name, "Gomez")
        self.assertEqual(user.country, "PE")
        self.assertEqual(user.phone, "+51 987654321")
        self.assertEqual(user.birth_date, date(1995, 10, 12))
