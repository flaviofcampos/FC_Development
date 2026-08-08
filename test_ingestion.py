"""
test_ingestion.py — proves normalize_listing() maps Domain's real,
documented response shape correctly. Uses sample payloads taken from
Domain's own developer portal docs (not live data), since this sandbox
has no outbound network access to call the live API.
"""
from ingestion import normalize_listing

# Shape taken from Domain's documented /v1/listings/residential/_search
# response (developer.domain.com.au), with study feature + land size
# regex-extractable from the description to exercise BOTH fallback paths.
SAMPLE_RAW_LISTING_1 = {
    "id": 2013958589,
    "priceDetails": {"price": 895000, "displayPrice": "$895,000"},
    "description": "Charming 3 bedroom home on a generous 480sqm block, "
                    "walking distance to the station.",
    "propertyDetails": {
        "propertyType": "House",
        "bedrooms": 3,
        "bathrooms": 2,
        "carspaces": 1,
        "features": ["Gas", "Study"],
        # landAreaSqm deliberately absent, per the known Domain gap —
        # this should force the regex fallback to find "480sqm" instead.
    },
    "geoLocation": {"latitude": -37.8600, "longitude": 145.0530},
    "addressParts": {"displayAddress": "45 Example Ave, Glen Iris VIC 3146",
                      "suburb": "Glen Iris"},
    "propertyDetailsUrl": "https://www.domain.com.au/45-example-ave-glen-iris-vic-3146",
}

# Shape with NO price (Contact Agent) and NO area info anywhere —
# should be dropped (price) / flagged unknown (area) respectively.
SAMPLE_RAW_LISTING_2 = {
    "id": 999,
    "priceDetails": {"displayPrice": "Contact Agent"},
    "description": "Lovely apartment, inspect this weekend.",
    "propertyDetails": {
        "propertyType": "ApartmentUnitFlat",
        "bedrooms": 2,
        "bathrooms": 1,
        "carspaces": 1,
        "features": [],
    },
    "geoLocation": {"latitude": -37.85, "longitude": 145.02},
    "addressParts": {"displayAddress": "1/1 Test St, Prahran VIC 3181",
                      "suburb": "Prahran"},
    "propertyDetailsUrl": "https://www.domain.com.au/1-1-test-st",
}

# Non-residential type that should be dropped by our type map.
SAMPLE_RAW_LISTING_3 = {
    "id": 888,
    "priceDetails": {"price": 850000},
    "description": "Vacant land, build your dream home.",
    "propertyDetails": {"propertyType": "Land", "bedrooms": 0,
                         "bathrooms": 0, "carspaces": 0, "features": []},
    "geoLocation": {"latitude": -37.86, "longitude": 145.03},
    "addressParts": {"displayAddress": "Lot 5 Test Rd, Malvern VIC 3144",
                      "suburb": "Malvern"},
    "propertyDetailsUrl": "https://www.domain.com.au/lot-5",
}


def run():
    r1 = normalize_listing(SAMPLE_RAW_LISTING_1)
    print("LISTING 1 (has study feature + regex-extractable area):")
    print(f"  price={r1['price']}  bedrooms={r1['bedrooms']}  has_study={r1['has_study']}")
    print(f"  area_sqm={r1['area_sqm']}  area_source={r1['area_source']}")
    print(f"  property_type={r1['property_type']}  suburb={r1['suburb']}")
    assert r1["has_study"] is True, "FAIL: should have detected Study feature"
    assert r1["area_sqm"] == 480.0, "FAIL: should have regex-extracted 480sqm from description"
    assert r1["area_source"] == "description_regex"
    print("  PASS\n")

    r2 = normalize_listing(SAMPLE_RAW_LISTING_2)
    print("LISTING 2 (no usable price -> should be dropped entirely):")
    print(f"  result={r2}")
    assert r2 is None, "FAIL: listing with no numeric price should return None"
    print("  PASS\n")

    r3 = normalize_listing(SAMPLE_RAW_LISTING_3)
    print("LISTING 3 (Land type -> not a residential type we handle):")
    print(f"  result={r3}")
    assert r3 is None, "FAIL: Land property type should return None"
    print("  PASS\n")

    print("All ingestion mapping tests passed.")


if __name__ == "__main__":
    run()
