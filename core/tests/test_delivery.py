from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict, modelform_factory
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from bookings.additional_services import get_services
from bookings.models import Reservation, ServiceCatalog
from bookings.services import PropertyUnavailable, ReservationService, ReservationValidationError
from bookings.tasks import send_confirmation_email
from core.tests.factories import create_property, create_user, future_dates
from payments.models import Payment
from payments.services import PaymentService
from payments.tests import payment_data
from properties.models import Airport, Country


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DeliveryFlowTests(TestCase):
    def setUp(self):
        self.property = create_property()
        self.user = create_user()
        self.check_in, self.check_out = future_dates(offset=90)
        Airport.objects.create(
            destination=self.property.destination, code="MAD", name_es="Aeropuerto de Madrid", name_en="Madrid Airport"
        )

    def create_reservation(self, **overrides):
        data = {
            "user": self.user,
            "property_id": self.property.pk,
            "check_in": self.check_in,
            "check_out": self.check_out,
            "guests": 2,
        }
        data.update(overrides)
        return ReservationService.create(**data)

    def checkout_data(self, **overrides):
        data = {
            "email": "new-guest@example.com",
            "password": "Sunset!9071Value",
            "full_name": "Taylor Visitor",
            "nationality": "PE",
            "phone_code": "+51",
            "phone": "987654321",
            "birth_date": "1995-06-15",
            "check_in": self.check_in.isoformat(),
            "check_out": self.check_out.isoformat(),
            "guests": "2",
            "booking_type": "daily",
        }
        data.update(overrides)
        return data

    def test_new_guest_can_configure_services_retry_payment_and_receive_one_confirmation(self):
        response = self.client.post(
            reverse("bookings:checkout", kwargs={"slug": self.property.slug}),
            self.checkout_data(selected_services=["flexible-checkin", "transport", "groceries", "baby-crib"]),
        )
        self.assertEqual(response.status_code, 302)
        reservation = Reservation.objects.get(user__email="new-guest@example.com")
        self.assertEqual(reservation.charges.count(), 4)
        services_url = reverse("bookings:services", kwargs={"public_id": reservation.public_id})
        self.assertIn("flexible-checkin", self.client.post(services_url).url)
        self.assertFalse(Payment.objects.filter(reservation=reservation).exists())
        configurations = {
            "flexible-checkin": {"service_date": self.check_in.isoformat(), "check_in_time": "09:00"},
            "transport": {
                "trip_type": "round_trip", "departure_date": self.check_in.isoformat(),
                "departure_time": "10:00", "departure_time_end": "11:00", "airport": "MAD",
                "return_date": self.check_out.isoformat(), "return_time": "12:00", "return_time_end": "13:00",
                "vehicle": "suv", "quantity": "2",
            },
            "groceries": {"pack": "breakfast", "delivery_date": self.check_in.isoformat()},
            "baby-crib": {"quantity": "2", "start_date": self.check_in.isoformat(), "end_date": self.check_out.isoformat()},
        }
        for key, data in configurations.items():
            with self.subTest(service=key):
                response = self.client.post(
                    reverse("bookings:service_detail", kwargs={"public_id": reservation.public_id, "service_key": key}), data
                )
                self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertTrue(all(charge.details["configured"] for charge in reservation.charges.all()))
        self.assertEqual(reservation.total, Decimal("511.00"))
        response = self.client.post(services_url)
        payment_url = reverse("payments:checkout", kwargs={"public_id": reservation.public_id})
        self.assertEqual(response.url, payment_url)
        with patch.object(PaymentService, "enqueue_confirmation") as enqueue:
            response = self.client.post(payment_url, payment_data("4000 0000 0000 0002"))
            reservation.refresh_from_db()
            self.assertEqual(reservation.status, Reservation.Status.PAYMENT_PENDING)
            enqueue.assert_not_called()
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(payment_url, payment_data("4242 4242 4242 4242"))
            enqueue.assert_called_once_with(reservation.pk)
        self.assertEqual(response.url, reservation.get_absolute_url())
        self.assertContains(self.client.get(response.url), "EXPERIENCIA DE HOGAR, CALIDAD DE HOTEL")
        send_confirmation_email(reservation.pk)
        send_confirmation_email(reservation.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new-guest@example.com"])
        self.assertIn("confirmada", mail.outbox[0].subject)
        self.assertIn("Total: 511,00", mail.outbox[0].body)
        reservation.refresh_from_db()
        self.assertIsNotNone(reservation.confirmation_sent_at)
        snapshot = str(Payment.objects.get(reservation=reservation).provider_snapshot)
        for sensitive in ("4242424242424242", "security_code", "10 Main Street", "postal_code"):
            self.assertNotIn(sensitive, snapshot)

    def test_anonymous_and_other_users_cannot_access_or_mutate_a_reservation(self):
        reservation = self.create_reservation()
        urls = [
            reverse("bookings:services", kwargs={"public_id": reservation.public_id}),
            reverse("bookings:service_detail", kwargs={"public_id": reservation.public_id, "service_key": "transport"}),
            reverse("payments:checkout", kwargs={"public_id": reservation.public_id}),
            reservation.get_absolute_url(),
        ]
        for url in urls:
            with self.subTest(url=url, actor="anonymous"):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response.url)
        self.client.force_login(create_user("other@example.com"))
        for url in urls:
            with self.subTest(url=url, actor="other"):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertIn(self.client.post(url, {"action": "remove"}).status_code, (404, 405))
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PAYMENT_PENDING)

    def test_existing_account_login_preserves_booking_and_profile_draft(self):
        data = self.checkout_data(email=self.user.email, selected_services=["baby-crib"])
        response = self.client.post(reverse("bookings:checkout", kwargs={"slug": self.property.slug}), data)
        query = parse_qs(urlparse(response.url).query)
        next_url = query["next"][0]
        response = self.client.post(reverse("accounts:login"), {
            "username": self.user.email, "password": "Strong-pass-2048", "next": next_url,
        })
        self.assertEqual(response.url, next_url)
        response = self.client.get(next_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["phone"], data["phone"])
        self.assertEqual(response.context["form"].initial["birth_date"], data["birth_date"])
        self.assertEqual(response.context["selected_service_keys"], ["baby-crib"])
        self.assertNotIn("password", self.client.session.get("checkout_draft", {}))

    def test_edit_does_not_release_another_hold_from_the_same_user(self):
        first = self.create_reservation()
        second = self.create_reservation(check_in=self.check_in + timedelta(days=10), check_out=self.check_out + timedelta(days=10))
        with self.assertRaises(PropertyUnavailable):
            ReservationService.update_stay(
                reservation=first, check_in=second.check_in, check_out=second.check_out, guests=2,
            )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.check_in, self.check_in)
        self.assertEqual(second.status, Reservation.Status.PAYMENT_PENDING)
        updated = ReservationService.update_stay(
            reservation=first, check_in=first.check_in, check_out=first.check_out, guests=3,
        )
        self.assertEqual(updated.guests, 3)

    def test_duplicate_submission_preserves_the_existing_hold(self):
        reservation = self.create_reservation()
        with self.assertRaises(PropertyUnavailable):
            self.create_reservation()
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PAYMENT_PENDING)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_editing_dates_invalidates_service_configuration_and_recalculates_the_total(self):
        reservation = self.create_reservation()
        ReservationService.add_service(reservation=reservation, kind="crib", amount=45, details={"configured": True})
        updated = ReservationService.update_stay(
            reservation=reservation, check_in=self.check_in + timedelta(days=1), check_out=self.check_out + timedelta(days=2),
            guests=2, selected_services=["baby-crib"],
        )
        self.assertFalse(updated.charges.get(kind="crib").details["configured"])
        self.assertEqual(updated.nights, 4)
        self.assertEqual(updated.total, Decimal("485.00"))

    def test_expired_payment_cannot_confirm_and_dates_become_available(self):
        reservation = self.create_reservation()
        PaymentService.start_checkout(reservation)
        Reservation.objects.filter(pk=reservation.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.client.force_login(self.user)
        with patch.object(PaymentService, "enqueue_confirmation") as enqueue:
            response = self.client.post(
                reverse("payments:checkout", kwargs={"public_id": reservation.public_id}),
                payment_data("4242 4242 4242 4242"),
            )
            self.assertEqual(response.status_code, 302)
            enqueue.assert_not_called()
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.EXPIRED)
        self.assertEqual(self.create_reservation().status, Reservation.Status.PAYMENT_PENDING)

    def test_prices_and_round_trip_configuration_come_from_the_active_catalog(self):
        ServiceCatalog.objects.filter(key="suv").update(is_active=False)
        ServiceCatalog.objects.filter(key="van").update(price="20.50", secondary_price="45.70")
        reservation = self.create_reservation()
        self.client.force_login(self.user)
        url = reverse("bookings:service_detail", kwargs={"public_id": reservation.public_id, "service_key": "transport"})
        response = self.client.get(url)
        self.assertEqual(response.context["quote"]["vehicle"], "van")
        self.assertContains(response, 'data-round-trip="45.70"')
        response = self.client.post(url, {
            "trip_type": "round_trip", "departure_date": self.check_in.isoformat(), "departure_time": "10:00",
            "departure_time_end": "11:00", "airport": "MAD", "return_date": self.check_out.isoformat(),
            "return_time": "12:00", "return_time_end": "13:00", "vehicle": "van", "quantity": "2",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(reservation.charges.get(kind="transport").amount, Decimal("91.40"))
        ServiceCatalog.objects.filter(key="flexible-checkin").update(price="38.75")
        response = self.client.get(reverse("bookings:checkout", kwargs={"slug": self.property.slug}), {
            "check_in": self.check_in, "check_out": self.check_out, "email": self.user.email, "phone": "987654321",
        })
        self.assertContains(response, 'data-service-price="38.75"')
        self.assertContains(response, "USD 38.75")
        response = self.client.get(reservation.get_absolute_url())
        self.assertEqual(response.status_code, 404)
        Reservation.objects.filter(pk=reservation.pk).update(status=Reservation.Status.CONFIRMED)
        self.client.cookies["django_language"] = "en"
        response = self.client.get(reservation.get_absolute_url())
        self.assertContains(response, "US$ 91.40")

    def test_empty_airport_catalog_does_not_crash_and_rejects_unavailable_airports(self):
        Airport.objects.all().delete()
        reservation = self.create_reservation()
        self.client.force_login(self.user)
        url = reverse("bookings:service_detail", kwargs={"public_id": reservation.public_id, "service_key": "transport"})
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"airport": "MAD"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("airport", response.context["form"].errors)

    def test_country_tax_changes_apply_to_new_reservations_and_preserve_existing_totals(self):
        first = self.create_reservation()
        Country.objects.filter(code="ES").update(tax_rate=Decimal("0.10"))
        second = self.create_reservation(check_in=self.check_out, check_out=self.check_out + timedelta(days=3))
        first.refresh_from_db()
        self.assertEqual(first.tax_rate, Decimal("0.21"))
        self.assertEqual(second.tax_rate, Decimal("0.10"))
        self.assertEqual(first.total, second.total)

    def test_negative_extra_charges_cannot_reduce_the_price(self):
        with self.assertRaises(ReservationValidationError):
            self.create_reservation(charges=[{"kind": "other", "amount": "-1"}])

    def test_payment_post_requires_csrf(self):
        reservation = self.create_reservation()
        PaymentService.start_checkout(reservation)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(reverse("payments:checkout", kwargs={"public_id": reservation.public_id}), payment_data("4242 4242 4242 4242"))
        self.assertEqual(response.status_code, 403)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PAYMENT_PENDING)

    def test_future_birth_dates_and_incomplete_registration_do_not_create_accounts(self):
        for data in ({}, self.checkout_data(birth_date=(timezone.localdate() + timedelta(days=1)).isoformat())):
            with self.subTest(data=bool(data)):
                response = self.client.post(reverse("bookings:checkout", kwargs={"slug": self.property.slug}), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertFalse(User.objects.filter(email="new-guest@example.com").exists())

    def test_monthly_inquiry_requires_only_contact_data_and_does_not_create_a_booking(self):
        response = self.client.post(reverse("bookings:monthly_inquiry", kwargs={"slug": self.property.slug}), {
            "full_name": "Taylor Visitor", "email": "monthly@example.com", "phone_code": "+51", "phone": "987654321",
        }, follow=True)
        self.assertContains(response, "Tu información fue enviada")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Reservation.objects.count(), 0)
        self.assertFalse(User.objects.filter(email="monthly@example.com").exists())

    def test_english_confirmation_uses_the_booking_language(self):
        reservation = self.create_reservation(language_code="en")
        Reservation.objects.filter(pk=reservation.pk).update(status=Reservation.Status.CONFIRMED)
        send_confirmation_email(reservation.pk)
        self.assertIn("is confirmed", mail.outbox[0].subject)
        self.assertIn("Central Home", mail.outbox[0].body)

    def test_manipulated_checkout_does_not_create_accounts_or_bookings(self):
        cases = [
            {"guests": "0"}, {"guests": "-1"}, {"guests": "5"},
            {"booking_type": "monthly", "check_out": (self.check_in + timedelta(days=35)).isoformat()},
            {"booking_type": "unsupported"}, {"check_out": "9999-12-31"},
            {"check_in": "9999-12-31", "check_out": "9999-12-31"},
        ]
        url = reverse("bookings:checkout", kwargs={"slug": self.property.slug})
        for values in cases:
            with self.subTest(values=values):
                response = self.client.post(url, self.checkout_data(**values))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertFalse(User.objects.filter(email="new-guest@example.com").exists())
                for errors in response.context["form"].errors.values():
                    for error in errors:
                        self.assertContains(response, str(error))
                self.assertEqual(Reservation.objects.count(), 0)

    def test_payment_revalidates_service_configuration_inside_the_transaction(self):
        reservation = self.create_reservation()
        PaymentService.start_checkout(reservation)
        ReservationService.add_service(reservation=reservation, kind="crib", amount=45, details={"configured": False})
        with patch.object(PaymentService, "enqueue_confirmation") as enqueue:
            with self.assertRaises(ReservationValidationError):
                PaymentService.process_simulated_payment(reservation, "approved")
            enqueue.assert_not_called()
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PAYMENT_PENDING)
        self.assertEqual(Payment.objects.get(reservation=reservation).status, Payment.Status.PENDING)

    def test_active_services_require_a_supported_configuration_and_matching_charge(self):
        service = ServiceCatalog.objects.get(key="flexible-checkin")
        form_class = modelform_factory(
            ServiceCatalog, fields=("category", "kind", "name_es", "name_en", "detail_key", "is_active")
        )
        data = model_to_dict(service)
        for changes, field in (
            ({"detail_key": ""}, "detail_key"),
            ({"detail_key": "unknown"}, "detail_key"),
            ({"kind": ""}, "kind"),
            ({"kind": "transport"}, "kind"),
        ):
            with self.subTest(changes=changes):
                form = form_class({**data, **changes}, instance=service)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        draft = form_class({**data, "detail_key": "", "is_active": False}, instance=service)
        self.assertTrue(draft.is_valid(), draft.errors)
        ServiceCatalog.objects.filter(key=service.key).update(detail_key="unknown")
        self.assertFalse(get_services().filter(key=service.key).exists())

    def test_unavailable_unconfigured_services_block_payment_and_can_be_removed(self):
        original = model_to_dict(ServiceCatalog.objects.get(key="transport"))
        original.pop("key")
        self.client.force_login(self.user)
        for index, state in enumerate(("inactive", "deleted", "invalid", "no_variants")):
            with self.subTest(state=state):
                ServiceCatalog.objects.update_or_create(key="transport", defaults=original)
                ServiceCatalog.objects.filter(category=ServiceCatalog.Category.VEHICLE).update(is_active=True)
                reservation = self.create_reservation(
                    check_in=self.check_in + timedelta(days=index * 10),
                    check_out=self.check_out + timedelta(days=index * 10),
                )
                base_total = reservation.total
                ReservationService.add_service(
                    reservation=reservation, kind="transport", amount=13, details={"configured": False}
                )
                service = ServiceCatalog.objects.filter(key="transport")
                if state == "deleted":
                    service.delete()
                elif state == "invalid":
                    service.update(detail_key="")
                elif state == "no_variants":
                    ServiceCatalog.objects.filter(category=ServiceCatalog.Category.VEHICLE).update(is_active=False)
                else:
                    service.update(is_active=False)
                PaymentService.start_checkout(reservation)
                payment_url = reverse("payments:checkout", kwargs={"public_id": reservation.public_id})
                services_url = reverse("bookings:services", kwargs={"public_id": reservation.public_id})
                with patch.object(PaymentService, "enqueue_confirmation") as enqueue:
                    with self.assertRaises(ReservationValidationError):
                        PaymentService.process_simulated_payment(reservation, "approved")
                    response = self.client.post(payment_url, payment_data("4242 4242 4242 4242"), follow=True)
                    self.assertEqual(response.redirect_chain, [(services_url, 302)])
                    self.assertContains(response, 'name="action" value="remove_service"')
                    reservation.refresh_from_db()
                    self.assertEqual(reservation.status, Reservation.Status.PAYMENT_PENDING)
                    self.assertEqual(Payment.objects.get(reservation=reservation).status, Payment.Status.PENDING)
                    enqueue.assert_not_called()
                    if state != "deleted":
                        response = self.client.get(reverse("bookings:service_detail", kwargs={
                            "public_id": reservation.public_id, "service_key": "transport",
                        }))
                        self.assertRedirects(response, services_url, fetch_redirect_response=False)
                    response = self.client.post(services_url, {"action": "remove_service", "kind": "transport"})
                    self.assertEqual(response.status_code, 302)
                    reservation.refresh_from_db()
                    self.assertFalse(reservation.charges.filter(kind="transport").exists())
                    self.assertEqual(reservation.total, base_total)
                    with self.captureOnCommitCallbacks(execute=True):
                        response = self.client.post(payment_url, payment_data("4242 4242 4242 4242"))
                    reservation.refresh_from_db()
                    self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)
                    enqueue.assert_called_once_with(reservation.pk)

    def test_a_configured_inactive_service_preserves_its_charge_when_paid(self):
        reservation = self.create_reservation()
        ReservationService.add_service(reservation=reservation, kind="crib", amount=45, details={
            "configured": True, "quantity": 1,
            "start_date": self.check_in.isoformat(), "end_date": self.check_out.isoformat(),
        })
        ServiceCatalog.objects.filter(key="baby-crib").update(is_active=False)
        PaymentService.start_checkout(reservation)
        self.client.force_login(self.user)
        with patch.object(PaymentService, "enqueue_confirmation") as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("payments:checkout", kwargs={"public_id": reservation.public_id}),
                    payment_data("4242 4242 4242 4242"),
                )
            enqueue.assert_called_once_with(reservation.pk)
        reservation.refresh_from_db()
        self.assertRedirects(response, reservation.get_absolute_url())
        self.assertEqual(reservation.status, Reservation.Status.CONFIRMED)
        self.assertEqual(reservation.charges.get(kind="crib").amount, Decimal("45.00"))
        self.assertEqual(reservation.total, Decimal("370.00"))
        self.assertEqual(Payment.objects.get(reservation=reservation).provider_snapshot["amount"], "370.00")

    def test_unrepresentable_prices_return_a_domain_error(self):
        self.property.price_per_night = Decimal("99999999.99")
        self.property.save(update_fields=("price_per_night",))
        with self.assertRaises(ReservationValidationError):
            self.create_reservation()
        self.assertEqual(Reservation.objects.count(), 0)

    def test_renamed_services_use_their_own_configuration_and_prices(self):
        configurations = {
            "flexible-checkin": ({"service_date": self.check_in.isoformat(), "check_in_time": "09:00"}, "38.75"),
            "transport": ({
                "trip_type": "one_way", "departure_date": self.check_in.isoformat(), "departure_time": "10:00",
                "departure_time_end": "11:00", "airport": "MAD", "vehicle": "suv", "quantity": "2",
            }, "26.00"),
            "groceries": ({"pack": "breakfast", "delivery_date": self.check_in.isoformat()}, "18.00"),
            "baby-crib": ({
                "quantity": "2", "start_date": self.check_in.isoformat(), "end_date": self.check_out.isoformat(),
            }, "112.50"),
        }
        ServiceCatalog.objects.filter(key="flexible-checkin").update(price="38.75")
        ServiceCatalog.objects.filter(key="baby-crib").update(price="18.75")
        reservation = self.create_reservation()
        self.client.force_login(self.user)
        for key, (data, expected) in configurations.items():
            with self.subTest(service=key):
                renamed = f"custom-{key}"
                ServiceCatalog.objects.filter(key=key).update(key=renamed)
                service = get_services().get(key=renamed)
                url = reverse("bookings:service_detail", kwargs={
                    "public_id": reservation.public_id, "service_key": renamed,
                })
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.post(url, data).status_code, 302)
                self.assertEqual(reservation.charges.get(kind=service.kind).amount, Decimal(expected))

    def test_active_catalog_entries_require_existing_images_and_unique_workflows(self):
        service = ServiceCatalog.objects.get(key="baby-crib")
        for image in ("", "design/nonexistent.webp"):
            with self.subTest(image=image):
                service.image = image
                with self.assertRaises(ValidationError) as error:
                    service.full_clean()
                self.assertIn("image", error.exception.message_dict)
        service.refresh_from_db()
        service.key = "another-crib"
        with self.assertRaises(ValidationError) as error:
            service.full_clean()
        self.assertIn("kind", error.exception.message_dict)
        country = Country.objects.get(code="ES")
        country.show_on_home = True
        country.home_image = "design/nonexistent.webp"
        with self.assertRaises(ValidationError) as error:
            country.full_clean()
        self.assertIn("home_image", error.exception.message_dict)

    def test_checkout_rejects_excessive_extras_without_a_partial_reservation(self):
        ServiceCatalog.objects.filter(key="baby-crib").update(price="99999999.99")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("bookings:checkout", kwargs={"slug": self.property.slug}),
            self.checkout_data(email=self.user.email, selected_services=["baby-crib", "baby-crib"]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertFalse(Reservation.objects.exists())

    def test_excessive_extra_amounts_roll_back_without_database_errors(self):
        reservation = self.create_reservation()
        with self.assertRaises(ReservationValidationError):
            ReservationService.add_service(reservation=reservation, kind="crib", amount="100000000")
        self.assertFalse(reservation.charges.exists())
        ServiceCatalog.objects.filter(key="baby-crib").update(price="99999999.99")
        with self.assertRaises(ReservationValidationError):
            ReservationService.update_stay(
                reservation=reservation, check_in=self.check_in, check_out=self.check_out, guests=2,
                selected_services=["baby-crib"],
            )
        reservation.refresh_from_db()
        self.assertEqual(reservation.total, Decimal("325.00"))
        self.assertFalse(reservation.charges.exists())

    def test_reservation_model_validation_checks_overlap_and_excludes_its_own_record(self):
        from copy import copy
        from uuid import uuid4

        reservation = self.create_reservation()
        reservation.full_clean()
        overlapping = copy(reservation)
        overlapping.pk = None
        overlapping.public_id = uuid4()
        with self.assertRaises(ValidationError):
            overlapping.full_clean()
