# QgisPyt — QGIS Import CSV Tool

**Tujuan tool:** Script Python untuk QGIS Console yang mengimpor data **CSV hasil survei jalan** (Roughometer3 / IRIMeter2) menjadi **layer point** di QGIS, menghitung **jarak ke hub terdekat** (*Distance to nearest hub / line to hub*), lalu mengekspor CSV `NearHub` **tanpa kolom WKT** sesuai format referensi `L1 Hub line.csv`. Setiap penggunaan tercatat otomatis (silent log) ke spreadsheet tim.

Didukung untuk pengelolaan infrastruktur jalan nasional di **BPJN Aceh** (Balai Pelaksanaan Jalan Nasional).

---

## 📁 Isi Folder

| File | Keterangan |
|------|------------|
| `qgis_import_csv_tool.py` | Script utama — dijalankan via Python Console (one-liner di bawah) |
| `GAS_Log_QgisPyt.gs` | Google Apps Script — backend silent logging (deploy sebagai Web App standalone) |
| `README.md` | Dokumentasi ini |

---

## 🚀 Cara Pakai

1. Buka **QGIS 3.x**, pastikan layer berikut sudah terbuka di project:
   - **Referensi** — layer point, berisi field `TO_STA (km)`
   - **Raw Data** — layer hubs, berisi field `Sta` (Roughometer3) atau `Stop distance` (IRIMeter2)
2. Buka **Processing ▸ Python Console**, tempel perintah ini lalu tekan **Enter**:

   ```python
   import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/Danii791/QgisPyt/main/qgis_import_csv_tool.py').read())
   ```

3. Ikuti wizard:

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

## 🔇 Silent Logging

Setiap eksekusi tercatat **silent** (tanpa popup, tidak menghentikan alur) ke sheet **`Log Python Qgis`** pada spreadsheet tim — kolom: `Username`, `Computer`, `Time`, `CSV Select`, `Reference`, `Status` (`PROSES HUB & EXPORT SELESAI!` atau `User memilih TIDAK lanjut ke hub.`).

URL web app **tertanam langsung** di konstanta `GAS_LOG_URL` pada script, jadi semua pengguna otomatis tercatat tanpa setup. Override per-mesin dimungkinkan via env `QGIS_LOG_URL` atau file `~/.qgis_log_config.txt`.

> **Catatan keamanan:** repo ini public sehingga URL web app terlihat publik. Web app hanya menambahkan baris (tidak membaca data), namun berpotensi di-spam. Detail setup backend (Apps Script standalone) dapat diminta dari admin tool ini.

---

## ⚠️ Catatan Teknis

- **`GEOMETRY=NONE` tidak didukung** oleh GDAL yang terpasang → export CSV memakai salinan layer **tanpa geometri** (memory layer) agar tidak ada kolom WKT.
- Import modul processing QGIS 3 wajib menggunakan `from qgis import processing`.
- Jika processing line-to-hub gagal pada id `qgis:...`, tool otomatis mencoba fallback ke `native:...`.
- **Run dari URL** memakai `exec(...)` → menjalankan kode dari jaringan; hanya gunakan URL yang Anda percaya. Di belakang proxy korporat, pastikan proxy ter-set di sistem supaya `urllib` bisa mengakses GitHub.

---

## ✍️ Author

**Chepie Rosdian Rhamdani**
- Consultant ID: 23
- Team Lead ID: 563
- Surv Tool ID: 6558