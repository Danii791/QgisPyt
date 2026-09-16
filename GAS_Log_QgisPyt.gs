/******************************************************************************
 * GAS_Log_QgisPyt.gs
 * Google Apps Script - Web App standalone untuk silent logging
 * dari QGIS Import CSV Tool (qgis_import_csv_tool.py)
 *
 * Target : Spreadsheet 17gQDW_ohM4DIAsmpPBXsXZstYwGddzosRCMrNeBSW5c
 *           Sheet    : Log Python Qgis
 * Kolom   : Username | Computer | Time | CSV Select | Reference | Status
 *
 * DEPLOY (wajib sebagai project STANDALONE, bukan bound ke spreadsheet):
 *   1. Buka https://script.google.com/home  -> New project
 *   2. Tempel seluruh file ini ke editor
 *   3. Deploy -> New deployment -> Web app
 *       - Execute as     : Me
 *       - Who has access : Anyone
 *   4. Salin URL /exec  -> isi ke GAS_LOG_URL di qgis_import_csv_tool.py
 ******************************************************************************/

var SPREADSHEET_ID = '17gQDW_ohM4DIAsmpPBXsXZstYwGddzosRCMrNeBSW5c';
var SHEET_NAME     = 'Log Python Qgis';
var HEADERS        = ['Username', 'Computer', 'Time', 'CSV Select', 'Reference', 'Status'];

function doGet(e) {
  return recordLog(e);
}

function doPost(e) {
  return recordLog(e);
}

function recordLog(e) {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sheet = ss.getSheetByName(SHEET_NAME);

  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
  }

  var p = (e && e.parameter) || {};
  var row = [
    p.username  || '',
    p.computer  || '',
    p.time      || '',
    p.csv       || '',
    p.reference || '',
    p.status    || ''
  ];
  sheet.appendRow(row);

  return ContentService.createTextOutput('OK');
}