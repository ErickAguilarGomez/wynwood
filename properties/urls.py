from django.urls import path

from .views import PropertyDetailView, PropertyListView, location_cities, location_districts

app_name = "properties"

urlpatterns = [
    path("api/locations/cities/", location_cities, name="location_cities"),
    path("api/locations/districts/", location_districts, name="location_districts"),
    path("search/", PropertyListView.as_view(), name="results"),
    path("properties/<slug:slug>/", PropertyDetailView.as_view(), name="detail"),
]
