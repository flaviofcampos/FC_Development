# Melbourne Property Scanner — setup guide

This runs automatically 3x/week (Mon/Wed/Fri) via GitHub Actions and
publishes ranked results to a Google Sheet you check from your phone.
Everything below is a **one-time setup** — once done, you never touch
this again unless you want to tune the criteria in `config.py`.

## What you're setting up and why

| Step | What | Why |
|---|---|---|
| 1 | Domain API access | The actual "what's for sale" data source |
| 2 | Google Sheet + Apps Script Web App | Lets the script write to your Sheet, no Cloud Console needed |
| 3 | A Google Sheet | Where you'll actually check results |
| 4 | GitHub repo + Secrets | Hosts the automation, keeps keys private |

---

## 1. Domain API access

1. Go to https://developer.domain.com.au and sign up (GitHub/Google/email).
2. Create a new project, request access to the **Listings** and **Property**
   packages.
3. As discussed earlier: Domain's API is built for businesses, so approval
   for a personal-use project isn't guaranteed on a fixed timeline. If it
   stalls, the fallback is manually exporting your Domain saved-search
   results to CSV and adapting `main.py` to read that instead of calling
   `fetch_domain_listings()` — the rest of the pipeline (filtering, scoring,
   Sheets output) works identically either way.
4. Once approved, copy your API key — you'll add it as a GitHub Secret in
   step 4.

## 2. Set up the Google Sheet + Apps Script (no Google Cloud needed)

This replaces the original "Google Cloud service account" approach —
it avoids Google Cloud Console and IAM entirely, so it also sidesteps any
Workspace organization policy blocking service account key creation
(a common snag if your Google account is tied to a work/company domain).

1. Create a new, blank Google Sheet.
2. In it, go to **Extensions → Apps Script**.
3. Delete the placeholder code, and paste in the entire contents of
   `AppsScript_Code.gs` (included in this folder).
4. Near the top of the pasted code, change `SHARED_SECRET` from
   `"CHANGE_ME_TO_SOMETHING_RANDOM"` to an actual random string you make
   up (treat it like a password — this is what stops random people on the
   internet from writing to your sheet).
5. Click **Deploy → New deployment**. Choose type **"Web app"**, set
   "Execute as" to **Me**, and "Who has access" to **Anyone**. (This
   sounds more open than it is — the deployment URL only accepts writes
   matching your exact shared secret and payload shape; it doesn't expose
   your Sheet for public browsing.)
6. Google will ask you to authorize the script (it's your own script, on
   your own Sheet — this is expected). Approve it.
7. Copy the generated **Web app URL** — you'll need this and your shared
   secret in step 4 below.

## 3. GitHub repo + Secrets

1. Create a new **private** GitHub repo, push this folder's contents to it.
2. In the repo: Settings → Secrets and variables → Actions → New repository
   secret. Add three secrets:
   - `DOMAIN_API_KEY` — from step 1
   - `APPS_SCRIPT_WEB_APP_URL` — from step 2.7
   - `APPS_SCRIPT_SHARED_SECRET` — the random string you made up in step 2.4
3. That's it — `.github/workflows/scan.yml` will now run automatically
   Mon/Wed/Fri, and you can also trigger it manually anytime from the
   repo's **Actions** tab (workflow_dispatch).

## If you'd rather use the original service-account approach anyway

That's only worth doing if you actually control the Google Cloud
Organization the blocking policy is attached to (Google Workspace admins,
essentially). If that's you: Cloud Console → IAM & Admin → Organization
Policies → find `iam.disableServiceAccountKeyCreation` → add an exception
for your project. For everyone else, the Apps Script route above is
genuinely the easier and equally automated path — there's no functional
downside for a personal-scale project like this.

## 5. Publish the Sheet as a read-only CSV (for the dashboard)

