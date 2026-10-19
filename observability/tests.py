import json
from unittest.mock import patch

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

    def test_request_logs_do_not_include_password_reset_tokens(self):
        with patch("observability.middleware.logger.info") as log_request:
            response = self.client.get("/accounts/password-reset/dXNlcg/sensitive-token/")

        self.assertEqual(response.status_code, 200)
        details = json.dumps(log_request.call_args.kwargs["extra"])
        self.assertNotIn("sensitive-token", details)
        self.assertEqual(log_request.call_args.kwargs["extra"]["route"], "accounts/password-reset/<uidb64>/<token>/")
