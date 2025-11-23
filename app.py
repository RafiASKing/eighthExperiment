import streamlit as st
import os
import math
from src import database, utils

# --- PAGE CONFIG ---
st.set_page_config(page_title="Knowledge Base AI", page_icon="🧠", layout="centered")

# --- CSS CUSTOMIZATION ---
# Membuat tampilan Expander lebih rapi dan Badge terlihat jelas
st.markdown("""
<style>
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        margin-bottom: 8px;
        background-color: white;
    }
    /* Font Judul di Header Expander */
    .stExpander p {
        font-size: 16px;
        font-weight: 500;
    }
    /* Link Style */
    a { text-decoration: none; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- HELPER: WARNA BADGE (REVERSE LOOKUP) ---
# Mencocokkan HEX dari Config dengan Nama Warna Streamlit di Palette
def get_badge_syntax(tag_name):
    tags_cfg = utils.load_tags_config()
    tag_data = tags_cfg.get(tag_name, {})
    
    # 1. Ambil HEX Code (Fallback ke gray jika error)
    if isinstance(tag_data, dict):
        hex_color = tag_data.get("color", "#808080")
    else:
        hex_color = str(tag_data) 

    # 2. Cari Nama Warna Streamlit (red, green, etc) dari Palette Utils
    st_color_name = "gray"
    for label, palette_data in utils.COLOR_PALETTE.items():
        if palette_data["hex"].lower() == hex_color.lower():
            st_color_name = palette_data["name"]
            break
            
    return f":{st_color_name}-background[{tag_name}]"

# --- STATE MANAGEMENT (PAGINATION) ---
if 'page' not in st.session_state: st.session_state.page = 0
if 'last_query' not in st.session_state: st.session_state.last_query = ""
if 'last_filter' not in st.session_state: st.session_state.last_filter = ""

# --- LOAD FILTERS ---
# Mengambil Tag yang BENAR-BENAR ada di Database agar filter tidak zonk
try: 
    db_tags = database.get_unique_tags_from_db()
except: 
    db_tags = []

all_tags = ["Semua Modul"] + (db_tags if db_tags else ["Umum"])

# --- UI HEADER ---
st.title("🧠 Knowledge Base AI")

col_s, col_f = st.columns([3, 1])
with col_s:
    # Placeholder yang memancing user
    query = st.text_input("Cari Kendala...", placeholder="Contoh: Cara retur obat, Error 505...")
with col_f:
    selected_tag = st.selectbox("Filter", all_tags)

st.divider()

# --- LOGIC RESET PAGE ---
# Jika user mengubah query atau filter, reset halaman ke 0 (awal)
if query != st.session_state.last_query or selected_tag != st.session_state.last_filter:
    st.session_state.page = 0
    st.session_state.last_query = query
    st.session_state.last_filter = selected_tag

# --- FETCH DATA ENGINE ---
all_results = []
is_search_mode = False

if query:
    # === MODE 1: SEARCHING (AI POWERED) ===
    is_search_mode = True
    # Ambil Top 50 agar pagination berjalan mulus
    raw_res = database.search_faq(query, selected_tag, n_results=50)
    
    if raw_res['ids'][0]:
        for i in range(len(raw_res['ids'][0])):
            item = raw_res['metadatas'][0][i]
            
            # --- WOW FACTOR: CONFIDENCE SCORE CALCULATION ---
            # ChromaDB mengembalikan 'distance'. Semakin kecil = Semakin mirip.
            # Rumus Simple: (1 - distance) * 100
            # Note: Distance cosine range biasanya 0 - 1 (untuk normalized vector)
            dist = raw_res['distances'][0][i]
            score_pct = max(0, (1 - dist) * 100) 
            
            item['score'] = score_pct # Simpan score untuk ditampilkan
            all_results.append(item)
else:
    # === MODE 2: BROWSING (CHRONOLOGICAL) ===
    # Ambil semua data, urut dari ID terbaru
    raw_all = database.get_all_faqs_sorted()
    
    if selected_tag != "Semua Modul":
        all_results = [x for x in raw_all if x['tag'] == selected_tag]
    else:
        all_results = raw_all
        
    # Di mode browse, kita tidak menampilkan score karena tidak ada pembanding
    for item in all_results:
        item['score'] = None

# --- PAGINATION LOGIC ---
ITEMS_PER_PAGE = 10
total_items = len(all_results)
total_pages = math.ceil(total_items / ITEMS_PER_PAGE)

# Safety Check: Cegah error index jika data berubah tiba-tiba
if total_pages > 0 and st.session_state.page >= total_pages: 
    st.session_state.page = 0 

start_idx = st.session_state.page * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE

# Slice data untuk halaman ini saja
current_page_data = all_results[start_idx:end_idx]

# --- DISPLAY DATA (CARD LOOP) ---
if not current_page_data:
    if is_search_mode:
        st.warning(f"❌ Tidak ditemukan hasil untuk '{query}' di kategori {selected_tag}.")
    else:
        st.info("📭 Database kosong. Silakan input data di Admin Console.")
else:
    # Info Caption
    st.caption(f"Menampilkan **{start_idx + 1}-{min(end_idx, total_items)}** dari total **{total_items}** data.")

    for item in current_page_data:
        # 1. Siapkan Elemen Header
        badge = get_badge_syntax(item.get('tag', 'Umum'))
        judul = item.get('judul', '(Tanpa Judul)')
        
        # 2. Logic Tampilan Score (Hanya muncul saat Search)
        score_display = ""
        if item.get('score') is not None:
            val = item['score']
            # Warna Score berdasarkan tingkat kemiripan
            if val >= 85: sc_color = "green"
            elif val >= 70: sc_color = "orange"
            else: sc_color = "red"
            
            score_display = f" :{sc_color}[({val:.0f}% Match)]"

        # 3. Render Header Expander
        header_text = f"{badge} **{judul}**{score_display}"
        
        with st.expander(label=header_text, expanded=False):
            # A. Jawaban Markdown
            st.markdown(item.get('jawaban_tampil', '-'))
            
            # B. Image Handling (Grid / List)
            raw_imgs = item.get('path_gambar', 'none')
            if raw_imgs and str(raw_imgs).lower() != 'none':
                st.markdown("---")
                img_list = raw_imgs.split(';')
                for img_path in img_list:
                    real_path = utils.fix_image_path_for_ui(img_path)
                    if real_path and os.path.exists(real_path):
                        # use_container_width agar responsif di HP/Desktop
                        st.image(real_path, use_container_width=True)
            
            # C. Source Link
            src_url = item.get('sumber_url', '')
            if src_url and len(str(src_url)) > 3:
                st.markdown(f"<br>🔗 [Buka Referensi Asli]({src_url})", unsafe_allow_html=True)

    # --- NAVIGATION BUTTONS ---
    if total_pages > 1:
        st.markdown("---")
        c_prev, c_info, c_next = st.columns([1, 2, 1])
        
        # Tombol Previous
        with c_prev:
            if st.session_state.page > 0:
                if st.button("⬅️ Sebelumnya", use_container_width=True):
                    st.session_state.page -= 1
                    st.rerun()
        
        # Info Halaman Tengah
        with c_info:
            st.markdown(
                f"<div style='text-align:center; color:grey; padding-top:5px;'>"
                f"Halaman <b>{st.session_state.page + 1}</b> dari {total_pages}</div>", 
                unsafe_allow_html=True
            )
            
        # Tombol Next
        with c_next:
            if st.session_state.page < total_pages - 1:
                if st.button("Berikutnya ➡️", use_container_width=True):
                    st.session_state.page += 1
                    st.rerun()