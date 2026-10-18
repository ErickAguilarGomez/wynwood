from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_liveness(self):
        response = self.client.get(reverse("observability:live"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("X-Request-ID", response)
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])

    def test_readiness(self):
        response = self.client.get(reverse("observability:ready"))
        self.assertEqual(response.status_code, 200)
