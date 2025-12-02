import os
from dotenv import load_dotenv

# Load environment variables dari file .env
load_dotenv()

# --- API KEYS & AUTH ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "admin")

if not GOOGLE_API_KEY:
    raise ValueError("❌ GOOGLE_API_KEY belum diset! Cek file .env.")

# --- PATHS CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "faq_db")
TAGS_FILE = os.path.join(BASE_DIR, "data", "tags_config.json")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
FAILED_SEARCH_LOG = os.path.join(BASE_DIR, "data", "failed_searches.csv")
COLLECTION_NAME = "faq_universal_v1"

# Setup Folder
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# --- BOT LOGIC CONFIGURATION (NEW) ---
# Mengambil nilai dari .env, default ke 80.0 dan 10.0 jika tidak ada
try:
    BOT_MIN_SCORE = float(os.getenv("BOT_MIN_SCORE", "80.0"))
    BOT_MIN_GAP = float(os.getenv("BOT_MIN_GAP", "10.0"))
except ValueError:
    print("⚠️ Format angka di .env salah, menggunakan default (80.0 & 10.0)")
    BOT_MIN_SCORE = 80.0
    BOT_MIN_GAP = 10.0