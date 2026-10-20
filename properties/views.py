from decimal import Decimal

from django.db.models import Max, Min, Prefetch, Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.generic import DetailView, ListView

from bookings.forms import ReservationForm, country_phone_prefix, parse_phone
from bookings.models import Reservation
from core.dates import parse_date

from .forms import PropertySearchForm
from .models import Amenity, Country, Destination, Property, PropertyImage


class PropertyListView(ListView):
    model = Property
    template_name = "properties/results.html"
    context_object_name = "properties"
    paginate_by = 12

    def get_template_names(self):
        if self.request.GET.get("partial") == "1":
            return ["properties/_results_list.html"]
        return [self.template_name]

    def get_queryset(self):
        queryset = Property.objects.filter(is_active=True).select_related("destination").prefetch_related(
            Prefetch("images", queryset=PropertyImage.objects.order_by("sort_order")),
            "amenities",
        ).order_by("-is_featured", "title_es", "pk")
        query_params = self.request.GET.copy()
        raw_check_in = (query_params.get("check_in") or "").strip()
        raw_check_out = (query_params.get("check_out") or "").strip()

        if not raw_check_in and not raw_check_out and ("check_in" in query_params or "check_out" in query_params):
            self.request.session.pop("search_check_in", None)
            self.request.session.pop("search_check_out", None)
        elif not raw_check_in and not raw_check_out:
            saved_in = self.request.session.get("search_check_in")
            saved_out = self.request.session.get("search_check_out")
            parsed_in = parse_date(saved_in)
            parsed_out = parse_date(saved_out)
            if parsed_in and parsed_out and parsed_in >= timezone.localdate() and parsed_out > parsed_in:
                query_params["check_in"] = saved_in
                query_params["check_out"] = saved_out
            else:
                self.request.session.pop("search_check_in", None)
                self.request.session.pop("search_check_out", None)

        if not query_params.get("guests") and self.request.session.get("search_guests"):
            query_params["guests"] = str(self.request.session.get("search_guests"))

        self.query_params = query_params
        self.form = PropertySearchForm(query_params)
        if not self.form.is_valid():
            return queryset.none()
        data = self.form.cleaned_data

        if data.get("check_in") and data.get("check_out"):
            self.request.session["search_check_in"] = data["check_in"].isoformat()
            self.request.session["search_check_out"] = data["check_out"].isoformat()
        if data.get("guests"):
            self.request.session["search_guests"] = str(data["guests"])


        dest_val = data.get("destination")
        if dest_val:
            if str(dest_val).isdecimal():
                queryset = queryset.filter(destination_id=int(dest_val))
            else:
                queryset = queryset.filter(
                    Q(destination__slug__iexact=dest_val)
                    | Q(destination__name_es__icontains=dest_val)
                    | Q(destination__name_en__icontains=dest_val)
                    | Q(country__icontains=dest_val)
                    | Q(province__icontains=dest_val)
                    | Q(district__icontains=dest_val)
                )


        country = data.get("country")
        if country:
            country_codes = Country.objects.filter(
                Q(code__iexact=country) | Q(name_es__iexact=country) | Q(name_en__iexact=country)
            ).values("code")
            queryset = queryset.filter(
                Q(country__iexact=country) | Q(destination__country_code__in=country_codes)
            )


        province = data.get("province")
        if province:
            queryset = queryset.filter(province__icontains=province)


        districts = [d.strip() for d in self.request.GET.getlist("district") if d.strip()]
        if not districts and data.get("district"):
            districts = [data["district"].strip()]
        if len(districts) > 20 or any(len(district) > 120 for district in districts):
            return queryset.none()
        if districts:
            district_q = Q()
            for d in districts:
                district_q |= Q(district__iexact=d)
            queryset = queryset.filter(district_q)


        guests = data.get("guests")
        if guests:
            queryset = queryset.filter(max_guests__gte=guests)


        min_price = data.get("min_price")
        if min_price is not None:
            queryset = queryset.filter(price_per_night__gte=min_price)
        max_price = data.get("max_price")
        if max_price is not None:
            queryset = queryset.filter(price_per_night__lte=max_price)


        for amenity in data.get("amenities", ()):
            queryset = queryset.filter(amenities=amenity)


        check_in = data.get("check_in")
        check_out = data.get("check_out")
        if check_in and check_out:
            unavailable = Reservation.objects.filter(
                Q(status=Reservation.Status.CONFIRMED)
                | Q(status=Reservation.Status.PAYMENT_PENDING, expires_at__gt=timezone.now()),
                check_in__lt=check_out,
                check_out__gt=check_in,
            ).values("property_id")
            queryset = queryset.exclude(id__in=unavailable)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = self.form
        data = self.form.cleaned_data if self.form.is_valid() else {}
        context["search_data"] = data


        selected_dest = data.get("destination")
        if selected_dest:
            selected_dest = Destination.objects.filter(
                Q(pk=selected_dest) if str(selected_dest).isdecimal() else Q(slug__iexact=selected_dest)
                | Q(name_es__iexact=selected_dest)
                | Q(name_en__iexact=selected_dest)
            ).first()
        context["current_destination"] = selected_dest
        context["current_districts"] = [d for d in self.request.GET.getlist("district") if d] or ([data.get("district")] if data.get("district") else [])
        context["current_guests"] = data.get("guests") or self.request.GET.get("guests") or 1
        context["current_min_price"] = data.get("min_price") or self.request.GET.get("min_price")
        context["current_max_price"] = data.get("max_price") or self.request.GET.get("max_price")
        context["all_districts"] = sorted(
            Property.objects.filter(is_active=True).exclude(district="").values_list("district", flat=True).distinct()
        )
        context["all_amenities"] = Amenity.objects.all()
        price_bounds = Property.objects.filter(is_active=True).aggregate(
            minimum=Min("price_per_night"), maximum=Max("price_per_night")
        )
        context["price_floor"] = price_bounds["minimum"] or Decimal("0")
        context["price_ceiling"] = price_bounds["maximum"] or Decimal("0")


        query_params = getattr(self, "query_params", self.request.GET)
        context["requested_destination"] = query_params.get("destination", "")
        context["requested_country"] = query_params.get("country", "")
        context["requested_check_in"] = query_params.get("check_in", "")
        context["requested_check_out"] = query_params.get("check_out", "")
        context["selected_amenity_ids"] = query_params.getlist("amenities")

        query_suffix = ""
        c_in = data.get("check_in") or query_params.get("check_in")
        c_out = data.get("check_out") or query_params.get("check_out")
        if c_in and c_out:
            c_in_str = c_in.strftime("%Y-%m-%d") if hasattr(c_in, "strftime") else str(c_in)
            c_out_str = c_out.strftime("%Y-%m-%d") if hasattr(c_out, "strftime") else str(c_out)
            query_suffix = f"?check_in={c_in_str}&check_out={c_out_str}&guests={context['current_guests']}"

        properties_map_data = []
        for prop in context.get("properties", []):
            if prop.latitude is not None and prop.longitude is not None:
                img_url = ""
                photo = prop.primary_image
                if photo and photo.image:
                    img_url = photo.image.url
                properties_map_data.append(
                    {
                        "id": prop.pk,
                        "title": prop.title,
                        "price": float(prop.price_per_night),
                        "currency": context.get("booking_currency", "USD"),
                        "lat": float(prop.latitude),
                        "lng": float(prop.longitude),
                        "url": f"{prop.get_absolute_url()}{query_suffix}",
                        "image": img_url,
                        "district": prop.district or prop.destination.name,
                        "destination": prop.destination.name,
                    }
                )
        context["properties_map_data"] = properties_map_data
        return context


