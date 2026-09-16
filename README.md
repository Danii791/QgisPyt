# QgisPyt — QGIS Import CSV Tool

Tool berbasis **QGIS Python Console** untuk mengimpor data CSV survei jalan menjadi layer point di QGIS, melakukan proses **Distance to nearest hub (line to hub)**, lalu mengekspor hasilnya ke CSV `NearHub` (tanpa kolom WKT) sesuai format referensi `L1 Hub line.csv`.

Didukung untuk pengelolaan infrastruktur jalan nasional di **BPJN Aceh** (Balai Pelaksanaan Jalan Nasional).

---

## 📁 Isi Folder

| File | Keterangan |
|------|------------|
| `qgis_import_csv_tool.py` | Script utama — salin & tempel ke QGIS Python Console |
| `GAS_Log_QgisPyt.gs` | Google Apps Script — backend silent logging ke spreadsheet (deploy sebagai Web App standalone) |
| `qgis_import_csv_tool_backup_20260916_124912.py` | Backup sebelum fitur Distance to nearest hub ditambahkan |
| `README.md` | Dokumentasi ini |

---

## ✅ Persyaratan

- **QGIS 3.x** (Python Console, dukungan `qgis`, `processing`, `osgeo`)
- **GDAL** dengan dukungan format `CSV` (sudah default di QGIS)
- Layer berikut harus sudah terbuka di QGIS sebelum menjalankan tool:
  - Layer **Referensi** (sumber point / LinkID, berisi field `TO_STA (km)`)
  - Layer **Data Alat / Hubs** (berisi field `Sta` untuk Roughometer3 atau `Stop distance` untuk IRIMeter2)

---

## 🚀 Cara Pakai

1. Buka QGIS, pastikan layer Referensi & Data Alat sudah terbuka di project.
2. Jalankan (salah satu):
   - **Dari URL (paling cepat)**: buka **Processing ▸ Python Console**, lalu tempel satu baris ini dan Enter:

     ```python
     import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/Danii791/QgisPyt/main/qgis_import_csv_tool.py').read())
     ```

     Script otomatis menjalankan wizard begitu di-`exec` (baris `process_csv()` di akhir).
   - **Dari file lokal**: salin `qgis_import_csv_tool.py`, buka tab **Editor** di Python Console, lalu **Run script**.
3. Ikuti alur wizard:

```
[0/5] Pilih Device Type          → Roughometer3 / IRIMeter2
[1/5] Pilih File CSV             → file output perangkat survei
[2/5] Deteksi header otomatis    → cari baris header & kolom kunci + lon/lat
[3/5] Baca data CSV              → import atribut (point bila lon/lat ada)
[4/5] Buat layer & styling       → simbol + label otomatis
[5/5] Distance to nearest hub    → pilih layer Source & Destination
      + Export CSV NearHub       → dialog simpan CSV
```

---

## 🔧 Perbedaan Tipe Alat

| Aspek | Roughometer3 | IRIMeter2 |
|-------|--------------|-----------|
| Keyword header | `TotalDistance` | `Stop distance` |
| Kolom `Sta` (10 m sequential) | Dibuat otomatis | Tidak ada |
| Hub field | `Sta` | `Stop distance` (auto-detect, case-insensitive) |
| Warna simbol | Biru `#256ae0`, size 1.6 | Hijau `#25e07d`, size 1.6 |
| Label field | `Sta` | `Stop distance` (bold) |

Font label: **Arial 8 pt**, outline hitam + buffer putih untuk keterbacaan.

---

## 📤 Format Output CSV

- Nama default mengikuti kode jalur dari nama layer hubs: `NearHub_L2.csv`, `NearHub_R1.csv`, dst. (fallback `NearHub.csv`).
- **Tanpa kolom WKT** — CSV berisi atribut saja (lihat referensi `L1 Hub line.csv`).
- Layer Options: `HEADER=YES`, `SEPARATOR=COMMA`, `STRING_QUOTING=IF_AMBIGUOUS`, `LINEFORMAT=CRLF`, `WRITE_BOM=NO`, `CREATE_CSVT=NO`.
- Dialog simpan terbuka otomatis di **folder file CSV yang di-import**.

