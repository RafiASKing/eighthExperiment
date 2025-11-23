import os
import json
import re
import random
import string
from .config import TAGS_FILE, IMAGES_DIR

# --- DAFTAR WARNA RESMI STREAMLIT (Palette Restricted) ---
# Format: "Label Dropdown": {"hex": "#HEXCODE", "name": "nama_streamlit"}
COLOR_PALETTE = {
    "Merah (Emergency/ED/HR)": {"hex": "#FF4B4B", "name": "red"},
    "Hijau (OPD/Poli/BPJS)":   {"hex": "#2ECC71", "name": "green"},
    "Biru (IPD/Ranap/MR)":     {"hex": "#3498DB", "name": "blue"},
    "Orange (Cashier/Radio)":  {"hex": "#FFA500", "name": "orange"},
    "Ungu (Mungkin Farmasi)":  {"hex": "#9B59B6", "name": "violet"},
    "Abu-abu (IT/Umum)":       {"hex": "#808080", "name": "gray"},
    "Pelangi (Special)":       {"hex": "#333333", "name": "rainbow"}
}

# --- 1. JSON TAG CONFIG ---
def load_tags_config():
    if not os.path.exists(TAGS_FILE):
        # Default struktur baru
        default_tags = {
            "ED": {"color": "#FF4B4B", "desc": "IGD, Emergency, Triage"},
            "OPD": {"color": "#2ECC71", "desc": "Rawat Jalan, Poli, Dokter"},
            "IPD": {"color": "#3498DB", "desc": "Rawat Inap, Bangsal, Bed"}
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
        import time
        return str(int(time.time()))

# --- 3. IMAGE HANDLING ---
def sanitize_filename(text):
    return re.sub(r'[^\w\-_]', '', text.replace(" ", "_"))[:30]

def save_uploaded_images(uploaded_files, judul, tag):
    if not uploaded_files: return "none"
    
    saved_paths = []
    clean_judul = sanitize_filename(judul)
    target_dir = os.path.join(IMAGES_DIR, tag)
    os.makedirs(target_dir, exist_ok=True)
    
    for i, file in enumerate(uploaded_files):
        ext = file.name.split('.')[-1]
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        
        filename = f"{clean_judul}_{tag}_{i+1}_{suffix}.{ext}"
        full_path = os.path.join(target_dir, filename)
        
        with open(full_path, "wb") as f:
            f.write(file.getbuffer())
            
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