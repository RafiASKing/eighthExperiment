import os
import json
import re
import random
import string
import time
import csv
from datetime import datetime
from PIL import Image
from .config import TAGS_FILE, IMAGES_DIR, BASE_DIR 

# --- DAFTAR WARNA RESMI STREAMLIT (Restricted Palette) ---
# Admin hanya boleh memilih warna ini agar badge di UI User valid
COLOR_PALETTE = {
    "Merah":            {"hex": "#FF4B4B", "name": "red"},
    "Hijau":            {"hex": "#2ECC71", "name": "green"},
    "Biru":             {"hex": "#3498DB", "name": "blue"},
    "Orange":           {"hex": "#FFA500", "name": "orange"},
    "Ungu":             {"hex": "#9B59B6", "name": "violet"},
    "Abu-abu":          {"hex": "#808080", "name": "gray"},
    "Pelangi (Special)":{"hex": "#333333", "name": "rainbow"}
}

# --- 1. JSON TAG CONFIG ---
def load_tags_config():
    if not os.path.exists(TAGS_FILE):
        # Default struktur (Nested Dict)
        default_tags = {
            "ED": {"color": "#FF4B4B", "desc": "IGD, Emergency, Triage, Ambulans"},
            "OPD": {"color": "#2ECC71", "desc": "Rawat Jalan, Poli, Dokter Spesialis"},
            "IPD": {"color": "#3498DB", "desc": "Rawat Inap, Bangsal, Bed, Visite"},
            "Umum": {"color": "#808080", "desc": "General Info, IT Support"}
        }
        save_tags_config(default_tags)
        return default_tags
    with open(TAGS_FILE, "r") as f:
        return json.load(f)

def save_tags_config(tags_dict):
    with open(TAGS_FILE, "w") as f:
        json.dump(tags_dict, f, indent=4)

# --- 2. SAFE ID GENERATOR ---
def get_next_id_safe(collection):
    try:
        data = collection.get(include=[])
        existing_ids = data['ids']
        if not existing_ids: return "1"
        
        # Filter hanya ID angka agar sorting benar
        numeric_ids = []
        for x in existing_ids:
            if x.isdigit():
                numeric_ids.append(int(x))
        
        if not numeric_ids: return "1"
        return str(max(numeric_ids) + 1)
    except Exception:
        return str(int(time.time()))

# --- 3. IMAGE HANDLING ---
def sanitize_filename(text):
    # Membersihkan nama file dari karakter aneh
    return re.sub(r'[^\w\-_]', '', text.replace(" ", "_"))[:30]

def save_uploaded_images(uploaded_files, judul, tag):
    if not uploaded_files: return "none"
    
    saved_paths = []
    clean_judul = sanitize_filename(judul)
    target_dir = os.path.join(IMAGES_DIR, tag)
    os.makedirs(target_dir, exist_ok=True)

    resample_module = getattr(Image, "Resampling", None)
    resample_method = resample_module.LANCZOS if resample_module else getattr(Image, "LANCZOS", Image.BICUBIC)
    max_width = 1024
    quality = 70
    
    for i, file in enumerate(uploaded_files):
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        filename = f"{clean_judul}_{tag}_{i+1}_{suffix}.jpg"
        full_path = os.path.join(target_dir, filename)

        try:
            if hasattr(file, "seek"):
                file.seek(0)
            image = Image.open(file)
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")

            if image.width > max_width:
                ratio = max_width / float(image.width)
                new_height = int(float(image.height) * ratio)
                image = image.resize((max_width, new_height), resample_method)

            image.save(full_path, "JPEG", quality=quality, optimize=True)
        except Exception as e:
            print(f"⚠️ Gagal compress gambar {file.name}: {e}")
            if hasattr(file, "seek"):
                file.seek(0)
            with open(full_path, "wb") as f:
                f.write(file.getbuffer())
        finally:
            if hasattr(file, "seek"):
                file.seek(0)
        
        rel_path = f"./images/{tag}/{filename}"
        saved_paths.append(rel_path)
        
    return ";".join(saved_paths)

def fix_image_path_for_ui(db_path):
    clean = str(db_path).strip('"').strip("'")
    if clean.lower() == "none": return None
    clean = clean.replace("\\", "/")
    if clean.startswith("./"):
        return clean 
    return clean

# --- 4. TEXT CLEANING FOR AI ---
def clean_text_for_embedding(text):
    """
    Menghapus tag [GAMBAR X] agar tidak menjadi noise bagi AI.
    Tapi MEMPERTAHANKAN markdown seperti **bold** atau list.
    Contoh: "Klik [GAMBAR 1] tombol save" -> "Klik tombol save"
    """
    if not text: return ""
    # Hapus pattern [GAMBAR angka] case insensitive
    clean = re.sub(r'\[GAMBAR\s*\d+\]', '', text, flags=re.IGNORECASE)
    # Hapus whitespace berlebih akibat penghapusan tadi
    return " ".join(clean.split())

def log_failed_search(query):
    """Mencatat pencarian yang hasilnya 0 ke file CSV"""
    filename = os.path.join(BASE_DIR, "data", "failed_searches.csv")
    
    # Cek header kalau file baru
    file_exists = os.path.exists(filename)
    
    try:
        with open(filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Query User"]) # Header
            
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), query])
    except Exception as e:
        print(f"Gagal mencatat log: {e}")