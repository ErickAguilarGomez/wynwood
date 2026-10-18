from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reservation", "provider", "status", "transaction_id", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("reservation__public_id", "transaction_id")
    readonly_fields = ("provider_snapshot", "created_at", "updated_at")