The HTML dashboard (`dashboard.html`) never uses your Domain key or service
account — it only reads a **published, read-only** CSV snapshot of the
results Sheet, which is safe to expose (it's just the ranked property list).

1. Open your Google Sheet → File → **Share** → **Publish to web**.
2. Under "Link", choose the "Ranked Properties" tab and select **CSV** as
   the format, then click **Publish**.
3. Copy the generated link and paste it into the dashboard's "Load
   properties" box the first time you open it.
4. This link stays the same across runs — GitHub Actions overwrites the
   tab's contents each scan, and the published CSV reflects that
   automatically. You won't need to re-publish or re-paste the link again.

## 6. Using the dashboard

Open `dashboard.html` in any browser (double-click it, or host it anywhere
— it's a single static file with no build step). It:
- Reads your published CSV (step 5) — the ranked shortlist, checkable from
  your phone.
- Queries ABS's public SEIFA service live, for the "check a suburb" box.
- Never touches Domain or your Google credentials, by design (see the
  note on the page itself for why).

## Testing the Sheets pipeline BEFORE Domain access arrives

Once you've deployed the Apps Script Web App (section 2), test it with
mock data — this isolates "does my Sheets pipeline work" from "does my
Domain API key work", so if something breaks later you know which half
to debug:

```bash
export APPS_SCRIPT_WEB_APP_URL="your-web-app-url-here"
export APPS_SCRIPT_SHARED_SECRET="your-random-secret-here"
python3 test_sheets_writer.py
```

This writes 4 clearly-fake properties (e.g. "MOCK-1", "12 Sample St") into
your real Sheet's "Ranked Properties" tab — check they appear, then you
know the whole write path works independent of Domain.

## Testing locally before relying on the schedule

```bash
pip install -r requirements.txt
export DOMAIN_API_KEY="your-key-here"
export APPS_SCRIPT_WEB_APP_URL="your-web-app-url-here"
export APPS_SCRIPT_SHARED_SECRET="your-random-secret-here"
python3 main.py
```

If the Apps Script env vars are left unset, it falls back to writing a local
`ranked_properties.csv` instead — useful for a first test run.

## Reading a scan result correctly

- **Red X on the Actions run** = every single suburb fetch failed — almost
  always a bad/placeholder `DOMAIN_API_KEY` or a Domain outage. Check the
  expanded "Run property scan" log for the actual error.
- **Green check, but the Sheet is empty** = fetches genuinely succeeded,
  nothing matched your price/bedroom/etc. filters this run. This is a
  normal, legitimate outcome, not a bug.
- Both of these used to look identical (green check either way) until this
  was fixed — worth knowing if you're looking at an older run.

## Things this automation does NOT cover (do these manually)

- **Domain off-market alerts** and **Listing Loop** — no public API for
  either; check the app/email 2-3x/week yourself (as discussed).
- **Building permit data** (`permits.py`) — needs a real `resource_id` per
  council filled into `COUNCIL_PORTALS` in that file; coverage will be
  patchy since Victoria has no single unified permits dataset.
- **Crime rate data** (`suburb_family_score.py`) — needs manual entry into
  `CRIME_RATE_PER_1000` from crimestatistics.vic.gov.au; defaults to
  neutral (0.5) until filled in.
- **Storeys / true ground-floor status** for apartments — flagged
  `needs_manual_check=True` on every result; glance at photos/floorplan
  before ruling anything in or out on this basis.

## Files in this folder

- `config.py` — all tunable criteria, weights, and target suburbs/stations
- `scoring.py` — the filtering + scoring logic (fully unit-tested, see below)
- `ingestion.py` — Domain API calls + field mapping
- `permits.py` — building permit lookup (Tier 1 renovation signal)
- `suburb_family_score.py` — SEIFA + crime composite per suburb
- `sheets_writer.py` — publishes results via the Apps Script Web App
- `AppsScript_Code.gs` — paste this into your Sheet's Apps Script editor
  (see section 2 above) — replaces the old service-account approach
- `dashboard.html` — the web dashboard (reads the published CSV + ABS live,
  no secrets embedded — see section 5/6 above)
- `main.py` — orchestrates the full pipeline
- `test_mock_data.py` / `run_test.py` — offline tests against fake data,
  proving the scoring logic itself is correct, independent of any live API
- `test_ingestion.py` — proves the Domain field-mapping logic is correct
  against Domain's own documented response shape
- `test_sheets_writer.py` — proves the Apps Script write path works using
  mock data, before Domain access is available
