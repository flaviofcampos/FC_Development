"""
config.py — all the tunable inputs for the Melbourne property scanner.
Edit this file to change suburbs, priorities, or weights. Nothing else
in the pipeline should need editing for day-to-day tuning.
"""

# ---------------------------------------------------------------------------
# HARD FILTERS — a property failing ANY of these is dropped before scoring
# ---------------------------------------------------------------------------
# Bedroom rule is now property-type-specific:
#   - apartment: 3BR, OR 2BR + study
#   - house / townhouse / villa: 2BR or more (no study requirement)
HARD_FILTERS = {
    "min_price": 750_000,
    "max_price": 950_000,
    "max_storeys": 2,
    "min_car_spaces": 1,
    "allowed_property_types": ["house", "townhouse", "villa", "apartment_ground_floor"],
    "min_bedrooms_apartment": 3,       # or 2 + study, handled in scoring.py
    "min_bedrooms_house_townhouse_villa": 2,
}

# ---------------------------------------------------------------------------
# GEOGRAPHIC SCOPE — the widened south-east corridor
# ---------------------------------------------------------------------------
TARGET_SUBURBS = [
    "Prahran", "Armadale", "Toorak", "Malvern", "Malvern East", "Glen Iris",
    "Carnegie", "Elsternwick", "Balaclava",
    # widened corridor, same rail lines, more likely to hit budget:
    "Tooronga", "Gardiner", "Holmesglen", "Ashburton", "Chadstone",
    "Caulfield", "McKinnon", "Ormond", "Bentleigh", "Ripponlea", "Gardenvale",
]

# ---------------------------------------------------------------------------
# PRIORITY LOCATIONS — real coordinates (WGS84 lat/lon)
# ---------------------------------------------------------------------------
PRIORITY_STATIONS = {
    # name: (lat, lon, line)
    "Toorak":     (-37.8510, 145.0140, "Frankston"),
    "Heyington":  (-37.8346, 145.0227, "Glen Waverley"),
}

# The one real junction connecting the Frankston line and Glen Waverley line
# without going a long way round — confirmed via PTV network data.
TRANSFER_STATION = {"name": "Richmond", "lat": -37.8236, "lon": 144.9889}

# Other stations on the SAME two lines — used so nearby corridor suburbs
# still score well even if not literally Toorak/Heyington. Each is tagged
# with its line, since that determines whether reaching Toorak/Heyington
# needs a change at Richmond or not.
CORRIDOR_STATIONS = {
    # name: (lat, lon, line)
    "Armadale":    (-37.8567, 145.0177, "Frankston"),
    "Malvern":     (-37.8598, 145.0292, "Frankston"),
    "Caulfield":   (-37.8774, 145.0432, "Frankston"),
    "Tooronga":    (-37.8494, 145.0417, "Glen Waverley"),
    "Gardiner":    (-37.8533, 145.0516, "Glen Waverley"),
    "Holmesglen":  (-37.8742, 145.0914, "Glen Waverley"),
    # Sandringham line — serves Prahran/Balaclava/Elsternwick corridor.
    # A DIFFERENT line again, so these genuinely exercise the 1-transfer
    # rule via Richmond (confirmed junction for Frankston/Glen Waverley/
    # Sandringham lines).
    "Balaclava":    (-37.8695, 144.9934, "Sandringham"),
    "Ripponlea":    (-37.8759, 144.9951, "Sandringham"),
    "Elsternwick":  (-37.8848, 145.0009, "Sandringham"),
}

# All stations a property could realistically walk to — priority + corridor
# combined, each tagged with its line for the transfer-aware time model.
ALL_STATIONS = {
    "Toorak": (-37.8510, 145.0140, "Frankston"),
    "Heyington": (-37.8346, 145.0227, "Glen Waverley"),
    **CORRIDOR_STATIONS,
}

