"""
ingestion.py — pulls live listings from the Domain API and normalises them
into the internal property schema that scoring.py expects.

NOTE ON API ACCESS: this module calls https://api.domain.com.au and needs a
real Domain API token (see README.md for how to apply). It cannot be
exercised from this sandbox (no outbound network access here), so
normalize_listing() below is unit-tested against Domain's OWN documented
response shape (see test_ingestion.py) rather than a live call — that
proves the field-mapping logic is correct; the HTTP call itself just needs
a real token dropped in to start working.

KNOWN DATA GAPS (be aware of these when reading results):
  - Land/floor size (landAreaSqm/buildingAreaSqm) is frequently NULL for
    residential listings on Domain — mainly populated for commercial. We
    fall back to regex-scanning the description for a size mention, and
    flag area_source="unknown" when neither works (feeds the neutral 0.5
    default in scoring.py's area_score()).
  - Number of storeys and "is it genuinely ground-floor" for apartments are
    NOT reliably in the API at all — flagged as needs_manual_check=True so
    you know to glance at photos/floorplan before treating a match as final.
"""
import re
import requests

DOMAIN_SEARCH_URL = "https://api.domain.com.au/v1/listings/residential/_search"

PROPERTY_TYPE_MAP = {
    "house": "house",
    "townhouse": "townhouse",
    "villa": "villa",
    "apartmentunitflat": "apartment_ground_floor",  # see needs_manual_check note
    "unitblock": "apartment_ground_floor",
    "duplex": "townhouse",
}

# matches "350sqm", "350 sq m", "350m2", "350 m²", "approx 350sqm" etc.
AREA_REGEX = re.compile(r"(\d{2,4})\s*(?:sqm|sq\s?m|m2|m²)", re.IGNORECASE)


def fetch_domain_listings(api_token, suburb, state="VIC", min_price=750_000,
                           max_price=950_000, min_bedrooms=2):
    """
    Calls Domain's residential search endpoint for a single suburb.
    Returns the raw JSON list of listing objects (Domain's own shape,
    NOT yet normalised — pass each element to normalize_listing()).
    """
    headers = {"X-Api-Key": api_token, "Content-Type": "application/json"}
    payload = {
        "listingType": "Sale",
        "propertyTypes": ["house", "townhouse", "villa", "apartmentUnitFlat"],
        "minBedrooms": min_bedrooms,
        "minPrice": min_price,
        "maxPrice": max_price,
        "locations": [{"state": state, "suburb": suburb}],
        "pageSize": 50,
    }
    resp = requests.post(DOMAIN_SEARCH_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _extract_area_sqm(property_details, description):
    """Structured field first, then regex fallback on free text."""
    for key in ("landAreaSqm", "buildingAreaSqm"):
        val = property_details.get(key)
        if val:
            return float(val), "structured_field"

    if description:
        match = AREA_REGEX.search(description)
        if match:
            return float(match.group(1)), "description_regex"

    return None, "unknown"


def _extract_price(price_details):
    """
    Domain's priceDetails is inconsistent — sometimes a real number,
    sometimes "Contact Agent" or an auction date string. We take a
    numeric price when present, else None (which should exclude the
    listing from scoring until a human checks it — silently guessing
    a price would be worse than flagging it).
    """
    for key in ("price", "priceFrom"):
        val = price_details.get(key)
        if isinstance(val, (int, float)):
            return val
    return None


def normalize_listing(raw):
    """
    raw: one listing object from Domain's /v1/listings/residential/_search
         response (the "listing" sub-object, per Domain's documented shape).

    Returns a dict matching the schema scoring.py expects, or None if the
    listing is missing something we can't safely guess (e.g. no price).
    """
    details = raw.get("propertyDetails", {})
    price_details = raw.get("priceDetails", {})
    description = raw.get("description", "") or ""

    price = _extract_price(price_details)
    if price is None:
        return None  # can't score a listing with no usable price

    raw_type = (details.get("propertyType") or "").lower()
    property_type = PROPERTY_TYPE_MAP.get(raw_type)
    if property_type is None:
        return None  # not a residential type we handle (e.g. land, rural)

    features = [f.lower() for f in details.get("features", [])]
    has_study = "study" in features

    area_sqm, area_source = _extract_area_sqm(details, description)

    geo = raw.get("geoLocation", {})
    address_parts = raw.get("addressParts", {})

    return {
        "id": raw.get("id"),
        "address": address_parts.get("displayAddress"),
        "suburb": address_parts.get("suburb"),
        "price": price,
        "bedrooms": details.get("bedrooms"),
        "bathrooms": details.get("bathrooms"),
        "car_spaces": details.get("carspaces"),
        "has_study": has_study,
        "property_type": property_type,
        "area_sqm": area_sqm,
        "area_source": area_source,
        "description": description,
        "lat": geo.get("latitude"),
        "lon": geo.get("longitude"),
        "listing_url": raw.get("propertyDetailsUrl") or raw.get("canonicalUrl"),
        # storeys is NOT reliably available via API — default to 1 (the
        # common case) but always flag for a manual glance before you rule
        # a property in or out on this basis.
        "storeys": 1,
        "needs_manual_check": True,
        "manual_check_reason": "storeys + true ground-floor status unconfirmed by API",
    }
