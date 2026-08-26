"""Facebook Marketplace — per-country location registry (companion to SKILL.md).

Each entry maps a country to its Marketplace currency and a list of cities.
City names are the **location slugs** Facebook uses in marketplace URLs
(https://www.facebook.com/marketplace/<slug>/search/?...). Convention:
lowercase, no spaces, umlauts transliterated, English exonyms (Köln →
"cologne", München → "munich", Wien → "vienna", Roma → "rome", ...).

Slug rule of thumb: whatever Facebook shows in the address bar once you pick
a location — "cologne" is verified working (2026, live URL). If a slug ever
stops resolving, drop it (location-less URLs fall back to the account's saved
location, so nothing breaks).

Marketplace shows prices in the listing's local currency; the `currency`
field is a convenience label for the report, not a filter parameter.
"""

COUNTRIES = {
    # --- DACH + Benelux ---
    "DE": {
        "name": "Germany",
        "currency": "EUR",
        "default_city": "cologne",
        "cities": [
            "cologne", "berlin", "hamburg", "munich", "frankfurt",
            "stuttgart", "duesseldorf", "leipzig", "dortmund", "essen",
            "bremen", "hannover",
        ],
    },
    "AT": {
        "name": "Austria",
        "currency": "EUR",
        "default_city": "vienna",
        "cities": ["vienna", "graz", "linz", "salzburg", "innsbruck"],
    },
    "CH": {
        "name": "Switzerland",
        "currency": "CHF",
        "default_city": "zurich",
        "cities": ["zurich", "geneva", "basel", "bern", "lausanne", "lugano"],
    },
    "NL": {
        "name": "Netherlands",
        "currency": "EUR",
        "default_city": "amsterdam",
        "cities": ["amsterdam", "rotterdam", "utrecht", "eindhoven", "groningen"],
    },
    "BE": {
        "name": "Belgium",
        "currency": "EUR",
        "default_city": "brussels",
        "cities": ["brussels", "antwerp", "ghent", "liege", "charleroi"],
    },
    # --- Western / Southern Europe ---
    "FR": {
        "name": "France",
        "currency": "EUR",
        "default_city": "paris",
        "cities": [
            "paris", "lyon", "marseille", "toulouse", "nice", "nantes",
            "strasbourg", "bordeaux", "lille", "montpellier",
        ],
    },
    "IT": {
        "name": "Italy",
        "currency": "EUR",
        "default_city": "rome",
        "cities": [
            "rome", "milan", "turin", "naples", "bologna", "florence",
            "genoa", "verona", "venice",
        ],
    },
    "ES": {
        "name": "Spain",
        "currency": "EUR",
        "default_city": "madrid",
        "cities": [
            "madrid", "barcelona", "valencia", "seville", "bilbao",
            "zaragoza", "malaga", "palma",
        ],
    },
    "PT": {
        "name": "Portugal",
        "currency": "EUR",
        "default_city": "lisbon",
        "cities": ["lisbon", "porto", "braga", "coimbra", "faro"],
    },
    # --- UK / Ireland ---
    "GB": {
        "name": "United Kingdom",
        "currency": "GBP",
        "default_city": "london",
        "cities": [
            "london", "manchester", "birmingham", "liverpool", "leeds",
            "bristol", "glasgow", "edinburgh", "newcastle", "sheffield",
            "nottingham",
        ],
    },
    "IE": {
        "name": "Ireland",
        "currency": "EUR",
        "default_city": "dublin",
        "cities": ["dublin", "cork", "galway", "limerick"],
    },
    # --- Nordics ---
    "DK": {
        "name": "Denmark",
        "currency": "DKK",
        "default_city": "copenhagen",
        "cities": ["copenhagen", "aarhus", "odense", "aalborg"],
    },
    "SE": {
        "name": "Sweden",
        "currency": "SEK",
        "default_city": "stockholm",
        "cities": ["stockholm", "gothenburg", "malmo", "uppsala"],
    },
    "NO": {
        "name": "Norway",
        "currency": "NOK",
        "default_city": "oslo",
        "cities": ["oslo", "bergen", "trondheim", "stavanger"],
    },
    "FI": {
        "name": "Finland",
        "currency": "EUR",
        "default_city": "helsinki",
        "cities": ["helsinki", "tampere", "turku", "oulu"],
    },
    # --- Central / Eastern Europe ---
    "PL": {
        "name": "Poland",
        "currency": "PLN",
        "default_city": "warsaw",
        "cities": ["warsaw", "krakow", "wroclaw", "poznan", "gdansk", "lodz"],
    },
    "CZ": {
        "name": "Czechia",
        "currency": "CZK",
        "default_city": "prague",
        "cities": ["prague", "brno", "ostrava", "plzen"],
    },
    # --- North America (slugs may vary; verify once — see module docstring) ---
    "US": {
        "name": "United States",
        "currency": "USD",
        "default_city": "newyork",
        "cities": [
            "newyork", "losangeles", "chicago", "sanfrancisco", "seattle",
            "boston", "austin", "miami",
        ],
    },
    "CA": {
        "name": "Canada",
        "currency": "CAD",
        "default_city": "toronto",
        "cities": ["toronto", "vancouver", "montreal", "calgary", "ottawa"],
    },
}

# Order used for --list and multi-country scans (EU-first, mirrors the
# hardware-flipping focus of the repo).
ORDER = [
    "DE", "AT", "CH", "NL", "BE",
    "FR", "IT", "ES", "PT",
    "GB", "IE",
    "DK", "SE", "NO", "FI",
    "PL", "CZ",
    "US", "CA",
]


def country(code):
    """Return the registry entry for a country code (None if unknown)."""
    return COUNTRIES.get(code.upper())


def cities_for(country_code):
    """Cities list for a country code ([] if unknown)."""
    entry = country(country_code)
    return entry["cities"] if entry else []


def default_city(country_code):
    """Default city slug for a country code (None if unknown)."""
    entry = country(country_code)
    return entry["default_city"] if entry else None


def currency_for(country_code):
    """Marketplace display currency for a country code ('' if unknown)."""
    entry = country(country_code)
    return entry["currency"] if entry else ""


def name_for(country_code):
    """Human-readable country name ('' if unknown)."""
    entry = country(country_code)
    return entry["name"] if entry else ""
