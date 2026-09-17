# ============================================================
# QGIS Python Console Script
# Import CSV -> Deteksi Header -> Layer Point -> Kolom Sta -> Simbol & Label
# ============================================================
# CARA PAKAI: Copy seluruh script ini ke QGIS Python Console lalu Run

import os
import csv
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QInputDialog
from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QColor, QFont
from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorFileWriter,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsProperty,
    QgsRenderContext,
    QgsCoordinateTransformContext,
)
from qgis import processing


# ============================================================
# KONFIGURASI SILENT LOGGING KE GOOGLE SPREADSHEET
#   - Tambahkan kode Google Apps Script (GAS_Log_QgisPyt.gs)
#     sebagai project STANDALONE, deploy Web App ('Execute as: Me',
#     'Who has access: Anyone'), lalu set URL /exec-nya.
#   - Sheet tujuan: 'Log Python Qgis' pada spreadsheet id:
#     17gQDW_ohM4DIAsmpPBXsXZstYwGddzosRCMrNeBSW5c
#
#   URL web app tertanam di konstanta GAS_LOG_URL di bawah (default aktif).
#   Prioritas pemuatan URL via _load_gas_log_url():
#     1. Env var   : QGIS_LOG_URL
#     2. File lokal: ~/.qgis_log_config.txt
#                    (baris: GAS_LOG_URL=https://script.google.com/macros/s/XXXX/exec)
#     3. Konstanta : GAS_LOG_URL di bawah (default aktif)
# ============================================================
GAS_LOG_URL = "https://script.google.com/macros/s/AKfycbxx3m4PQY_fzfo5Dzfy-HA635o8ym6LaNknzi9V-3okL9hhHEqrRI36C8hl2H4t6wsF/exec"
GAS_LOG_CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.qgis_log_config.txt')


def _load_gas_log_url():
    """Baca URL web app logging dari env, file config lokal, lalu konstanta."""
    env_url = os.environ.get('QGIS_LOG_URL', '').strip()
    if env_url:
        return env_url
    try:
        with open(GAS_LOG_CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.lower().startswith('gas_log_url='):
                    return line.split('=', 1)[1].strip()
                if line.startswith('http'):
                    return line
    except Exception:
        pass
    return GAS_LOG_URL


LON_KEYWORDS = ['longitude', 'long', 'lon', 'x', 'xcoord', 'x_coordinate',
                'point_x', 'easting', 'lng']
LAT_KEYWORDS = ['latitude', 'lat', 'y', 'ycoord', 'y_coordinate',
                'point_y', 'northing']


def is_lon_header(name):
    """Cek apakah nama kolom adalah Longitude (exact match atau substring 'long')"""
    n = name.lower()
    for kw in LON_KEYWORDS:
        if n == kw:
            return True
    if 'long' in n:
        return True
    return False


def is_lat_header(name):
    """Cek apakah nama kolom adalah Latitude (exact match atau substring 'lat')"""
    n = name.lower()
    for kw in LAT_KEYWORDS:
        if n == kw:
            return True
    if 'lat' in n:
        return True
    return False


def identify_columns(headers, keyword_norm):
    """Cari index kolom keyword (TotalDistance/Stop distance), Longitude, Latitude dari list header"""
    key_col = None
    lon_col = None
    lat_col = None
    
    for i, h in enumerate(headers):
        h_clean = h.lower().replace(' ', '').replace('_', '').replace('-', '')
        # Cari kolom keyword utama (misal 'totaldistance' atau 'stopdistance')
        if keyword_norm in h_clean:
            if key_col is None:
                key_col = i
        # Cari Longitude / X
        if is_lon_header(h):
            if lon_col is None:
                lon_col = i
        # Cari Latitude / Y
        if is_lat_header(h):
            if lat_col is None:
                lat_col = i
    
    return key_col, lon_col, lat_col


def detect_headers(filepath, keyword):
    """
    Auto-search baris header CSV (cara sederhana):
    - Scan SELURUH baris (pakai csv.reader, SAMA seperti read_csv_data
      agar index baris konsisten & tidak ada pergeseran offset)
    - Begitu ketemu baris yang mengandung kata kunci 'TotalDistance'/'Stop distance'
      → baris itu LANGSUNG dijadikan baris header (tanpa harus memenuhi Longitude/Latitude)
    - Cari kolom longitude/latitude BILA ADA di baris header tsb (boleh None)
    Returns: (headers_list, key_col, lon_col, lat_col, delimiter, header_row_number)
    """
    keyword_norm = keyword.lower().replace(' ', '').replace('_', '').replace('-', '')
    delimiters = [',', ';', '\t', '|']
    
    for delim in delimiters:
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                all_rows = list(csv.reader(f, delimiter=delim))
        except csv.Error:
            continue
        
        for row_idx, row in enumerate(all_rows):
            if not row:
                continue
            parts = [p.strip().strip('"').strip("'") for p in row]
            if len(parts) < 2:
                continue
            
            # Lewati baris yang jelas komentar/banner di awal file
            first_cell = parts[0].lstrip()
            if first_cell.startswith(('#', '//', '*', '!', '=')):
                continue
            
            # Cek apakah baris ini mengandung keyword (case-insensitive)
            has_key = False
            for p in parts:
                p_clean = p.lower().replace(' ', '').replace('_', '').replace('-', '')
                if keyword_norm in p_clean:
                    has_key = True
                    break
            
            if has_key:
                key_col, lon_col, lat_col = identify_columns(parts, keyword_norm)
                # LANGSUNG anggap baris ini header, tanpa wajib lon/lat ada
                return parts, key_col, lon_col, lat_col, delim, row_idx
    
    return None, None, None, None, None, None


def read_csv_data(filepath, delimiter, header_row_number):
    """
    Baca data CSV mulai dari baris SETELAH header row.
    Baris-baris sebelum header row (yang bukan header) di-skip otomatis.
    """
    rows = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=delimiter)
        all_rows = list(reader)
    
    # header_row_number adalah index baris header (0-based)
    data_rows = all_rows[header_row_number + 1:]
    
    for row in data_rows:
        if not row:
            continue
        # Skip baris yang jumlah kolomnya kurang dari header
        if len(row) < 2:
            continue
        rows.append(row)
    
    return rows


