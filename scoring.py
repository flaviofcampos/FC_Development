"""
scoring.py — pure functions: distance math + the weighted scoring model.
No network calls here, which is why we can fully unit-test this file
without any live API access.

TRAVEL TIME MODEL — important caveat:
The train travel times below are ESTIMATES derived from straight-line
distance, an assumed average suburban-rail speed, and a fixed transfer
penalty at Richmond (the confirmed real junction between the Frankston
and Glen Waverley lines). They are good enough to RANK properties against
each other, but are not pulled from a live timetable. When we wire up the
real GTFS static feed (Step 5 follow-up), replace estimate_train_time_min()
with an actual shortest-path lookup over GTFS stop_times/transfers — the
function signature below is designed to be a drop-in replacement point.
"""
import math
from datetime import date
from config import (
    ALL_STATIONS, TRANSFER_STATION, WEIGHTS,
    WALK_DECAY_METRES, TRAIN_TIME_DECAY_MIN, AREA_SCALE_SQM, LAND_VALUE_MULTIPLIER,
    PERMIT_RECENCY_DECAY_YEARS, BUILD_AGE_DECAY_YEARS,
    RENOVATION_POSITIVE_KEYWORDS, RENOVATION_NEGATIVE_KEYWORDS,
    HARD_FILTERS, AVG_TRAIN_SPEED_KMH,
    STATION_DWELL_MIN, TRANSFER_PENALTY_MIN,
)


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two lat/lon points."""
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearest_station(lat, lon):
    """Returns (station_name, walk_distance_m, line) for the closest station
    to a property — ANY station, not just Toorak/Heyington. This is the
    realistic "what do I actually walk to" answer."""
    distances = {
        name: haversine_m(lat, lon, s_lat, s_lon)
        for name, (s_lat, s_lon, _line) in ALL_STATIONS.items()
    }
    name = min(distances, key=distances.get)
    s_lat, s_lon, line = ALL_STATIONS[name]
    return name, distances[name], line


def _line_travel_time_min(dist_m):
    """Straight-line distance converted to an estimated in-vehicle minutes,
    plus a per-stop dwell buffer proportional to distance (rough proxy for
    number of intermediate stops on suburban rail, ~1 stop per 1.1km)."""
    km = dist_m / 1000
    in_vehicle_min = (km / AVG_TRAIN_SPEED_KMH) * 60
    est_stops = max(0, km / 1.1)
    dwell_min = est_stops * STATION_DWELL_MIN
    return in_vehicle_min + dwell_min


def estimate_train_time_min(station_name):
    """
    Estimated one-way travel time in minutes from `station_name` to the
    BETTER of Toorak or Heyington, respecting the "no more than one change"
    rule. Returns (minutes, transfers_used, destination_reached).

    Logic:
      - Same line as destination -> direct, 0 transfers.
      - Different line -> via Richmond (the real junction), 1 transfer.
      - Both destinations are checked; we return whichever is faster,
        since either satisfies the family's need (mirrors "at most one
        change is OK, not more").
    """
    s_lat, s_lon, s_line = ALL_STATIONS[station_name]
    r_lat, r_lon = TRANSFER_STATION["lat"], TRANSFER_STATION["lon"]

    destinations = {
        "Toorak": (-37.8510, 145.0140, "Frankston"),
        "Heyington": (-37.8346, 145.0227, "Glen Waverley"),
    }

    options = []
    for dest_name, (d_lat, d_lon, d_line) in destinations.items():
        if s_line == d_line:
            direct_dist = haversine_m(s_lat, s_lon, d_lat, d_lon)
            time_min = _line_travel_time_min(direct_dist)
            options.append((time_min, 0, dest_name))
        else:
            leg1 = haversine_m(s_lat, s_lon, r_lat, r_lon)
            leg2 = haversine_m(r_lat, r_lon, d_lat, d_lon)
            time_min = (
                _line_travel_time_min(leg1)
                + TRANSFER_PENALTY_MIN
                + _line_travel_time_min(leg2)
            )
            options.append((time_min, 1, dest_name))

    # pick the faster option; both respect the <=1 transfer rule by construction
    best = min(options, key=lambda x: x[0])
    return best  # (minutes, transfers, destination_name)


def decay_score(value, cutoff):
    """1.0 at value=0, exponential decay to ~0 by 3x cutoff. Used for
    distance/time factors where SMALLER is better."""
    if value <= 0:
        return 1.0
    score = math.exp(-value / cutoff)
    return max(0.0, min(1.0, score))


def growth_score(value, scale):
    """0.0 at value=0, rising to ~0.63 at value=scale, asymptotic to 1.0.
    Used for factors where BIGGER is better (here: property area). Same
    exponential family as decay_score, just inverted, so both factors are
    scored on a consistent curve shape."""
    if value <= 0:
        return 0.0
    score = 1 - math.exp(-value / scale)
    return max(0.0, min(1.0, score))


def area_score(prop):
    """
    Land size (house/townhouse/villa) or floor size (apartment), scored
    against a type-specific scale since the two aren't directly comparable
    — then adjusted by the land value multiplier, since land ownership
    tends to appreciate differently than strata title. Returns
    (adjusted_score, raw_score) so the raw "how generous for its type"
    figure stays visible even after the land-value discount is applied.
    """
    scale = AREA_SCALE_SQM.get(prop["property_type"])
    area_sqm = prop.get("area_sqm")
    if scale is None or area_sqm is None:
        return 0.5, 0.5  # neutral default if data is missing

    raw_score = growth_score(area_sqm, scale)
    multiplier = LAND_VALUE_MULTIPLIER.get(prop["property_type"], 1.0)
    adjusted_score = raw_score * multiplier
    return adjusted_score, raw_score


def _keyword_renovation_signal(description):
    """Weak fallback signal from free-text listing copy. Returns a score in
    [0.2, 0.8] — deliberately never as confident as a real data source,
    since this is just agent marketing language, not a verified fact."""
    if not description:
        return None
    text = description.lower()
    positive_hits = sum(1 for kw in RENOVATION_POSITIVE_KEYWORDS if kw in text)
    negative_hits = sum(1 for kw in RENOVATION_NEGATIVE_KEYWORDS if kw in text)
    if positive_hits == 0 and negative_hits == 0:
        return None  # no signal at all — let the caller fall through to "unknown"
    net = positive_hits - negative_hits
    # squash net hits into [0.2, 0.8], capped either direction at +/-2 hits
    net_clamped = max(-2, min(2, net))
    return 0.5 + net_clamped * 0.15


def renovation_score(prop, today=None):
    """
    Fallback chain, strongest signal first:
      1. Building permit record (years since issued) — most trustworthy
      2. Structured year_built field — moderately trustworthy
      3. Keyword scan of listing description — weak, noisy
      4. Neutral default — flagged as unknown

    Returns (score 0..1, confidence_tier string).
    """
    today = today or date.today()

    permit_years_ago = prop.get("building_permit_years_ago")
    if permit_years_ago is not None:
        return decay_score(permit_years_ago, PERMIT_RECENCY_DECAY_YEARS), "permit_record"

    year_built = prop.get("year_built")
    if year_built is not None:
        age_years = today.year - year_built
        return decay_score(max(0, age_years), BUILD_AGE_DECAY_YEARS), "year_built"

    keyword_score = _keyword_renovation_signal(prop.get("description"))
    if keyword_score is not None:
        return keyword_score, "keyword_signal"

    return 0.5, "unknown"


def passes_hard_filters(prop):
    """
    prop is a dict with the fields listed in ingestion.py's schema.

    Bedroom rule is property-type-specific:
      - apartment_ground_floor: needs 3BR, OR 2BR + study
      - house / townhouse / villa: needs 2BR or more (study irrelevant)
    """
    f = HARD_FILTERS

    if not (f["min_price"] <= prop["price"] <= f["max_price"]):
        return False, "price out of range"
    if prop["storeys"] > f["max_storeys"]:
        return False, "too many storeys"
    if prop["car_spaces"] < f["min_car_spaces"]:
        return False, "not enough parking"
    if prop["property_type"] not in f["allowed_property_types"]:
        return False, "wrong property type"

    if prop["property_type"] == "apartment_ground_floor":
        effective_bedrooms = prop["bedrooms"] + (1 if prop.get("has_study") else 0)
        if effective_bedrooms < f["min_bedrooms_apartment"]:
            return False, "apartment needs 3BR, or 2BR + study"
    else:  # house / townhouse / villa
        if prop["bedrooms"] < f["min_bedrooms_house_townhouse_villa"]:
            return False, "house/townhouse/villa needs 2BR or more"

    return True, None


def score_property(prop, suburb_family_scores):
    """
    prop: dict with lat, lon, suburb, price, bedrooms, storeys, car_spaces,
          property_type, has_study, area_sqm
    suburb_family_scores: dict of suburb -> 0..1 composite (SEIFA + crime),
          precomputed once per run in enrichment.py

    Three factors, in priority order: train access, property area, then
    suburb family-friendliness.
    """
    station_name, walk_dist_m, line = nearest_station(prop["lat"], prop["lon"])
    train_time_min, transfers, dest_reached = estimate_train_time_min(station_name)

    walk_score = decay_score(walk_dist_m, WALK_DECAY_METRES)
    train_time_score = decay_score(train_time_min, TRAIN_TIME_DECAY_MIN)
    train_access_score = 0.5 * walk_score + 0.5 * train_time_score

    area_sc, area_sc_raw = area_score(prop)
    reno_sc, reno_confidence = renovation_score(prop)
    family_score = suburb_family_scores.get(prop["suburb"], 0.5)  # neutral default

    weighted = (
        WEIGHTS["train_access"] * train_access_score
        + WEIGHTS["renovation_recency"] * reno_sc
        + WEIGHTS["property_area"] * area_sc
        + WEIGHTS["suburb_family_score"] * family_score
    )

    return {
        "priority_score": round(weighted, 4),
        "nearest_station": station_name,
        "nearest_station_line": line,
        "walk_distance_m": round(walk_dist_m),
        "train_time_to_family_hub_min": round(train_time_min, 1),
        "transfers_required": transfers,
        "hub_reached": dest_reached,
        "area_sqm": prop.get("area_sqm"),
        "land_value_multiplier": LAND_VALUE_MULTIPLIER.get(prop["property_type"], 1.0),
        "renovation_confidence": reno_confidence,
        "walk_subscore": round(walk_score, 3),
        "train_time_subscore": round(train_time_score, 3),
        "train_access_subscore": round(train_access_score, 3),
        "area_subscore_raw": round(area_sc_raw, 3),
        "area_subscore": round(area_sc, 3),
        "renovation_subscore": round(reno_sc, 3),
        "family_subscore": round(family_score, 3),
    }