# ---------------------------------------------------------------------------
# TRAVEL TIME MODEL — estimated, not live-timetabled (see note in scoring.py)
# ---------------------------------------------------------------------------
AVG_TRAIN_SPEED_KMH = 32   # realistic average incl. stops, inner Melbourne suburban rail
STATION_DWELL_MIN = 1.5    # average time lost per intermediate stop (rounding buffer)
TRANSFER_PENALTY_MIN = 7   # walk between platforms + average wait at Richmond
MAX_TRANSFERS = 1          # hard rule: no more than one change of trains

# NOTE: school-proximity criteria removed — it's superseded by the train
# access criteria, since St Catherine's Toorak and Armadale Primary both
# sit right by the Toorak/Armadale station cluster anyway.

# NOTE: parks/aquatic/sports amenity criteria removed per your steer.

# ---------------------------------------------------------------------------
# SCORING WEIGHTS — must sum to 1.0. Four factors now, in priority order:
#   1. train_access          (walk + network time to Toorak/Heyington)
#   2. renovation_recency     (age/renovation proxy — see note below)
#   3. property_area          (land size for house/townhouse/villa,
#                              floor size for apartments)
#   4. suburb_family_score    (SEIFA + crime composite)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "train_access": 0.45,
    "renovation_recency": 0.25,
    "property_area": 0.20,
    "suburb_family_score": 0.10,
}

# Decay/cutoff parameters
WALK_DECAY_METRES = 1200        # ~15 min walk to the nearest station
TRAIN_TIME_DECAY_MIN = 20       # effective cutoff for network travel time, in minutes

# AREA scoring — "scale" is the size (sqm) at which a property is considered
# comfortably generous for its type (score asymptotically approaches 1.0
# well beyond this, ~63% AT this value). Land size for house/townhouse/villa,
# internal floor size for ground-floor apartments (these aren't directly
# comparable, hence separate scales per type).
AREA_SCALE_SQM = {
    "house": 350,
    "townhouse": 220,
    "villa": 220,
    "apartment_ground_floor": 100,
}

# LAND VALUE MULTIPLIER — applied on top of the area score, reflecting that
# land ownership tends to appreciate differently than strata title, even at
# an equivalent "size relative to its type" score. A house sits on its own
# full land parcel (no discount); townhouse/villa still own a land
# component but typically a smaller, subdivided one (slight discount);
# ground-floor apartments are strata title with no direct land ownership
# (the biggest discount). This means an apartment's area score can never
# reach the ceiling a house's can, even if it's very generously sized for
# an apartment — which is the deliberate point.
LAND_VALUE_MULTIPLIER = {
    "house": 1.00,
    "townhouse": 0.92,
    "villa": 0.92,
    "apartment_ground_floor": 0.70,
}

# ---------------------------------------------------------------------------
# RENOVATION / AGE scoring — no single reliable free bulk source exists, so
# this uses a FALLBACK CHAIN, strongest signal first. Each property ends up
# tagged with which tier actually fired, so you can see how much to trust it.
#
#   Tier 1: data.vic.gov.au Building Permit record found for the address
#           -> years since permit issued, decay-scored (most trustworthy)
#   Tier 2: structured "year built" field disclosed in the listing
#           -> building age, decay-scored (moderately trustworthy)
#   Tier 3: keyword scan of the listing title/description
#           -> weak positive/negative signal (agent marketing copy, noisy)
#   Tier 4: nothing available -> neutral default, flagged "unknown"
# ---------------------------------------------------------------------------
PERMIT_RECENCY_DECAY_YEARS = 8     # a permit >~20yrs old barely counts as "recent"
BUILD_AGE_DECAY_YEARS = 30         # a newly-built home scores highest; decays from there

RENOVATION_POSITIVE_KEYWORDS = [
    "renovated", "renovation", "updated", "refurbished", "restored",
    "architecturally redesigned", "architect designed", "brand new",
    "near new", "as new", "newly built", "fully renovated", "modernised",
    "modernized", "new kitchen", "new bathroom",
]
RENOVATION_NEGATIVE_KEYWORDS = [
    "original condition", "untouched", "needs renovation", "needs updating",
    "deceased estate", "as-is", "renovator's delight", "original features",
    "circa 19", "circa 18", "dated", "requires updating", "in need of tlc",
    "tlc",
]
