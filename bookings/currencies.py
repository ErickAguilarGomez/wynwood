

CURRENCY_SYMBOLS = {
    "PEN": "S/",
    "USD": "US$",
    "MXN": "MX$",
    "COP": "COL$",
    "ARS": "AR$",
    "CLP": "CLP$",
    "EUR": "€",
}


def currency_symbol(currency):

    return CURRENCY_SYMBOLS.get(currency, currency)
