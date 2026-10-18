from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import TemplateView

from properties.forms import PropertySearchForm
from properties.models import Destination, Property


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        destinations = Destination.objects.all().order_by("country_code", "sort_order", "name_es")
        by_country = {}
        for d in destinations:
            by_country.setdefault(d.country, []).append(d)

        districts_map = {}
        for prop in Property.objects.filter(is_active=True).exclude(district=""):
            districts_map.setdefault(str(prop.destination_id), set()).add(prop.district)
            districts_map.setdefault(prop.destination.slug, set()).add(prop.district)

        initial = {"guests": self.request.session.get("search_guests", 2)}
        saved_in = self.request.session.get("search_check_in")
        saved_out = self.request.session.get("search_check_out")
        if saved_in and saved_out:
            parsed_in = parse_date(str(saved_in))
            parsed_out = parse_date(str(saved_out))
            if parsed_in and parsed_out and parsed_in >= timezone.localdate():
                initial["check_in"] = parsed_in
                initial["check_out"] = parsed_out

        context.update(
            search_form=PropertySearchForm(initial=initial),
            featured_properties=Property.objects.filter(is_active=True, is_featured=True).select_related("destination").prefetch_related("images")[:4],
            spain_properties=Property.objects.filter(is_active=True, destination__country_code="ES").select_related("destination").prefetch_related("images")[:6],
            destinations=destinations[:6],
            destinations_by_country=by_country,
            districts_by_destination={k: sorted(v) for k, v in districts_map.items()},
        )
        return context


def error_page(request, status, title):
    return render(request, "errors/error.html", {"status": status, "title": title}, status=status)


def bad_request(request, exception):
    return error_page(request, 400, "We could not process that request")


def permission_denied(request, exception):
    return error_page(request, 403, "You do not have access to this page")


def page_not_found(request, exception):
    return error_page(request, 404, "The page you are looking for does not exist")


def server_error(request):
    return error_page(request, 500, "Something went wrong")