def create_layer_from_csv(filepath, csv_data, headers, lon_col, lat_col, totaldist_col, layer_name):
    """Buat QgsVectorLayer dari data CSV"""
    
    # Bangun field list untuk delimitedtext
    field_defs = []
    for i, h in enumerate(headers):
        if i == totaldist_col:
            field_defs.append('{}:double'.format(h.replace(' ', '_').replace('"', '')))
        elif i == lon_col or i == lat_col:
            continue  # skip lon/lat dari atribut, sudah jadi geometry
        else:
            field_defs.append('{}:string'.format(h.replace(' ', '_').replace('"', '')))
    
    # Tambah field Sta di awal
    field_defs.insert(0, 'Sta:double')
    
    # Build uri untuk delimitedtext
    field_str = '&'.join(field_defs)
    uri = (
        'file:///{path}?'
        'delimiter={delim}'
        '&xField={xfield}'
        '&yField={yfield}'
        '&crs=epsg:4326'
        '&fieldType=double'
        '&fields={fields}'
        '&skipLines=1'
    ).format(
        path=filepath.replace('\\', '/'),
        delim=delimiter,
        xfield=headers[lon_col],
        yfield=headers[lat_col],
        fields=field_str
    )
    
    layer = QgsVectorLayer(uri, layer_name, 'delimitedtext')
    
    if not layer.isValid():
        print("[ERROR] Gagal membuat layer dari CSV!")
        return None
    
    return layer


def get_loaded_vector_layers():
    """Kembalikan daftar (nama, layer) dari semua vector layer yang sedang loaded di QGIS"""
    layers = []
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            layers.append((layer.name(), layer))
    return sorted(layers, key=lambda x: x[0])


def prompt_select_layer(title, prompt):
    """Dialog dropdown untuk memilih layer dari project"""
    layers = get_loaded_vector_layers()
    if not layers:
        QMessageBox.warning(None, "Warning",
            "No vector layers are currently open in QGIS!\n"
            "Please open the Reference and Equipment Data layers first.")
        return None
    
    names = [n for n, l in layers]
    name, ok = QInputDialog.getItem(None, title, prompt, names, 0, False)
    if not ok:
        return None
    
    for n, l in layers:
        if n == name:
            return l
    return None


