"""
test_mock_data.py — realistic MOCK listings (I made these up; not real
current listings) used only to prove the scoring/filtering logic behaves
sensibly before we ever touch a live API.
"""

MOCK_PROPERTIES = [
    {
        "id": "MOCK-1",
        "address": "12 Sample St, Armadale VIC 3143",
        "suburb": "Armadale",
        "price": 920_000,
        "bedrooms": 2,
        "bathrooms": 2,
        "car_spaces": 1,
        "storeys": 2,
        "property_type": "townhouse",
        "area_sqm": 210,   # decent townhouse land size, just under its 220 scale
        "building_permit_years_ago": 2,   # Tier 1: recent reno permit on file
        "lat": -37.8560, "lon": 145.0185,
        "notes": "2BR townhouse, great train access, recent permit = strong reno signal",
    },
    {
        "id": "MOCK-2",
        "address": "45 Example Ave, Glen Iris VIC 3146",
        "suburb": "Glen Iris",
        "price": 900_000,
        "bedrooms": 3,
        "bathrooms": 1,
        "car_spaces": 2,
        "storeys": 1,
        "property_type": "house",
        "area_sqm": 480,   # generously sized block, well over the 350 scale
        "year_built": 1948,   # Tier 2: no permit on file, but disclosed build year
        "lat": -37.8600, "lon": 145.0530,
        "notes": "3BR house on a big block, old build year with no known reno",
    },
    {
        "id": "MOCK-3",
        "address": "3/8 Demo Rd, Malvern East VIC 3145",
        "suburb": "Malvern East",
        "price": 875_000,
        "bedrooms": 2,
        "has_study": True,
        "bathrooms": 2,
        "car_spaces": 1,
        "storeys": 1,
        "property_type": "apartment_ground_floor",
        "area_sqm": 75,    # smallish apartment, below its 100 scale
        "description": "Fully renovated throughout with a brand new kitchen "
                        "and updated bathroom.",   # Tier 3: keyword signal only
        "lat": -37.8690, "lon": 145.0600,
        "notes": "2BR + study apartment, no permit/year data — relies on "
                 "keyword scan of the description",
    },
    {
        "id": "MOCK-4 (should FAIL filter)",
        "address": "9 Two Bedder Ct, Bentleigh VIC 3204",
        "suburb": "Bentleigh",
        "price": 900_000,
        "bedrooms": 2,
        "has_study": False,
        "bathrooms": 1,
        "car_spaces": 1,
        "storeys": 1,
        "property_type": "apartment_ground_floor",
        "area_sqm": 90,
        "lat": -37.9130, "lon": 145.0330,
        "notes": "2BR apartment, NO study — should FAIL, apartments need 3BR or 2BR+study",
    },
    {
        "id": "MOCK-5 (should FAIL filter)",
        "address": "1 Overbudget Manor, Toorak VIC 3142",
        "suburb": "Toorak",
        "price": 1_400_000,
        "bedrooms": 4,
        "bathrooms": 3,
        "car_spaces": 2,
        "storeys": 2,
        "property_type": "house",
        "area_sqm": 600,
        "lat": -37.8400, "lon": 145.0120,
        "notes": "over the $950k price cap — tests the tightened price filter",
    },
    {
        "id": "MOCK-6 (should FAIL filter)",
        "address": "9 Highrise Tower, Prahran VIC 3181",
        "suburb": "Prahran",
        "price": 900_000,
        "bedrooms": 3,
        "bathrooms": 2,
        "car_spaces": 1,
        "storeys": 3,
        "property_type": "townhouse",
        "area_sqm": 150,
        "lat": -37.8500, "lon": 144.9930,
        "notes": "tests the max_storeys filter",
    },
    {
        "id": "MOCK-7",
        "address": "22 Sandringham Line Test St, Elsternwick VIC 3185",
        "suburb": "Elsternwick",
        "price": 880_000,
        "bedrooms": 2,
        "bathrooms": 1,
        "car_spaces": 1,
        "storeys": 2,
        "property_type": "villa",
        "area_sqm": 260,   # comfortably over its 220 scale
        "description": "Original condition, in need of TLC, being sold as-is.",
        "lat": -37.8848, "lon": 145.0009,
        "notes": "1-transfer via Richmond, spacious villa, but negative "
                 "keyword signal (untouched/original)",
    },
]

# Mock suburb "family friendliness" composite (would come from SEIFA + crime
# data in the real enrichment step). Placeholder values 0..1, higher=better.
MOCK_SUBURB_FAMILY_SCORES = {
    "Armadale": 0.82,
    "Glen Iris": 0.88,
    "Malvern East": 0.85,
    "Bentleigh": 0.80,
    "Toorak": 0.90,
    "Prahran": 0.60,
    "Elsternwick": 0.83,
}
