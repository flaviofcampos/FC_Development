"""
permits.py — Tier-1 renovation signal: checks a Victorian council's
building permit register (via CKAN, the platform data.vic.gov.au and most
council open-data portals run on) for a permit issued at a given address.

HONEST LIMITATION: there is no single statewide building-permits dataset
with clean geocoded addresses. Coverage is per-council (Stonnington, Glen
Eira, Boroondara, Port Phillip each publish separately, if at all), and
address matching against free-text permit records is inherently fuzzy.
Treat a MISS here as "no data available", not "no permit exists" — this
is exactly why permits.py is Tier 1 of a fallback chain, not the only
signal. Expect this tier to fire for a minority of properties.
"""
import re
import requests

CKAN_DATASTORE_SEARCH = "{base_url}/api/3/action/datastore_search"


def _normalize_address(address):
    """Lowercase, strip unit/suburb/state/postcode noise for fuzzy matching
    against permit register address strings, which are rarely formatted
    identically to Domain's displayAddress."""
    addr = address.lower()
    addr = re.sub(r"vic\s*\d{4}$", "", addr)          # trailing "VIC 3143"
    addr = re.sub(r"[^a-z0-9\s]", "", addr)            # punctuation
    addr = re.sub(r"\s+", " ", addr).strip()
    return addr


def query_permits(base_url, resource_id, address, api_key=None, years_lookback=15):
    """
    base_url: the council's open-data CKAN root, e.g.
              "https://data.melbourne.vic.gov.au" (adjust per council)
    resource_id: the specific building-permits resource ID for that portal
                 (find via the dataset's "API" tab on the portal)
    address: the listing's display address to match against

    Returns years_since_permit (float) if a plausible match is found within
    years_lookback, else None (meaning: fall through to Tier 2).
    """
    normalized_target = _normalize_address(address)
    street_number_and_name = " ".join(normalized_target.split()[:3])  # rough key

    params = {"resource_id": resource_id, "q": street_number_and_name, "limit": 20}
    headers = {"Authorization": api_key} if api_key else {}

    try:
        resp = requests.get(
            CKAN_DATASTORE_SEARCH.format(base_url=base_url),
            params=params, headers=headers, timeout=15,
        )
        resp.raise_for_status()
        records = resp.json().get("result", {}).get("records", [])
    except requests.RequestException:
        return None  # network/API issue — fall through gracefully, don't crash the run

    best_years_ago = None
    from datetime import date
    for rec in records:
        rec_address = rec.get("address") or rec.get("property_address") or ""
        if _normalize_address(rec_address) != normalized_target:
            continue  # not a confident match — skip rather than guess
        permit_date_str = rec.get("permit_date") or rec.get("issue_date") or rec.get("date")
        if not permit_date_str:
            continue
        try:
            permit_year = int(str(permit_date_str)[:4])
        except ValueError:
            continue
        years_ago = date.today().year - permit_year
        if years_ago <= years_lookback:
            if best_years_ago is None or years_ago < best_years_ago:
                best_years_ago = years_ago

    return best_years_ago


# Council open-data portals covering your target suburbs — fill in real
# resource_ids once you've located each on data.vic.gov.au / the council's
# own portal (search "<council name> building permits open data").
COUNCIL_PORTALS = {
    "Stonnington": {"base_url": "https://data.vic.gov.au", "resource_id": None},
    "Glen Eira":   {"base_url": "https://data.vic.gov.au", "resource_id": None},
    "Boroondara":  {"base_url": "https://data.vic.gov.au", "resource_id": None},
    "Port Phillip": {"base_url": "https://data.vic.gov.au", "resource_id": None},
}
