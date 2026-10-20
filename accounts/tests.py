from django.test import TestCase
from django.urls import reverse

from .models import User


class RegistrationTests(TestCase):
    def test_registers_and_authenticates_user(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Alex",
                "last_name": "Guest",
                "email": "Alex@Example.com",
                "password1": "A-strong-password-2048",
                "password2": "A-strong-password-2048",
            },
        )
        self.assertRedirects(response, reverse("core:home"))
        self.assertTrue(User.objects.filter(email="alex@example.com").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_rejects_duplicate_email(self):
        User.objects.create_user(email="alex@example.com", password="A-strong-password-2048")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Alex",
                "last_name": "Guest",
                "email": "alex@example.com",
                "password1": "A-strong-password-2048",
                "password2": "A-strong-password-2048",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["email"])

    def test_registration_returns_to_safe_checkout_url(self):
        target = "/properties/central-home/checkout/?check_in=2026-12-01&check_out=2026-12-04&guests=2"
        response = self.client.post(
            f"{reverse('accounts:register')}?next={target}",
            {
                "first_name": "Alex",
                "last_name": "Guest",
                "email": "new@example.com",
                "password1": "A-strong-password-2048",
                "password2": "A-strong-password-2048",
                "next": target,
            },
        )
        self.assertRedirects(response, target, fetch_redirect_response=False)

    def test_registration_rejects_external_redirect(self):
        response = self.client.post(
            f"{reverse('accounts:register')}?next=https://malicious.example/steal",
            {
                "first_name": "Alex",
                "last_name": "Guest",
                "email": "safe@example.com",
                "password1": "A-strong-password-2048",
                "password2": "A-strong-password-2048",
                "next": "https://malicious.example/steal",
            },
        )
        self.assertRedirects(response, reverse("core:home"))


class AccountRecoveryTests(TestCase):
    def test_password_reset_changes_the_password_and_invalidates_the_used_link(self):
        import re

        from django.core import mail

        user = User.objects.create_user(email="recover@example.com", password="Original!9081Value")
        response = self.client.post(reverse("accounts:password_reset"), {"email": user.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"https?://[^\s]+", mail.outbox[0].body).group(0)
        response = self.client.get(link, follow=True)
        self.assertTrue(response.context["validlink"])
        response = self.client.post(response.wsgi_request.path, {
            "new_password1": "BlueForest#7092", "new_password2": "BlueForest#7092",
        })
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("BlueForest#7092"))
        self.assertFalse(user.check_password("Original!9081Value"))
        self.assertFalse(self.client.get(link, follow=True).context["validlink"])

    def test_unknown_email_returns_the_same_reset_response_without_sending_mail(self):
        from django.core import mail

        response = self.client.post(reverse("accounts:password_reset"), {"email": "unknown@example.com"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_concurrent_duplicate_registration_is_shown_as_a_form_error(self):
        from unittest.mock import patch

        from django.db import IntegrityError

        with patch("accounts.forms.RegistrationForm.save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(reverse("accounts:register"), {
                "first_name": "Alex", "last_name": "Guest", "email": "race@example.com",
                "password1": "A-strong-password-2048", "password2": "A-strong-password-2048",
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertNotIn("_auth_user_id", self.client.session)
