import streamlit as st
import os
from src import database, utils

# --- PAGE CONFIG ---
st.set_page_config(page_title="Knowledge Base AI", page_icon="🧠", layout="centered")
st.markdown("""
<style>
    .stExpander { border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# --- LOAD DATA FOR FILTER ---
# REVISI: Filter berdasarkan data REAL di DB, bukan Config
# Config hanya dipakai untuk mapping warna
tags_config = utils.load_tags_config()

try:
    db_tags = database.get_unique_tags_from_db()
except Exception as e:
    db_tags = []

# Gabungkan logic:
# Kalau DB kosong (awal deploy), pakai list dari config biar gak kopong banget dropdown-nya
if not db_tags:
    filter_options = sorted(list(tags_config.keys()))
else:
    filter_options = db_tags

all_tags = ["Semua Modul"] + filter_options

# --- HEADER ---
st.title("🧠 Knowledge Base AI")
st.caption("Tanya apa saja terkait prosedur & kendala.")

# Filter UI
col_s, col_f = st.columns([3, 1])
with col_s:
    query = st.text_input("Cari...", placeholder="Contoh: Cara cuti melahirkan...")
with col_f:
    selected_tag = st.selectbox("Filter", all_tags)

st.divider()

# --- LOGIC PENCARIAN ---
results = []

if query:
    # Panggil Backend Search (Pre-filtered)
    raw_res = database.search_faq(query, selected_tag, n_results=3)
    
    if raw_res['ids'][0]:
        for i in range(len(raw_res['ids'][0])):
            meta = raw_res['metadatas'][0][i]
            results.append(meta)
            
else:
    # Default View (Ambil data random/terbaru jika kosong)
    # Untuk simpel, kita tidak load all dulu biar ringan
    st.info("👋 Silakan ketik pertanyaan atau pilih Filter.")

# --- DISPLAY RESULTS ---
if query and not results:
    st.warning(f"❌ Tidak ditemukan hasil untuk '{query}' di kategori {selected_tag}.")

for item in results:
    # Logic Warna: Ambil dari config.
    # Kalau tag di DB gak ada di config (misal udah dihapus admin), default ke abu-abu
    tag_data = tags_config.get(item['tag'], "#808080")
    
    # Handle struktur baru (Dict vs String)
    if isinstance(tag_data, dict):
        tag_color = tag_data.get("color", "#808080")
    else:
        tag_color = tag_data

    # HTML Badge Trick
    badge_html = f"<span style='background-color:{tag_color};color:white;padding:3px 8px;border-radius:4px;font-size:12px;'>{item['tag']}</span>"
    
    with st.expander(label="Hasil Pencarian", expanded=True):
        st.markdown(f"### {badge_html} {item['judul']}", unsafe_allow_html=True)
        st.markdown(item['jawaban_tampil'])
        st.markdown("---")
        
        # IMAGE HANDLING (Sorted)
        raw_imgs = item.get('path_gambar', 'none')
        if raw_imgs and raw_imgs != 'none':
            img_list = raw_imgs.split(';')
            img_list.sort() # <--- Fitur Sort Gambar
            
            for img_path in img_list:
                real_path = utils.fix_image_path_for_ui(img_path)
                if real_path and os.path.exists(real_path):
                    st.image(real_path, width='stretch')
        
        # Source Link
        url = item.get('sumber_url', '')
        if url and len(url) > 3:
            st.link_button("🔗 Sumber Referensi", url)