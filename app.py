import streamlit as st
import os
import math
import re
import warnings
from src import database, utils

# --- 1. CONFIG & SUPPRESS WARNINGS ---
st.set_page_config(page_title="Siloam Knowledge Base", page_icon="🏥", layout="centered")

# Matikan warning deprecation
# (Kode lama dihapus karena sudah tidak supported di Streamlit baru)
warnings.filterwarnings("ignore")

# Load Konfigurasi Tag dari JSON (Single Source of Truth)
TAGS_MAP = utils.load_tags_config()

# CSS Styling
st.markdown("""
<style>
    div[data-testid="stExpander"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        background-color: white;
        margin-bottom: 10px;
    }
    div[data-testid="stExpander"] p {
        font-size: 15px;
        font-family: sans-serif;
    }
    .stApp {
        background-color: #FAFAFA;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. HELPER FUNGSI ---

def get_badge_color_name(tag):
    """
    Menerjemahkan HEX Code dari tags_config.json menjadi Nama Warna Streamlit.
    """
    tag_data = TAGS_MAP.get(tag, {})
    hex_code = tag_data.get("color", "#808080").upper() 
    
    hex_to_name = {
        "#FF4B4B": "red",     # Merah (ED)
        "#2ECC71": "green",   # Hijau (OPD)
        "#3498DB": "blue",    # Biru (IPD/MR/Rehab)
        "#FFA500": "orange",  # Orange (Cashier)
        "#9B59B6": "violet",  # Ungu (Farmasi)
        "#808080": "gray",    # Abu (Umum)
        "#333333": "gray"     # Dark Gray
    }
    
    return hex_to_name.get(hex_code, "gray")

def render_image_safe(image_path):
    if image_path and os.path.exists(image_path):
        st.image(image_path, use_container_width=True)

def render_mixed_content(jawaban_text, images_str):
    if not images_str or str(images_str).lower() == 'none':
        st.markdown(jawaban_text)
        return

    img_list = images_str.split(';')
    img_list = [x for x in img_list if x.strip()]
    parts = re.split(r'(\[GAMBAR\s*\d+\])', jawaban_text, flags=re.IGNORECASE)
    
    # Case 1: Fallback (Gambar di bawah)
    if len(parts) == 1:
        st.markdown(jawaban_text)
        if img_list:
            st.markdown("---")
            cols = st.columns(min(3, len(img_list)))
            for idx, p in enumerate(img_list):
                clean_p = utils.fix_image_path_for_ui(p)
                if clean_p and os.path.exists(clean_p):
                    with cols[idx % 3]:
                        st.image(clean_p, use_container_width=True)
        return

    # Case 2: Inline (Diselipkan)
    for part in parts:
        match = re.search(r'\[GAMBAR\s*(\d+)\]', part, re.IGNORECASE)
        if match:
            try:
                idx = int(match.group(1)) - 1 
                if 0 <= idx < len(img_list):
                    clean_p = utils.fix_image_path_for_ui(img_list[idx])
                    if clean_p and os.path.exists(clean_p):
                        render_image_safe(clean_p)
                    else:
                        st.error(f"🖼️ File gambar tidak ditemukan: {clean_p}")
                else:
                    st.caption(f"*(Gambar #{idx+1} tidak tersedia)*")
            except ValueError: pass
        else:
            if part.strip(): st.markdown(part)

# --- 3. STATE MANAGEMENT ---
if 'page' not in st.session_state: st.session_state.page = 0
if 'last_query' not in st.session_state: st.session_state.last_query = ""
if 'last_filter' not in st.session_state: st.session_state.last_filter = ""

# --- 4. HEADER UI ---
st.title("⚡Fast Cognitive Search System")
st.caption("Smart Knowledge Base Retrieval")

col_q, col_f = st.columns([3, 1])
with col_q:
    query = st.text_input("Cari isu/kendala:", placeholder="Ketik masalah (cth: Kenapa Gagal Retur Obat, gagal discharge)...")
with col_f:
    # Ambil tag unik dari DB agar dropdown dinamis
    try:
        db_tags = database.get_unique_tags_from_db()
    except:
        db_tags = []
    all_tags = ["Semua Modul"] + (db_tags if db_tags else [])
    filter_tag = st.selectbox("Filter:", all_tags)

# --- 5. LOGIC PENCARIAN ---
if query != st.session_state.last_query or filter_tag != st.session_state.last_filter:
    st.session_state.page = 0
    st.session_state.last_query = query
    st.session_state.last_filter = filter_tag

results = []
is_search_mode = False

if query:
    is_search_mode = True
    raw = database.search_faq(query, filter_tag, n_results=50)
    
    if raw['ids'][0]:
        for i in range(len(raw['ids'][0])):
            meta = raw['metadatas'][0][i]
            dist = raw['distances'][0][i]
            score = max(0, (1 - dist) * 100)
            
            # === THRESHOLD 32% ===
            if score > 32:
                meta['score'] = score
                results.append(meta)
else:
    raw_all = database.get_all_faqs_sorted()
    if filter_tag == "Semua Modul":
        results = raw_all
    else:
        results = [x for x in raw_all if x.get('tag') == filter_tag]

# --- 6. PAGINATION & DISPLAY ---
ITEMS_PER_PAGE = 10
total_docs = len(results)
total_pages = math.ceil(total_docs / ITEMS_PER_PAGE)

if st.session_state.page >= total_pages and total_pages > 0:
    st.session_state.page = 0

start_idx = st.session_state.page * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
page_data = results[start_idx:end_idx]

st.divider()

if not page_data:
    if is_search_mode:
        # Catat query gagal ke CSV
        try: utils.log_failed_search(query)
        except: pass
        
        # === CALL TO ACTION (WA BOT) ===
        st.warning(f"❌ Tidak ditemukan hasil yang relevan (Relevansi < 32%).")
        
        st.markdown("""
        ### 🧐 Belum ada solusinya?
        Sistem telah mencatat pencarianmu untuk perbaikan. Sementara itu, kamu bisa:
        
        1. Coba gunakan kata kunci yang lebih umum.
        2. Atau langsung request bantuan ke Tim IT Support:
        """)
        
        # GANTI NOMOR WA DI SINI (Format: 628xxx)
        wa_number = "6289635225253" 
        wa_text = f"Halo Admin, saya cari solusi tentang '{query}' tapi tidak ketemu di aplikasi FAQ."
        wa_link = f"https://wa.me/{wa_number}?text={wa_text.replace(' ', '%20')}"
        
        st.markdown(f'''
        <a href="{wa_link}" target="_blank" style="text-decoration: none;">
            <button style="
                background-color: #25D366; 
                color: white; 
                padding: 10px 20px; 
                border: none; 
                border-radius: 5px; 
                cursor: pointer;
                font-weight: bold;
                font-size: 16px;
                display: flex;
                align_items: center;
                gap: 8px;">
                📱 Chat WhatsApp Support
            </button>
        </a>
        ''', unsafe_allow_html=True)
        # ===============================
        
    else:
        st.info("👋 Selamat Datang. Database siap digunakan.")
else:
    st.markdown(f"**Menampilkan {start_idx+1}-{min(end_idx, total_docs)} dari {total_docs} data**")
    
    for item in page_data:
        # 1. Badge Warna
        tag = item.get('tag', 'Umum')
        badge_color = get_badge_color_name(tag)
        
        # 2. Indikator Relevansi
        score_md = ""
        if item.get('score'):
            sc = item['score']
            if sc > 75: sc_color = "green"
            elif sc > 50: sc_color = "orange"
            else: sc_color = "red"
            score_md = f":{sc_color}[({sc:.0f}% Relevansi)]"
            
        label = f":{badge_color}-background[{tag}] **{item.get('judul')}** {score_md}"
        
        with st.expander(label):
            render_mixed_content(item.get('jawaban_tampil', '-'), item.get('path_gambar'))
            if item.get('sumber_url') and len(str(item.get('sumber_url'))) > 3:
                st.markdown(f"🔗 [Sumber Referensi]({item.get('sumber_url')})")

    if total_pages > 1:
        st.markdown("---")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.session_state.page > 0:
                if st.button("⬅️ Sebelumnya"):
                    st.session_state.page -= 1
                    st.rerun()
        with c3:
            if st.session_state.page < total_pages - 1:
                if st.button("Berikutnya ➡️"):
                    st.session_state.page += 1
                    st.rerun()