def find_field_contains(layer, keyword_norm):
    """
    Cari nama field di layer yang mengandung keyword (normalisasi spasi/underscore,
    case-insensitive). Kembalikan NAMA ASLI field di layer, atau None bila tidak ada.
    Contoh: layer hubs berfield 'Stop distance' -> cari 'stopdistance' -> 'Stop distance'.
    """
    for f in layer.fields():
        fn = f.name().lower().replace(' ', '').replace('_', '').replace('-', '')
        if keyword_norm in fn:
            return f.name()
    return None


def log_to_spreadsheet(csv_name, reference, status):
    """
    Silent logging ke Google Spreadsheet (sheet 'Log Python Qgis').
    Mengirim GET ke Web App Google Apps Script; TIDAK menampilkan dialog
    apa pun dan TIDAK menghentikan alur tool bila gagal.
    URL diambil dari env QGIS_LOG_URL / file ~/.qgis_log_config.txt /
    konstanta GAS_LOG_URL. Bila kosong, logging dilewati diam-diam.
    """
    gas_url = _load_gas_log_url()
    if not gas_url:
        print("[LOG] URL logging tidak ditemukan - logging ke spreadsheet dilewati.")
        return False

    params = urllib.parse.urlencode({
        'username': os.environ.get('USERNAME', ''),
        'computer': os.environ.get('COMPUTERNAME', ''),
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'csv': csv_name,
        'reference': reference,
        'status': status,
    })
    url = gas_url + '?' + params

    try:
        for i in range(3):
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    if resp.read().strip() == b'OK':
                        return True
            except Exception:
                pass
            time.sleep(2)
    except Exception:
        pass

    print("[WARN] Gagal kirim log ke spreadsheet (silent).")
    return False


def run_distance_to_nearest_hub(src_layer, hubs_layer, hub_field='Sta'):
    """
    Jalankan processing 'Distance to nearest hub (line to hub)'
    UNIT = 0 (Meters), FIELD = hub_field (Sta / Stop distance)
    """
    candidates = ['qgis:distancetonearesthublinetohub', 'native:distancetonearesthublinetohub']
    
    chosen = None
    try:
        check = processing.algorithmExists
    except AttributeError:
        check = None      # QGIS versi lama tanpa algorithmExists
    
    if check is not None:
        for c in candidates:
            if check(c):
                chosen = c
                break
        if chosen is None:
            print("[ERROR] Algoritma 'Distance to nearest hub (line to hub)' tidak ditemukan!")
            QMessageBox.critical(None, "Error",
                "Algorithm 'Distance to nearest hub (line to hub)' was not found in the Processing Toolbox.")
            return None
    else:
        chosen = candidates[0]
    
    print("\n[HUB] Menjalankan Distance to nearest hub (line to hub)...")
    print("  Source points (Referensi) : {}".format(src_layer.name()))
    print("  Destination hubs (Data)   : {}".format(hubs_layer.name()))
    print("  Hub name attribute        : {}".format(hub_field))
    print("  Measurement unit          : Meters")
    
    params = {
        'INPUT':  src_layer,
        'HUBS':   hubs_layer,
        'FIELD':  hub_field,
        'UNIT':   0,          # 0 = Meters
        'OUTPUT': 'memory:',
    }
    
    try:
        result = processing.run(chosen, params)
    except Exception as e:
        if chosen != candidates[-1]:
            # Coba fallback ke id lain bila qgis: gagal
            try:
                result = processing.run(candidates[-1], params)
                chosen = candidates[-1]
            except Exception as e2:
                print("[ERROR] Gagal menjalankan: {}\n  Detail: {}\n  Fallback detail: {}".format(chosen, e, e2))
                QMessageBox.critical(None, "Error",
                    "Failed to run processing:\n{}\n\nThe fallback also failed:\n{}".format(e, e2))
                return None
        else:
            print("[ERROR] Gagal menjalankan '{}': {}".format(chosen, e))
            QMessageBox.critical(None, "Error",
                "Failed to run processing '{}':\n{}".format(chosen, e))
            return None
    
    out_layer = result['OUTPUT']
    
    if out_layer is None or not out_layer.isValid():
        print("[ERROR] Processing Distance to nearest hub GAGAL!")
        QMessageBox.critical(None, "Error", "Processing 'Distance to nearest hub (line to hub)' failed to run.")
        return None
    
    out_layer.setName('Distance to Nearest Hub')
    QgsProject.instance().addMapLayer(out_layer)
    print("  Layer 'Distance to Nearest Hub' ditambahkan ke QGIS.")
    print("  Jumlah fitur: {}".format(out_layer.featureCount()))
    
    return out_layer


