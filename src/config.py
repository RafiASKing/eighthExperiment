import os

# --- API KEYS ---
# JANGAN TULIS KEY LANGSUNG DISINI!
# Ambil dari environment variable (file .env)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 

# Jika lupa set env, kasih error biar sadar
if not GOOGLE_API_KEY:
    raise ValueError("❌ GOOGLE_API_KEY belum diset! Cek file .env atau environment server.")

# --- PATHS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "faq_db")
TAGS_FILE = os.path.join(BASE_DIR, "data", "tags_config.json")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
COLLECTION_NAME = "faq_emr_v2"

# --- SETUP FOLDERS ---
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)