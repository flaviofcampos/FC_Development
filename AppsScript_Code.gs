/**
 * Code.gs — paste this into the Apps Script editor attached to your
 * Google Sheet (Extensions -> Apps Script). This replaces the whole
 * "Google Cloud service account + JSON key" approach — no Cloud Console,
 * no IAM, no org policy issues, since this runs under your own Google
 * account via a Web App deployment instead of a downloadable key.
 *
 * SETUP (one-time):
 *   1. Open your Google Sheet -> Extensions -> Apps Script
 *   2. Delete any starter code, paste this whole file in
 *   3. Change SHARED_SECRET below to something random you make up
 *   4. Deploy -> New deployment -> type: "Web app"
 *        - Execute as: Me
 *        - Who has access: Anyone
 *      (this only lets people POST data in the exact shape this script
 *      expects, gated by SHARED_SECRET — it does not expose your Sheet
 *      for public browsing)
 *   5. Copy the generated Web App URL — this is APPS_SCRIPT_WEB_APP_URL
 *      in main.py / GitHub Secrets.
 */

const SHARED_SECRET = "CHANGE_ME_TO_SOMETHING_RANDOM";
const TAB_NAME = "Ranked Properties";

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);

    if (payload.secret !== SHARED_SECRET) {
      return ContentService.createTextOutput(
        JSON.stringify({ error: "unauthorized" })
      ).setMimeType(ContentService.MimeType.JSON);
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(TAB_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(TAB_NAME);
    }
    sheet.clear();

    const rows = payload.rows; // array of arrays: [ [headers...], [row1...], ... ]
    if (rows && rows.length > 0) {
      sheet.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
      sheet.setFrozenRows(1);
    }

    return ContentService.createTextOutput(
      JSON.stringify({ success: true, rowsWritten: rows ? rows.length - 1 : 0 })
    ).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(
      JSON.stringify({ error: err.toString() })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

// Lets you sanity-check the deployment URL is live by just visiting it
// in a browser (GET request), separate from the actual doPost() write path.
function doGet(e) {
  return ContentService.createTextOutput(
    JSON.stringify({ status: "Apps Script web app is running. POST data to write." })
  ).setMimeType(ContentService.MimeType.JSON);
}
