from django.urls import path

from .views import PaymentCheckoutView

app_name = "payments"

urlpatterns = [
    path("bookings/<uuid:public_id>/payment/", PaymentCheckoutView.as_view(), name="checkout"),
]
