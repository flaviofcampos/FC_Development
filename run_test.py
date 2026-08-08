"""
run_test.py — end-to-end test of the pipeline logic using mock data.
No network calls. This is what we run in Step 5 to prove the model works
before wiring in the real Domain API / GTFS / SEIFA sources.
"""
import pandas as pd
from scoring import passes_hard_filters, score_property
from test_mock_data import MOCK_PROPERTIES, MOCK_SUBURB_FAMILY_SCORES


def run():
    results = []
    for prop in MOCK_PROPERTIES:
        # Normalise "2BR + study" style listings would happen in real
        # ingestion; here mock data already reflects that.
        ok, reason = passes_hard_filters(prop)
        if not ok:
            results.append({
                "id": prop["id"], "address": prop["address"], "status": "FILTERED OUT",
                "reason": reason, "priority_score": None,
            })
            continue

        score = score_property(prop, MOCK_SUBURB_FAMILY_SCORES)
        results.append({
            "id": prop["id"],
            "address": prop["address"],
            "status": "PASS",
            "reason": None,
            "price": prop["price"],
            **score,
        })

    df = pd.DataFrame(results)
    # Rank passing properties by priority_score, descending
    df_pass = df[df["status"] == "PASS"].sort_values("priority_score", ascending=False)
    df_fail = df[df["status"] == "FILTERED OUT"]

    print("=" * 80)
    print("RANKED CANDIDATES (passed hard filters)")
    print("=" * 80)
    cols = ["id", "address", "price", "priority_score", "nearest_station",
            "area_sqm", "land_value_multiplier", "area_subscore_raw", "area_subscore",
            "renovation_confidence", "train_access_subscore", "renovation_subscore",
            "family_subscore"]
    print(df_pass[cols].to_string(index=False))

    print()
    print("=" * 80)
    print("FILTERED OUT (hard filter failures — proves filters actually bite)")
    print("=" * 80)
    print(df_fail[["id", "address", "reason"]].to_string(index=False))

    df_pass.to_csv("test_output_ranked.csv", index=False)
    return df_pass, df_fail


if __name__ == "__main__":
    run()
