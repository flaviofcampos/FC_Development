"""
sheets_writer.py — publishes the ranked results to a Google Sheet via an
Apps Script Web App (see AppsScript_Code.gs), rather than a Google Cloud
service account. This sidesteps Google Workspace org policies that block
service account key creation entirely, since there's no Cloud IAM key
involved — the Apps Script runs under your own Google account via a
deployed Web App URL + a shared secret you make up yourself.
"""
import requests

OUTPUT_COLUMNS = [
    "priority_score", "address", "price", "suburb", "property_type",
    "bedrooms", "has_study", "car_spaces", "storeys",
    "nearest_station", "walk_distance_m", "train_time_to_family_hub_min",
    "transfers_required", "area_sqm", "land_value_multiplier",
    "area_subscore", "renovation_confidence", "renovation_subscore",
    "family_subscore", "needs_manual_check", "manual_check_reason",
    "listing_url", "scan_timestamp",
]


def write_ranked_results(webapp_url, shared_secret, ranked_df):
    """
    ranked_df: pandas DataFrame already filtered, scored, and sorted
               (highest priority_score first) — the output of main.py's
               pipeline.

    Posts the whole table as JSON to the Apps Script Web App, which
    overwrites the "Ranked Properties" tab each run.
    """
    available_cols = [c for c in OUTPUT_COLUMNS if c in ranked_df.columns]
    header_row = available_cols
    data_rows = ranked_df[available_cols].astype(str).values.tolist()
    all_rows = [header_row] + data_rows

    payload = {"secret": shared_secret, "rows": all_rows}

    resp = requests.post(webapp_url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    if "error" in result:
        raise RuntimeError(f"Apps Script write failed: {result['error']}")

    print(f"Wrote {result.get('rowsWritten', '?')} ranked properties via Apps Script.")
