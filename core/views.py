from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from properties.forms import PropertySearchForm
from properties.models import Country, Property


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.request.GET.get("category", "all")
        if category not in {"all", Property.Brand.COLLECTION, Property.Brand.CASA_WYNWOOD}:
            category = "all"
        initial = {"guests": 2}
        self.request.session.pop("search_guests", None)
        self.request.session.pop("search_check_in", None)
        self.request.session.pop("search_check_out", None)

        featured_properties = Property.objects.filter(is_active=True, is_featured=True)
        if category != "all":
            featured_properties = featured_properties.filter(brand=category)

        context.update(
            search_form=PropertySearchForm(initial=initial),
            featured_properties=featured_properties.select_related("destination").prefetch_related("images")[:4],
            featured_category=category,
            featured_countries=Country.objects.filter(is_active=True, show_on_home=True).exclude(home_image=""),
        )
        return context


def error_page(request, status, title):
    return render(request, "errors/error.html", {"status": status, "title": title}, status=status)


def bad_request(request, exception):
    return error_page(request, 400, _("We could not process that request"))


def permission_denied(request, exception):
    return error_page(request, 403, _("You do not have access to this page"))


def page_not_found(request, exception):
    return error_page(request, 404, _("The page you are looking for does not exist"))


def server_error(request):
    return error_page(request, 500, _("Something went wrong"))
