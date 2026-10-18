import uuid

from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        ERROR = "error", "Error"

    reservation = models.OneToOneField("bookings.Reservation", on_delete=models.PROTECT, related_name="payment")
    provider = models.CharField(max_length=30, default="wynwood_simulator")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    checkout_reference_id = models.CharField(max_length=160, unique=True, null=True, blank=True)
    transaction_id = models.CharField(max_length=160, unique=True, null=True, blank=True)
    status_detail = models.CharField(max_length=120, blank=True)
    provider_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=("status", "created_at"), name="payment_status_created_idx")]

    def __str__(self):
        return f"{self.provider} · {self.status}"
