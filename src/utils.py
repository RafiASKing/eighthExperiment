import os
import json
import time
import re
import random
import string
from .config import TAGS_FILE, IMAGES_DIR

# --- 1. JSON TAG CONFIG ---
# Struktur JSON yang disarankan:
# { "NamaTag": { "color": "#Hex", "desc": "Sinonim/Context" } }

def load_tags_config():
    if not os.path.exists(TAGS_FILE):
        # Default Struktur BARU (Nested Dict)
        default_tags = {
            "ED": {"color": "#FF4B4B", "desc": "IGD, Emergency"},
            "OPD": {"color": "#2ECC71", "desc": "Rawat Jalan, Poli"},
            "General": {"color": "#7F8C8D", "desc": "Umum"}
        }
        save_tags_config(default_tags)
        return default_tags
        
    with open(TAGS_FILE, "r") as f:
        return json.load(f)

def save_tags_config(tags_dict):
    with open(TAGS_FILE, "w") as f:
        json.dump(tags_dict, f, indent=4)

# --- 2. SAFE ID GENERATOR (Max + 1) ---
def get_next_id_safe(collection):
    try:
        data = collection.get(include=[])
        existing_ids = data['ids']
        if not existing_ids: return "1"
        
        numeric_ids = [int(x) for x in existing_ids if x.isdigit()]
        if not numeric_ids: return "1"
        
        return str(max(numeric_ids) + 1)
    except Exception as e:
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
    
    # Sorting file upload (best effort)
    # Note: Streamlit file uploader return list, kita percaya urutan user/OS
    for i, file in enumerate(uploaded_files):
        ext = file.name.split('.')[-1]
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        
        # Naming convention: judul_tag_urutan_random.ext
        filename = f"{clean_judul}_{tag}_{i+1}_{suffix}.{ext}"
        full_path = os.path.join(target_dir, filename)
        
        with open(full_path, "wb") as f:
            f.write(file.getbuffer())
            
        # Simpan relative path agar portable
        rel_path = f"./images/{tag}/{filename}"
        saved_paths.append(rel_path)
        
    return ";".join(saved_paths)

def fix_image_path_for_ui(db_path):
    """Mengubah path database string menjadi path lokal yang bisa dibaca Streamlit"""
    clean = str(db_path).strip('"').strip("'")
    if clean.lower() == "none": return None
    
    # Normalisasi path windows/linux
    clean = clean.replace("\\", "/")
    
    # Logic untuk mencari file relatif terhadap app.py
    if clean.startswith("./"):
        return clean # Sudah relative
    return clean