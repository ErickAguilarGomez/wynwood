from django.urls import path

from .views import (
    CheckoutView,
    ConfirmationView,
    MonthlyInquiryView,
    MyBookingsView,
    ReservationServicesView,
    ServiceDetailView,
)

app_name = "bookings"

urlpatterns = [
    path("properties/<slug:slug>/monthly-inquiry/", MonthlyInquiryView.as_view(), name="monthly_inquiry"),
    path("properties/<slug:slug>/checkout/", CheckoutView.as_view(), name="checkout"),
    path("bookings/<uuid:public_id>/services/", ReservationServicesView.as_view(), name="services"),
    path(
        "bookings/<uuid:public_id>/services/<slug:service_key>/",
        ServiceDetailView.as_view(),
        name="service_detail",
    ),
    path("bookings/<uuid:public_id>/confirmation/", ConfirmationView.as_view(), name="confirmation"),
    path("my-bookings/", MyBookingsView.as_view(), name="list"),
]
