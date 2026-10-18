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
