// Deploy this as a Google Apps Script Web App:
// 1. Go to https://script.google.com → New Project
// 2. Paste this code
// 3. Click Deploy → New Deployment → Web App
//    - Execute as: Me
//    - Who has access: Anyone
// 4. Copy the deployment URL and set it as LIVE_COUNTER_URL in config.json

const SHEET_NAME = "LiveBots";
const SPREADSHEET_ID = "1qWQn7thB23QoQl3Rp1k6TwDqaifSoIGriETUabKNtuQ";

function doGet(e) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(SHEET_NAME);

  const params = e.parameter;
  const version = params.version || "unknown";
  const year = params.year || new Date().getFullYear();
  const timestamp = new Date().toISOString();

  sheet.appendRow([timestamp, year, version, 1]);

  const data = sheet.getDataRange().getValues();
  const total = data.slice(1).reduce((sum, row) => sum + (row[3] || 0), 0);
  const thisYear = data.slice(1)
    .filter(row => String(row[1]) === String(year))
    .reduce((sum, row) => sum + (row[3] || 0), 0);

  return ContentService
    .createTextOutput(JSON.stringify({ total, thisYear, year, timestamp }))
    .setMimeType(ContentService.MimeType.JSON);
}