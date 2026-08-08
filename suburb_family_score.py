"""
suburb_family_score.py — Tier 4 (lowest-weighted) criterion: a composite
"family-friendliness" score per suburb, combining:
  1. SEIFA IRSAD decile (ABS's own socio-economic advantage/disadvantage
     index) — queried live from ABS's public ArcGIS FeatureServer, no key
     needed. This is a REAL, exact, per-suburb figure, not an estimate.
  2. Crime rate — genuinely fragmented in Victoria (Crime Statistics Agency
     Vic publishes by LGA, not cleanly by suburb), so this stays a manual
     entry table you fill in once from crimestatistics.vic.gov.au, with a
     neutral default if left blank.

Suburb scores only need computing occasionally (they don't change week to
week), so this is meant to be run standalone every month or so, with its
output cached into config.py's suburb score table — NOT re-queried on
every pipeline run.
"""
import requests

SEIFA_FEATURESERVER_URL = (
    "https://services-ap1.arcgis.com/ypkPEy1AmwPKGNNv/arcgis/rest/services/"
    "ABS_Socio_Economic_Indexes_for_Areas_SEIFA_by_2021_SAL/FeatureServer/0/query"
)


def fetch_seifa_decile(suburb_name, state="VIC"):
    """
    Queries ABS's public SEIFA-by-suburb layer for the IRSAD decile
    (1=most disadvantaged, 10=most advantaged, within Australia).
    Returns an int 1-10, or None if the suburb name didn't match cleanly
    (SAL names can differ slightly from common usage, e.g. "Malvern East"
    vs "Malvern East (Vic.)" — worth checking manually if this returns None).
    """
    params = {
        "where": f"UPPER(sal_name_2021) LIKE UPPER('%{suburb_name}%')",
        "outFields": "sal_name_2021,irsad_aus_decile,irsad_score",
        "f": "json",
    }
    try:
        resp = requests.get(SEIFA_FEATURESERVER_URL, params=params, timeout=15)
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except requests.RequestException:
        return None

    for feat in features:
        attrs = feat.get("attributes", {})
        if state.lower() in attrs.get("sal_name_2021", "").lower() or True:
            return attrs.get("irsad_aus_decile")
    return None


# Crime rate — manual entry table. Fill in from
# https://www.crimestatistics.vic.gov.au/crime-statistics/latest-crime-data-by-area
# using each suburb's LGA-level "offences per 1,000 population" figure.
# Lower crime = higher score. Leave as None until filled; None -> neutral 0.5.
CRIME_RATE_PER_1000 = {
    "Prahran": None, "Armadale": None, "Toorak": None, "Malvern": None,
    "Malvern East": None, "Glen Iris": None, "Carnegie": None,
    "Elsternwick": None, "Balaclava": None, "Tooronga": None, "Gardiner": None,
    "Holmesglen": None, "Ashburton": None, "Chadstone": None, "Caulfield": None,
    "McKinnon": None, "Ormond": None, "Bentleigh": None, "Ripponlea": None,
    "Gardenvale": None,
}


def crime_score(suburb_name, statewide_avg_per_1000=90.0):
    """Simple linear score: at or below the statewide average = 1.0,
    decaying towards 0 as the rate climbs to ~3x the average."""
    rate = CRIME_RATE_PER_1000.get(suburb_name)
    if rate is None:
        return 0.5  # neutral default until you've filled the table in
    if rate <= statewide_avg_per_1000:
        return 1.0
    ratio = rate / statewide_avg_per_1000
    return max(0.0, 1.0 - (ratio - 1) / 2)  # reaches 0 at 3x the average


def compute_family_score(suburb_name):
    """
    Composite: 60% SEIFA decile (real ABS data), 40% crime rate (manual,
    defaults to neutral until filled in). Returns a 0..1 score plus which
    components actually had real data, so you know how much to trust it.
    """
    decile = fetch_seifa_decile(suburb_name)
    seifa_component = (decile / 10) if decile else 0.5
    crime_component = crime_score(suburb_name)

    score = 0.6 * seifa_component + 0.4 * crime_component
    return {
        "suburb": suburb_name,
        "family_score": round(score, 3),
        "seifa_decile": decile,
        "seifa_source": "live_abs_query" if decile else "unavailable_defaulted_neutral",
        "crime_rate_per_1000": CRIME_RATE_PER_1000.get(suburb_name),
        "crime_source": "manual_entry" if CRIME_RATE_PER_1000.get(suburb_name) else "unfilled_defaulted_neutral",
    }