def _strip_geometry_for_csv(src_layer):
    """
    Buat salinan layer MEMORI TANPA GEOMETRI (NoGeometry).
    Tujuannya: export CSV tanpa kolom geometri (WKT/X/Y),
    kompatibel semua versi QGIS (opsi GEOMETRY=NONE tidak selalu didukung).
    """
    mem = QgsVectorLayer('?crs=' + src_layer.crs().authid(), 'NearHub_export', 'memory')
    if not mem.isValid():
        print("[WARN] Gagal membuat layer tanpa geometri; memakai layer asli (geometri akan ikut tertulis).")
        return src_layer
    
    provider = mem.dataProvider()
    provider.addAttributes([f for f in src_layer.fields()])
    mem.updateFields()
    
    feats = []
    for f in src_layer.getFeatures():
        nf = QgsFeature(mem.fields())
        nf.setAttributes(f.attributes())
        feats.append(nf)
    provider.addFeatures(feats)
    mem.updateExtents()
    return mem


def _hub_token(name):
    """
    Ambil token L1/L2/L3/R1/R2/R3 dari nama layer alat.
    Contoh: 'Survey NL2' -> 'L2', 'Survey OR1' -> 'R1'. None bila tidak ketemu.
    """
    m = re.search(r'([LR][123])', name.upper())
    return m.group(1) if m else None


def export_nearhub_csv(out_layer, hub_layer=None, start_dir=None):
    """
    Export layer hasil hub ke CSV.
    - Dialog Save As (bisa ganti nama), nama default otomatis dari layer alat:
      'Survey NL2' -> NearHub_L2.csv, 'Survey OR1' -> NearHub_R1.csv,
      tanpa token -> NearHub.csv.
    - Bila start_dir diisi, dialog terbuka di direktori tersebut (mis. folder
      file CSV yang di-import).
    - Layer Options (persis referensi 'L1 Hub line.csv'):
      CREATE_CSVT=NO, HEADER=YES, LINEFORMAT=CRLF, SEPARATOR=COMMA,
      STRING_QUOTING=IF_AMBIGUOUS, WRITE_BOM=NO.
      Geometri tidak ditulis (layer di-copy tanpa geometri).
    """
    name_hint = hub_layer.name() if hub_layer is not None else ''
    token = _hub_token(name_hint)
    default_file = 'NearHub_{}.csv'.format(token) if token else 'NearHub.csv'
    
    default_path = default_file
    if start_dir:
        default_path = os.path.join(start_dir, default_file)
    
    csv_path, selected_filter = QFileDialog.getSaveFileName(
        None,
        "Save CSV ({})".format(default_file),
        default_path,
        "CSV Files (*.csv)"
    )
    
    if not csv_path:
        print("[BATAL] Export CSV dibatalkan (tidak ada nama/lokasi dipilih).")
        return None
    
    if not csv_path.lower().endswith('.csv'):
        csv_path += '.csv'
    
    print("\n[EXPORT] Menulis CSV: {}".format(csv_path))
    
    export_layer = _strip_geometry_for_csv(out_layer)
    
    opt = QgsVectorFileWriter.SaveVectorOptions()
    opt.driverName = 'CSV'
    opt.fileEncoding = 'UTF-8'
    opt.layerName = 'NearHub'
    opt.layerOptions = [
        'HEADER=YES',
        'SEPARATOR=COMMA',
        'STRING_QUOTING=IF_AMBIGUOUS',
        'LINEFORMAT=CRLF',
        'WRITE_BOM=NO',
        'CREATE_CSVT=NO',
    ]
    
    try:
        error, msg, newFileName, saved = QgsVectorFileWriter.writeAsVectorFormatV3(
            export_layer,
            csv_path,
            QgsCoordinateTransformContext(),
            opt
        )
        if saved:
            print("  CSV berhasil disimpan: {}".format(newFileName))
            return newFileName
        print("  [ERROR] Gagal menulis CSV: {} - {}".format(error, msg))
    except AttributeError:
        # Fallback untuk QGIS versi lama (legacy writeAsVectorFormat)
        layer_options = opt.layerOptions
        try:
            result = QgsVectorFileWriter.writeAsVectorFormat(
                export_layer,
                csv_path,
                'UTF-8',
                export_layer.crs(),
                'CSV',
                onlySelected=False,
                layerOptions=layer_options
            )
        except TypeError:
            result = QgsVectorFileWriter.writeAsVectorFormat(
                export_layer,
                csv_path,
                'UTF-8',
                export_layer.crs(),
                'CSV',
                onlySelected=False
            )
        # Tangani return type: tuple(2/4), int, atau string
        code = result
        if isinstance(result, (tuple, list)):
            code = result[0]
        try:
            code = int(code)
            if code == 0:
                print("  CSV berhasil disimpan (legacy): {}".format(csv_path))
                return csv_path
        except (TypeError, ValueError):
            pass
        print("  [ERROR] Gagal menulis CSV (legacy): {}".format(result))
    
    QMessageBox.critical(None, "Error", "Failed to export CSV.\nSee details in the Python Console.")
    return None


