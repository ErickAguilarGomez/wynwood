from django.utils.dateparse import parse_date as django_parse_date


def parse_date(value):
    try:
        return django_parse_date(value)
    except (TypeError, ValueError):
        return None