class PropertyDetailView(DetailView):
    model = Property
    template_name = "properties/detail.html"
    context_object_name = "property"

    def get_queryset(self):
        return Property.objects.filter(is_active=True).select_related("destination").prefetch_related("images", "amenities")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        check_in = self._requested_date("check_in")
        check_out = self._requested_date("check_out")
        guests = self.request.GET.get("guests") or self.request.session.get("search_guests", 2)
        initial = {"guests": guests}
        date_range_label = ""
        if check_in and check_out:
            initial["check_in"] = check_in
            initial["check_out"] = check_out
            date_range_label = (
                f"{date_format(check_in, 'd M Y')} - {date_format(check_out, 'd M Y')}"
            )
        context["reservation_form"] = ReservationForm(
            property=self.object,
            initial=initial,
        )
        context["date_range_label"] = date_range_label
        user = self.request.user
        dest_country = getattr(getattr(self.object, "destination", None), "country_code", None)
        phone_code, phone_number = parse_phone(
            getattr(user, "phone", "") if user.is_authenticated else "",
            country=getattr(user, "country", None) or dest_country,
            default_prefix=country_phone_prefix(dest_country, "+57"),
        )
        context["user_phone_code"] = phone_code
        context["user_phone_number"] = phone_number
        context["user_full_name"] = user.get_full_name().strip() if user.is_authenticated else ""
        context["detail_view"] = True
        return context

    def _requested_date(self, name):
        value = (self.request.GET.get(name) or "").strip() or self.request.session.get(f"search_{name}")
        if value:
            parsed = parse_date(str(value))
            if parsed:
                return parsed
        return None


def location_cities(request):

    country = (request.GET.get("country") or "").strip()
    cities = Destination.objects.filter(properties__is_active=True)
    if country:
        country_codes = Country.objects.filter(
            Q(code__iexact=country) | Q(name_es__iexact=country) | Q(name_en__iexact=country)
        ).values("code")
        cities = cities.filter(Q(properties__country__iexact=country) | Q(country_code__in=country_codes))
    cities = cities.distinct().order_by("name_es")
    return JsonResponse({"cities": [{"id": city.pk, "name": city.name, "slug": city.slug} for city in cities]})


def location_districts(request):

    destination_id = request.GET.get("destination")
    districts = Property.objects.filter(is_active=True).exclude(district="")
    if destination_id:
        if str(destination_id).isdecimal():
            districts = (
                districts.filter(destination_id=int(destination_id))
                if len(destination_id) <= 19 and int(destination_id) <= 9223372036854775807
                else districts.none()
            )
        else:
            districts = districts.filter(destination__slug=destination_id)
    names = districts.order_by("district").values_list("district", flat=True).distinct()
    return JsonResponse({"districts": [{"name": name} for name in names]})