def process_csv():
    """Main function - jalankan workflow"""
    
    print("=" * 60)
    print("  QGIS IMPORT CSV TOOL")
    print("  Import CSV -> Layer -> Simbol & Label -> Hub")
    print("=" * 60)
    
    # LANGKAH 0: Pilih Jenis Alat
    print("\n[0/5] Pilih jenis alat...")
    tool_types = ["Roughometer3", "IRIMeter2"]
    tool_type, ok = QInputDialog.getItem(
        None,
        "Select Device Type",
        "Device type:",
        tool_types,
        0,
        False
    )
    if not ok or not tool_type:
        print("[BATAL] Jenis alat tidak dipilih.")
        return
    
    is_roughometer = (tool_type == "Roughometer3")
    keyword = 'TotalDistance' if is_roughometer else 'Stop distance'
    keyword_norm = keyword.lower().replace(' ', '')  # totaldistance / stopdistance
    
    print("  Alat: {} (keyword header: '{}')".format(tool_type, keyword))
    print("  Buat kolom Sta: {}".format("YA" if is_roughometer else "TIDAK"))
    
    # LANGKAH 1: Pilih File CSV
    print("\n[1/5] Pilih file CSV...")
    filepath, _ = QFileDialog.getOpenFileName(
        None,
        "Select CSV File",
        "",
        "CSV Files (*.csv);;All Files (*)"
    )
    
    if not filepath:
        print("[BATAL] Tidak ada file yang dipilih.")
        return
    
    selected_file = os.path.basename(filepath)
    csv_name = os.path.splitext(selected_file)[0]  # contoh: 01_027_L1_5M
    print("  File dipilih: {}".format(filepath))
    
    # LANGKAH 2: Deteksi Header
    print("\n[2/5] Auto-search baris header CSV...")
    headers, key_col, lon_col, lat_col, delimiter, header_row = detect_headers(filepath, keyword)
    
    if headers is None:
        QMessageBox.warning(None, "Error", "Failed to read or find the CSV header row!")
        print("[ERROR] Gagal membaca header!")
        return
    
    print("  Baris header ditemukan di: row #{}".format(header_row + 1))
    print("  Headers: {}".format(headers))
    
    if key_col is None:
        QMessageBox.warning(None, "Error",
            "Column '{}' not found!\n"
            "Available headers: {}".format(keyword, ', '.join(headers)))
        print("[ERROR] Kolom '{}' tidak ditemukan!".format(keyword))
        return
    
    if lon_col is None or lat_col is None:
        print("  [INFO] Kolom Longitude/Latitude TIDAK ditemukan di baris header.")
        print("         Semua kolom tetap di-import ke atribut tanpa geometri point.")
    
    print("  Keyword kolom: {} (index {})".format(headers[key_col], key_col))
    if lon_col is not None:
        print("  Longitude kolom: {} (index {})".format(headers[lon_col], lon_col))
    else:
        print("  Longitude kolom: TIDAK ADA")
    if lat_col is not None:
        print("  Latitude kolom: {} (index {})".format(headers[lat_col], lat_col))
    else:
        print("  Latitude kolom: TIDAK ADA")
    print("  Delimiter: '{}'".format(delimiter))
    
    # LANGKAH 3: Baca Data CSV
    print("\n[3/5] Membaca data CSV...")
    csv_data = read_csv_data(filepath, delimiter, header_row)
    print("  Jumlah baris data: {}".format(len(csv_data)))
    
    if len(csv_data) == 0:
        QMessageBox.warning(None, "Warning", "CSV is empty or contains no data!")
        print("[ERROR] Data CSV kosong!")
        return
    
    # LANGKAH 4: Buat Layer & Proses
    print("\n[4/5] Membuat layer QGIS...")
    layer_name = os.path.splitext(selected_file)[0]
    
    # Build attribute fields
    # Roughometer3: tambah kolom Sta di awal
    # IRIMeter2   : TANPA Sta; kolom keyword dibuat persis bernama seperti header
    field_list = []
    if is_roughometer:
        field_list.append(QgsField('Sta', QVariant.LongLong))
    
    label_field_name = 'Sta' if is_roughometer else keyword
    
    for i, h in enumerate(headers):
        if lon_col is not None and i == lon_col:
            continue
        if lat_col is not None and i == lat_col:
            continue
        if i == key_col and not is_roughometer:
            # Kolom 'Stop distance' tetap bernama persis 'Stop distance'
            field_list.append(QgsField(keyword, QVariant.String))
            continue
        clean_name = h.replace(' ', '_').replace('"', '')
        if not clean_name:
            clean_name = 'col_{}'.format(i)
        field_list.append(QgsField(clean_name, QVariant.String))
    
    # Buat memory layer lalu populate
    crs = 'EPSG:4326'
    uri = 'Point?crs={}&index=yes'.format(crs)
    layer = QgsVectorLayer(uri, layer_name, 'memory')
    
    if not layer.isValid():
        print("[ERROR] Gagal membuat memory layer!")
        return
    
    # Tambah fields
    pr = layer.dataProvider()
    pr.addAttributes(field_list)
    layer.updateFields()
    
    # Populate features
    features = []
    no_geom_count = 0
    sta_counter = 0
    
    # True jika kedua kolom lon/lat ditemukan di header
    has_geometry_cols = (lon_col is not None and lat_col is not None)
    
    for row in csv_data:
        feat = QgsFeature()
        
        # Buat geometry HANYA jika baris punya long/lat yang valid
        point = None
        if has_geometry_cols:
            try:
                lon = float(str(row[lon_col]).strip().replace(',', '.'))
                lat = float(str(row[lat_col]).strip().replace(',', '.'))
                point = QgsPointXY(lon, lat)
            except (ValueError, IndexError):
                point = None
        
        if point is not None:
            feat.setGeometry(QgsGeometry.fromPointXY(point))
        else:
            no_geom_count += 1  # feature tetap dibuat, tanpa geometri
        
        # Roughometer3: values = [Sta sequential 10,20,30,...] + field lain
        # IRIMeter2   : values = field lain (tanpa Sta)
        values = []
        if is_roughometer:
            sta_counter += 1
            values.append(sta_counter * 10)  # sequential: 10, 20, 30, ...
        
        for i, h in enumerate(headers):
            if lon_col is not None and i == lon_col:
                continue
            if lat_col is not None and i == lat_col:
                continue
            values.append(row[i] if i < len(row) else '')
        
        feat.setAttributes(values)
        features.append(feat)
    
    pr.addFeatures(features)
    layer.updateExtents()
    layer.updateFields()
    
    print("  Features ditambahkan: {}".format(len(features)))
    if no_geom_count > 0:
        print("  Feature TANPA geometri (lon/lat kosong/tak ada): {}".format(no_geom_count))
    
    # Tambahkan layer ke project
    QgsProject.instance().addMapLayer(layer)
    print("  Layer '{}' ditambahkan ke QGIS!".format(layer_name))
    
    # -------------------------------------------------------
    # SIMBOL: Simple Marker, Size 1.6
    #   Roughometer3 -> biru #256ae0 ; IRIMeter2 -> hijau #25e07d
    # -------------------------------------------------------
    marker_color = '#256ae0' if is_roughometer else '#25e07d'
    color_name = 'biru #256ae0' if is_roughometer else 'hijau #25e07d'
    
    print("\n[STYLE] Mengatur simbol simple marker {} size 1.6...".format(color_name))
    
    symbol = QgsMarkerSymbol.createSimple({
        'name': 'circle',
        'color': marker_color,
        'outline_color': '0,0,0,255', # Outline hitam
        'outline_width': '0',         # Sinambung/hairline
        'size': '1.6'
    })
    
    renderer = QgsSingleSymbolRenderer(symbol)
    layer.setRenderer(renderer)
    
    # Update renderer
    context = QgsRenderContext.fromMapSettings(iface.mapCanvas().mapSettings())
    layer.renderer().startRender(context, layer.fields())
    layer.renderer().stopRender(context)
    
    layer.triggerRepaint()
    print("  Simbol: circle, {}, size 1.6".format(color_name))
    
    # -------------------------------------------------------
    # LABEL: Single Labels -> Value = label_field_name
    # -------------------------------------------------------
    print("\n[LABEL] Mengatur label single labels -> {}...".format(label_field_name))
    
    label_settings = QgsPalLayerSettings()
    label_settings.fieldName = label_field_name
    label_settings.enabled = True
    
    # Format teks label
    text_format = QgsTextFormat()
    font = QFont("Arial")
    font.setPointSize(8)
    text_format.setFont(font)
    text_format.setSize(8)
    text_format.setColor(QColor(0, 0, 0))  # Hitam
    
    # Buffer agar label mudah dibaca
    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(0.5)
    buffer_settings.setColor(QColor(255, 255, 255))
    text_format.setBuffer(buffer_settings)
    
    label_settings.setFormat(text_format)
    
    # Terapkan labeling
    labeling = QgsVectorLayerSimpleLabeling(label_settings)
    layer.setLabeling(labeling)
    layer.setLabelsEnabled(True)
    
    layer.triggerRepaint()
    layer.updateExtents()
    
    print("  Label field: {}".format(label_field_name))
    print("  Label font: Arial 8pt, hitam, white buffer")
    
    # -------------------------------------------------------
    # ZOOM ke Layer
    # -------------------------------------------------------
    canvas = iface.mapCanvas()
    canvas.setExtent(layer.extent())
    canvas.refresh()
    
    if is_roughometer:
        import_desc = "- Kolom Sta = sequential 10, 20, 30, ..."
    else:
        import_desc = "- Tanpa kolom Sta (label = nilai 'Stop distance')"
    
    print("\n" + "=" * 60)
    print("  SELESAI!")
    print("  Layer '{}' berhasil dibuat dengan:".format(layer_name))
    print("    - {} baris data di-import".format(len(features)))
    print("    - {}".format(import_desc))
    print("    - Simbol: {}, size 1.6".format(color_name))
    print("    - Label: {}".format(label_field_name))
    if no_geom_count > 0:
        print("    - Peringatan: {} baris tanpa geometri (lon/lat kosong/tak ada)".format(no_geom_count))
    print("=" * 60)
    
    QMessageBox.information(
        None,
        "Done!",
        "Layer '{}' created successfully!\n\n"
        "- {} data rows imported\n"
        "- {}\n"
        "- Symbol: {}, size 1.6\n"
        "- Label: {}".format(
            layer_name, len(features), import_desc, color_name, label_field_name
        )
    )
    
    # -------------------------------------------------------
    # LANJUTAN: Distance to nearest hub (line to hub)?
    # -------------------------------------------------------
    reply = QMessageBox.question(
        None,
        "Continue?",
        "Proceed to 'Distance to nearest hub (line to hub)'?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    
    if reply != QMessageBox.Yes:
        print("[SELESAI] User memilih TIDAK lanjut ke hub.")
        log_to_spreadsheet(csv_name, "", "User memilih TIDAK lanjut ke hub.")
        return None
    
    # Pilih Source points layer (Referensi)
    src_layer = prompt_select_layer(
        "Source Points Layer",
        "Select Source points layer (Reference):"
    )
    if src_layer is None:
        print("[BATAL] Source points layer tidak dipilih.")
        return None
    
    # Pilih Destination hubs layer (Data Alat)
    hubs_layer = prompt_select_layer(
        "Destination Hubs Layer",
        "Select Destination hubs layer (Raw Data):"
    )
    if hubs_layer is None:
        print("[BATAL] Destination hubs layer tidak dipilih.")
        return None
    
    # Validasi field hub ada di hubs layer
    # Roughometer3: cari field 'Sta'
    # IRIMeter2   : cari field 'Stop distance' (case-insensitive, norm. spasi/underscore)
    if is_roughometer:
        if hubs_layer.fields().indexOf('Sta') == -1:
            QMessageBox.warning(
                None,
                "Error",
                "Field 'Sta' not found in layer '{}'!\n"
                "Available fields: {}".format(
                    hubs_layer.name(),
                    ', '.join([f.name() for f in hubs_layer.fields()])
                )
            )
            print("[ERROR] Field 'Sta' tidak ada di hubs layer.")
            return None
        hub_field = 'Sta'
    else:
        hub_field = find_field_contains(hubs_layer, 'stopdistance')
        if hub_field is None:
            QMessageBox.warning(
                None,
                "Error",
                "Field 'Stop distance' not found in layer '{}'!\n"
                "Available fields: {}".format(
                    hubs_layer.name(),
                    ', '.join([f.name() for f in hubs_layer.fields()])
                )
            )
            print("[ERROR] Field 'Stop distance' tidak ada di hubs layer.")
            return None
    
    # Jalankan processing line-to-hub
    hub_layer = run_distance_to_nearest_hub(src_layer, hubs_layer, hub_field)
    if hub_layer is None:
        return None
    
    # Export ke CSV (NearHub_L2.csv / NearHub_R1.csv / dst)
    # Dialog dibuka di folder file CSV yang di-import
    csv_path = export_nearhub_csv(hub_layer, hubs_layer, os.path.dirname(filepath))
    if csv_path is None:
        return None
    
    # -------------------------------------------------------
    # STYLING LAYER REFERENSI (setelah export)
    #   - Simbol  : #ff8800, size 2
    #   - Label   : single label "TO_STA (km)", font 10
    # -------------------------------------------------------
    print("\n[STYLE REFERENSI] Mengatur styling layer '{}'...".format(src_layer.name()))
    
    # Simbol: orange #ff8800, size 2
    ref_symbol = QgsMarkerSymbol.createSimple({
        'name': 'circle',
        'color': '#ff8800',
        'outline_color': '0,0,0,255',
        'outline_width': '0',
        'size': '2'
    })
    src_layer.setRenderer(QgsSingleSymbolRenderer(ref_symbol))
    ref_context = QgsRenderContext.fromMapSettings(iface.mapCanvas().mapSettings())
    src_layer.renderer().startRender(ref_context, src_layer.fields())
    src_layer.renderer().stopRender(ref_context)
    src_layer.triggerRepaint()
    print("  Simbol: circle, orange #ff8800, size 2")
    
    # Label "TO_STA (km)": cari nama field asli via normalisasi
    to_sta_field = None
    for f in src_layer.fields():
        fn = f.name().lower().replace(' ', '').replace('_', '').replace('-', '')
        if 'tosta(km)' in fn:
            to_sta_field = f.name()
            break
    
    if to_sta_field is None:
        QMessageBox.warning(
            None,
            "Warning",
            "Field 'TO_STA (km)' not found in layer '{}'!\n"
            "Symbol color is still set to orange #ff8800, but labeling was skipped.\n\n"
            "Available fields: {}".format(
                src_layer.name(),
                ', '.join([f.name() for f in src_layer.fields()])
            )
        )
        print("[WARN] Field 'TO_STA (km)' tidak ada di layer Referensi; label dilewati.")
    else:
        ref_label_settings = QgsPalLayerSettings()
        ref_label_settings.fieldName = to_sta_field
        ref_label_settings.enabled = True
        
        ref_text_format = QgsTextFormat()
        ref_font = QFont("Arial")
        ref_font.setPointSize(10)
        ref_text_format.setFont(ref_font)
        ref_text_format.setSize(10)
        ref_text_format.setColor(QColor(0, 0, 0))
        
        ref_buffer = QgsTextBufferSettings()
        ref_buffer.setEnabled(True)
        ref_buffer.setSize(0.5)
        ref_buffer.setColor(QColor(255, 255, 255))
        ref_text_format.setBuffer(ref_buffer)
        
        ref_label_settings.setFormat(ref_text_format)
        src_layer.setLabeling(QgsVectorLayerSimpleLabeling(ref_label_settings))
        src_layer.setLabelsEnabled(True)
        src_layer.triggerRepaint()
        print("  Label field: {} (font Arial 10pt)".format(to_sta_field))
    
    print("\n" + "=" * 60)
    print("  PROSES HUB & EXPORT SELESAI!")
    print("  CSV : {}".format(csv_path))
    print("=" * 60)

    # Silent log ke spreadsheet (status diambil dari print di atas)
    log_to_spreadsheet(csv_name, src_layer.name(), "PROSES HUB & EXPORT SELESAI!")

    QMessageBox.information(
        None,
        "Hub & Export Complete",
        "Distance to nearest hub completed!\n"
        "Layer 'Distance to Nearest Hub' added to QGIS.\n\n"
        "CSV saved to:\n{}".format(csv_path)
    )


# JALANKAN!
process_csv()