---

## 🎨 Styling Layer Referensi (setelah export)

| Aspek | Nilai |
|-------|-------|
| Simbol | Circle `#ff8800`, size 2 |
| Label | Field `TO_STA (km)`, font Arial 10 pt, hitam, buffer putih |
| Jika field `TO_STA (km)` tidak ditemukan | Warning + daftar field; warna tetap, label dilewati |

---

## ⚠️ Catatan Teknis

- **`GEOMETRY=NONE` tidak didukung** oleh GDAL yang terpasang → export CSV memakai salinan layer **tanpa geometri** (memory layer) agar tidak ada kolom WKT.
- Import modul processing QGIS 3 wajib menggunakan `from qgis import processing`.
- Semua message box & dialog memakai **bahasa Inggris profesional**; log di Python Console tetap berbahasa Indonesia.
- Jika processing line-to-hub gagal pada id `qgis:...`, tool otomatis mencoba fallback ke `native:...`.
- **Run dari URL**: `exec(urllib.request.urlopen('...'))` menjalankan kode dari jaringan — hanya gunakan URL yang Anda percaya (repo ini). Bila berada di belakang proxy korporat, pastikan proxy ter-set di lingkungan sistem supaya `urllib` bisa mengakses GitHub.

---

## 🔇 Silent Logging ke Google Spreadsheet

Tool mencatat setiap eksekusi secara **silent** (tanpa popup, tidak menghentikan alur) ke sheet **`Log Python Qgis`** pada spreadsheet `17gQDW_ohM4DIAsmpPBXsXZstYwGddzosRCMrNeBSW5c`.

| Kolom | Isi |
|-------|-----|
| `Username` | User Windows yang menjalankan QGIS |
| `Computer` | Nama komputer |
| `Time` | Waktu lokal `YYYY-MM-DD HH:MM:SS` |
| `CSV Select` | Nama file CSV yang di-import (tanpa `.csv`), mis. `01_027_L1_5M` |
| `Reference` | Nama layer Referensi yang dipilih di QGIS |
| `Status` | `PROSES HUB & EXPORT SELESAI!` atau `User memilih TIDAK lanjut ke hub.` |

### Setup backend (sekali saja, butuh akun Google pemilik spreadsheet)

> **Penting:** spreadsheet itu **sudah punya project Apps Script aktif** (xOpenWorkbook / `AKfycbz...`). Spreadsheet hanya bisa punya **satu** project *bound*, jadi logging ini wajib dibuat sebagai project **standalone** — tidak menyentuh script yang sudah aktif.

1. Buka `script.google.com/home` → **New project** (jangan via *Extensions → Apps Script* dari spreadsheet, supaya tidak memasuki project AKfycbz).
2. Tempel seluruh isi `GAS_Log_QgisPyt.gs`.
3. Simpan → **Deploy → New deployment → Web app**:
   - *Execute as*: **Me**
   - *Who has access*: **Anyone**
4. Salin URL `/exec` dan pasang di mesin yang boleh mengirim log (lihat di bawah).

### Mengaktifkan logging pada sebuah mesin

URL web app **tidak ditanam di script** (repo ini public, supaya URL tidak disalahgunakan untuk men-spam sheet). Tool mencari URL dengan urutan prioritas:

1. **Env var** `QGIS_LOG_URL`
2. **File lokal** `~/.qgis_log_config.txt` (di Windows: `C:\Users\<user>\.qgis_log_config.txt`)
3. Konstanta `GAS_LOG_URL` di dalam script (default kosong)

Contoh isi file config (satu baris dalam format `key=value`):

```
GAS_LOG_URL=https://script.google.com/macros/s/xxxxx/exec
```

Mesin **tanpa** config/env → tool tetap berjalan normal, logging dilewati diam-diam (catatan `[LOG]` di Python Console).

## ✍️ Author

**Chepie Rosdian Rhamdani**
- Consultant ID: 23
- Team Lead ID: 563
- Surv Tool ID: 6558