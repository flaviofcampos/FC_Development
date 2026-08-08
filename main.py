"""
main.py — orchestrates the full pipeline:
  ingest (Domain API, per target suburb)
    -> normalise
    -> filter (hard filters)
    -> enrich (train access, area, renovation signal, suburb family score)
    -> score + rank
    -> write to Google Sheet

Run manually with:  python3 main.py
Run automatically via .github/workflows/scan.yml (Mon/Wed/Fri).

Required environment variables (set as GitHub Secrets in production, or
in a local .env file for manual testing — see README.md):
  DOMAIN_API_KEY
  APPS_SCRIPT_WEB_APP_URL
  APPS_SCRIPT_SHARED_SECRET
"""
import os
import sys
from datetime import datetime, timezone

import pandas as pd

from config import TARGET_SUBURBS, HARD_FILTERS
from ingestion import fetch_domain_listings, normalize_listing
from scoring import passes_hard_filters, score_property
from suburb_family_score import compute_family_score


def build_suburb_family_scores(suburbs):
    """One-off per run — suburbs don't change day to day, but this is
    cheap enough (a handful of suburbs) to just recompute each time rather
    than maintain a separate cache file."""
    scores = {}
    for suburb in suburbs:
        result = compute_family_score(suburb)
        scores[suburb] = result["family_score"]
        print(f"  {suburb}: family_score={result['family_score']} "
              f"(seifa={result['seifa_source']}, crime={result['crime_source']})")
    return scores


def run_pipeline():
    api_key = os.environ.get("DOMAIN_API_KEY")
    if not api_key:
        print("ERROR: DOMAIN_API_KEY not set. See README.md for how to apply "
              "for Domain API access and configure this.", file=sys.stderr)
        sys.exit(1)

    print("Fetching suburb family scores (SEIFA + crime)...")
    suburb_scores = build_suburb_family_scores(TARGET_SUBURBS)

    all_normalized = []
    print("\nFetching listings per suburb...")
    for suburb in TARGET_SUBURBS:
        try:
            raw_listings = fetch_domain_listings(
                api_key, suburb,
                min_price=HARD_FILTERS["min_price"],
                max_price=HARD_FILTERS["max_price"],
            )
        except Exception as e:
            print(f"  WARNING: fetch failed for {suburb}: {e}", file=sys.stderr)
            continue

        for raw in raw_listings:
            normalized = normalize_listing(raw)
            if normalized:
                all_normalized.append(normalized)
        print(f"  {suburb}: {len(raw_listings)} raw -> "
              f"{sum(1 for r in raw_listings if normalize_listing(r))} usable")

    print(f"\nTotal usable listings across all suburbs: {len(all_normalized)}")

    results = []
    for prop in all_normalized:
        ok, reason = passes_hard_filters(prop)
        if not ok:
            continue
        score = score_property(prop, suburb_scores)
        results.append({**prop, **score})

    if not results:
        print("No properties passed the hard filters this run.")
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)
    df["scan_timestamp"] = datetime.now(timezone.utc).isoformat()

    print(f"{len(df)} properties passed filters and were scored.")
    print(df[["address", "price", "priority_score"]].head(10).to_string(index=False))
    return df


def main():
    df = run_pipeline()
    if df.empty:
        return

    webapp_url = os.environ.get("APPS_SCRIPT_WEB_APP_URL")
    shared_secret = os.environ.get("APPS_SCRIPT_SHARED_SECRET")
    if webapp_url and shared_secret:
        from sheets_writer import write_ranked_results
        write_ranked_results(webapp_url, shared_secret, df)
    else:
        print("\nAPPS_SCRIPT_WEB_APP_URL / APPS_SCRIPT_SHARED_SECRET not set — "
              "skipping Sheets write, saving to CSV instead.")
        df.to_csv("ranked_properties.csv", index=False)

    print("\nReminder: Domain off-market alerts and Listing Loop aren't "
          "covered by this automated scan — check those two manually.")


if __name__ == "__main__":
    main()
