from django.urls import path

from .views import live, ready

app_name = "observability"

urlpatterns = [path("live/", live, name="live"), path("ready/", ready, name="ready")]
