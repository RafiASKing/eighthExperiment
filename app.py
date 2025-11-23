import streamlit as st
import os
import math
from src import database, utils

# --- PAGE CONFIG ---
st.set_page_config(page_title="Knowledge Base AI", page_icon="🧠", layout="centered")

# CSS Custom untuk Expander
st.markdown("""
<style>
    .stExpander {
        border: 1px solid #e0e0e0; border-radius: 6px;
        margin-bottom: 8px; background-color: white;
    }
    .stExpander p { font-size: 16px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# --- HELPER: WARNA BADGE (REVERSE LOOKUP) ---
def get_badge_syntax(tag_name):
    tags_cfg = utils.load_tags_config()
    tag_data = tags_cfg.get(tag_name, {})
    
    # Ambil HEX (Fallback ke gray)
    if isinstance(tag_data, dict):
        hex_color = tag_data.get("color", "#808080")
    else:
        hex_color = str(tag_data) 

    # Cari Nama Warna Streamlit dari Palette
    st_color_name = "gray"
    for label, palette_data in utils.COLOR_PALETTE.items():
        if palette_data["hex"].lower() == hex_color.lower():
            st_color_name = palette_data["name"]
            break
            
    return f":{st_color_name}-background[{tag_name}]"

# --- STATE MANAGEMENT ---
if 'page' not in st.session_state: st.session_state.page = 0
if 'last_query' not in st.session_state: st.session_state.last_query = ""
if 'last_filter' not in st.session_state: st.session_state.last_filter = ""

# --- LOAD FILTERS ---
try: db_tags = database.get_unique_tags_from_db()
except: db_tags = []
all_tags = ["Semua Modul"] + (db_tags if db_tags else ["Umum"])

# --- UI HEADER ---
st.title("🧠 Knowledge Base AI")

col_s, col_f = st.columns([3, 1])
with col_s:
    query = st.text_input("Cari Kendala...", placeholder="Ketik masalah atau kode error...")
with col_f:
    selected_tag = st.selectbox("Filter", all_tags)

st.divider()

# Reset Page jika filter/query berubah
if query != st.session_state.last_query or selected_tag != st.session_state.last_filter:
    st.session_state.page = 0
    st.session_state.last_query = query
    st.session_state.last_filter = selected_tag

# --- FETCH DATA ---
all_results = []
is_search_mode = False

if query:
    is_search_mode = True
    raw_res = database.search_faq(query, selected_tag, n_results=50)
    if raw_res['ids'][0]:
        for i in range(len(raw_res['ids'][0])):
            all_results.append(raw_res['metadatas'][0][i])
else:
    raw_all = database.get_all_faqs_sorted()
    if selected_tag != "Semua Modul":
        all_results = [x for x in raw_all if x['tag'] == selected_tag]
    else:
        all_results = raw_all

# --- PAGINATION LOGIC ---
ITEMS_PER_PAGE = 10
total_items = len(all_results)
total_pages = math.ceil(total_items / ITEMS_PER_PAGE)

if total_pages > 0 and st.session_state.page >= total_pages: 
    st.session_state.page = 0 

start_idx = st.session_state.page * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
current_page_data = all_results[start_idx:end_idx]

# --- DISPLAY DATA ---
if not current_page_data:
    if is_search_mode:
        st.warning(f"❌ Tidak ditemukan hasil untuk '{query}'.")
    else:
        st.info("📭 Database kosong.")
else:
    st.caption(f"Menampilkan **{start_idx + 1}-{min(end_idx, total_items)}** dari **{total_items}** data.")

    for item in current_page_data:
        badge = get_badge_syntax(item.get('tag', 'Umum'))
        judul = item.get('judul', '(Tanpa Judul)')
        header_text = f"{badge} **{judul}**"
        
        with st.expander(label=header_text, expanded=False):
            st.markdown(item.get('jawaban_tampil', '-'))
            
            raw_imgs = item.get('path_gambar', 'none')
            if raw_imgs and str(raw_imgs).lower() != 'none':
                st.markdown("---")
                for img_path in raw_imgs.split(';'):
                    real_path = utils.fix_image_path_for_ui(img_path)
                    if real_path and os.path.exists(real_path):
                        st.image(real_path, use_container_width=True)
            
            src_url = item.get('sumber_url', '')
            if src_url and len(str(src_url)) > 3:
                st.markdown(f"<br>🔗 [Buka Referensi]({src_url})", unsafe_allow_html=True)

    # --- NAVIGATION BUTTONS ---
    if total_pages > 1:
        st.markdown("---")
        c_p, c_i, c_n = st.columns([1, 2, 1])
        if c_p.button("⬅️ Sebelumnya", use_container_width=True) and st.session_state.page > 0:
            st.session_state.page -= 1
            st.rerun()
        
        c_i.markdown(f"<div style='text-align:center;color:grey;padding-top:5px'>Hal <b>{st.session_state.page + 1}</b> / {total_pages}</div>", unsafe_allow_html=True)
        
        if c_n.button("Berikutnya ➡️", use_container_width=True) and st.session_state.page < total_pages - 1:
            st.session_state.page += 1
            st.rerun()