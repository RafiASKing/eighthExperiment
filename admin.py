import streamlit as st
import pandas as pd
import time
import re
from src import database, utils
from src.config import ADMIN_PASSWORD, FAILED_SEARCH_LOG

# --- AUTH SYSTEM ---
if 'auth' not in st.session_state: st.session_state.auth = False

def login():
    if st.session_state.pass_input == ADMIN_PASSWORD: 
        st.session_state.auth = True
    else:
        st.error("Password salah")

if not st.session_state.auth:
    st.set_page_config(page_title="Admin Login")
    st.markdown("<h1 style='text-align: center;'>🔒 Admin Login</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.text_input("Password", type="password", key="pass_input", on_change=login)
    st.stop()

# --- MAIN UI SETUP ---
st.set_page_config(page_title="Admin Console", layout="wide")
st.title("🛠️ Admin Console (Safe Mode)")
tags_map = utils.load_tags_config()

# State Management
if 'preview_mode' not in st.session_state: st.session_state.preview_mode = False
if 'draft_data' not in st.session_state: st.session_state.draft_data = {}

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Database", "➕ New FaQ", "✏️ Edit/Delete FaQ", "⚙️ Config Tags", "📈 Analytics"
])

# === TAB 1: LIST DATA ===
with tab1:
    if st.button("🔄 Refresh Data"):
        # CLEAR CACHE DISINI (MANUAL REFRESH)
        database.get_all_data_as_df.clear()
        st.rerun()
        
    df = database.get_all_data_as_df()
    st.dataframe(df, use_container_width=True, hide_index=True)

# === TAB 2: TAMBAH DATA (SMART EDITOR) ===
with tab2:
    # --- SMART CALLBACKS ---
    def add_text(text):
        """Menambahkan teks (Bold/List) ke akhir editor"""
        if 'in_a' in st.session_state:
            st.session_state.in_a += text

    def add_next_image_tag():
        """
        FITUR PINTAR (AUTO COUNTER):
        Otomatis scan teks, hitung jumlah tag [GAMBAR X], 
        lalu tambahkan [GAMBAR X+1].
        """
        current_text = st.session_state.get('in_a', "")
        matches = re.findall(r'\[GAMBAR\s*\d+\]', current_text, flags=re.IGNORECASE)
        next_num = len(matches) + 1
        
        tag_to_insert = f"\n\n[GAMBAR {next_num}]\n\n"
        st.session_state.in_a += tag_to_insert

    # --- PHASE 1: INPUT FORM ---
    if not st.session_state.preview_mode:
        # Load Draft (Anti-Amnesia Logic)
        default_tag = st.session_state.draft_data.get('tag', list(tags_map.keys())[0])
        default_judul = st.session_state.draft_data.get('judul', '')
        default_jawab = st.session_state.draft_data.get('jawab', '')
        default_key = st.session_state.draft_data.get('key', '')
        default_src = st.session_state.draft_data.get('src', '')
        
        try: idx_tag = list(tags_map.keys()).index(default_tag)
        except: idx_tag = 0

        st.subheader("📝 FaQ/SOP Baru")
        
        # Row 1: Module & Judul
        col_m, col_j = st.columns([1, 3])
        with col_m: i_tag = st.selectbox("Modul", list(tags_map.keys()), index=idx_tag, key="in_t")
        with col_j: i_judul = st.text_input("Judul Masalah (Pertanyaan/SOP)", value=default_judul, key="in_j")
            
        # Row 2: Smart Toolbar & Editor
        st.markdown("**Jawaban / Solusi:**")
        
        # Toolbar Layout
        tb1, tb2, tb3, tb_spacer = st.columns([1, 1, 2, 4])
        
        tb1.button("𝗕 Bold", on_click=add_text, args=(" **teks tebal** ",), 
                   help="Tebalkan teks", use_container_width=True)
        
        tb2.button("Bars", on_click=add_text, args=("\n- Langkah 1\n- Langkah 2",), 
                   help="Buat List", use_container_width=True)
        
        # Tombol Ajaib
        tb3.button("+ Klik ini untuk add penanda gambar", on_click=add_next_image_tag, 
                   type="primary", icon="🖼️", use_container_width=True,
                   help="Otomatis memasukkan tag [GAMBAR 1], [GAMBAR 2], dst.")

        # Text Area Utama
        i_jawab = st.text_area("Editor", value=default_jawab, height=300, key="in_a", label_visibility="collapsed")
        st.caption("💡 *Tips: Klik tombol '📸' untuk memasukkan placeholder gambar secara urut.*")
        
        # Row 3: Meta Info & Upload
        c_k, c_s = st.columns(2)
        with c_k: 
            st.markdown("Term terkait / Bahasa User (HyDE) 👇")
            i_key = st.text_input("Hidden Label", value=default_key, key="in_k", 
                                  placeholder="Contoh: Gabisa login, User not found, Kok gagal discharge?...",
                                  label_visibility="collapsed",
                                  help="Masukkan kata-kata yang mungkin diketik user saat panik.")
            
        with c_s: 
            st.markdown("Sumber Info/Source URL")
            i_src = st.text_input("Hidden Label 2", value=default_src, key="in_s", label_visibility="collapsed")
        
        i_imgs = st.file_uploader("Upload Gambar", accept_multiple_files=True, key="in_i")
        
        st.divider()
        if st.button("🔍 Lanjut ke Preview", type="primary", use_container_width=True):
            if not i_judul or not i_jawab:
                st.error("Judul & Jawaban wajib diisi!")
            else:
                # Simpan Draft ke Session State
                st.session_state.draft_data = {
                    "tag": i_tag, "judul": i_judul, "jawab": i_jawab,
                    "key": i_key, "src": i_src, "imgs": i_imgs
                }
                st.session_state.preview_mode = True
                st.rerun()

    # --- PHASE 2: PREVIEW & SUBMIT ---
    else:
        draft = st.session_state.draft_data
        
        st.info("📱 **Mode Preview:** Periksa tampilan sebelum Publish.")
        
        # Simulasi Tampilan User (Card)
        with st.container(border=True):
            hex_color = tags_map.get(draft['tag'], {}).get("color", "#808080")
            st.markdown(f"### <span style='color:{hex_color}'>[{draft['tag']}]</span> {draft['judul']}", unsafe_allow_html=True)
            st.caption(f"🔑 Keywords/HyDE: {draft['key']}")
            st.divider()
            
            # Logic Render Gambar Sederhana untuk Preview
            parts = re.split(r'(\[GAMBAR\s*\d+\])', draft['jawab'], flags=re.IGNORECASE)
            imgs = draft['imgs'] or []
            
            for part in parts:
                match = re.search(r'\[GAMBAR\s*(\d+)\]', part, re.IGNORECASE)
                if match:
                    try:
                        idx = int(match.group(1)) - 1
                        if 0 <= idx < len(imgs):
                            st.image(imgs[idx], width=400, caption=f"Gambar {idx+1}")
                        else:
                            st.warning(f"⚠️ [GAMBAR {idx+1}] ditulis tapi file belum diupload.")
                    except: pass
                else:
                    if part.strip(): st.markdown(part)
        
        st.divider()
        c_back, c_save = st.columns([1, 3])
        
        with c_back:
            if st.button("⬅️ Edit Lagi", use_container_width=True):
                st.session_state.preview_mode = False
                st.rerun()
        
        with c_save:
            if st.button("💾 PUBLISH KE DATABASE", type="primary", use_container_width=True):
                try:
                    with st.spinner("Menyimpan ke ChromaDB..."):
                        # 1. Simpan Gambar ke Disk
                        paths = utils.save_uploaded_images(draft['imgs'], draft['judul'], draft['tag'])
                        
                        # 2. Upsert ke DB
                        new_id = database.upsert_faq(
                            doc_id="auto",
                            tag=draft['tag'], 
                            judul=draft['judul'], 
                            jawaban=draft['jawab'], 
                            keyword=draft['key'], 
                            img_paths=paths, 
                            src_url=draft['src']
                        )
                        
                        st.balloons()
                        st.success(f"✅ Data Tersimpan! ID Dokumen: {new_id}")
                        
                        # === [1] CLEAR CACHE (WAJIB) ===
                        database.get_all_data_as_df.clear()
                        
                        # Reset
                        st.session_state.preview_mode = False
                        st.session_state.draft_data = {}
                        time.sleep(2)
                        st.rerun()
                except Exception as e: 
                    st.error(f"Error Save: {e}")

# === TAB 3: EDIT/HAPUS ===
with tab3:
    st.header("✏️ Edit Data Lama")
    df_e = database.get_all_data_as_df()
    
    if not df_e.empty:
        opts = [f"{r['ID']} | {r['Judul']}" for _, r in df_e.iterrows()]
        sel = st.selectbox("Pilih Data", opts)
        
        if sel:
            sel_id = sel.split(" | ")[0]
            row = df_e[df_e['ID'] == sel_id].iloc[0]
            
            with st.form("edit_form"):
                curr = row['Tag']
                idx = list(tags_map.keys()).index(curr) if curr in tags_map else 0
                
                c_id, c_t = st.columns([1, 4])
                with c_id: st.text_input("ID", value=sel_id, disabled=True)
                with c_t: e_tag = st.selectbox("Modul", list(tags_map.keys()), index=idx)
                
                e_jud = st.text_input("Judul SOP", value=row['Judul'])
                e_jaw = st.text_area("Jawaban (Gunakan [GAMBAR X])", value=row['Jawaban'], height=200)
                e_key = st.text_input("Keyword / Bahasa User (HyDE)", value=row['Keyword'], help="Isi dengan variasi pertanyaan user.")
                e_src = st.text_input("Source URL", value=row['Source'])
                
                st.markdown(f"**Path Gambar Saat Ini:** `{row['Gambar']}`")
                e_new = st.file_uploader("Timpa Gambar Baru (Opsional)", accept_multiple_files=True)
                
                c_up, c_del = st.columns([1, 1])
                
                if c_up.form_submit_button("💾 UPDATE DATA"):
                    p = row['Gambar']
                    if e_new: 
                        p = utils.save_uploaded_images(e_new, e_jud, e_tag)
                    
                    database.upsert_faq(sel_id, e_tag, e_jud, e_jaw, e_key, p, e_src)
                    st.toast("Data Updated!", icon="✅")
                    
                    # === [2] CLEAR CACHE (WAJIB) ===
                    database.get_all_data_as_df.clear()
                    
                    time.sleep(1)
                    st.rerun()
                
                if c_del.form_submit_button("🗑️ HAPUS PERMANEN", type="primary"):
                    database.delete_faq(sel_id)
                    st.toast("Data & Gambar Dihapus.", icon="🗑️")
                    
                    # === [3] CLEAR CACHE (WAJIB) ===
                    database.get_all_data_as_df.clear()
                    
                    time.sleep(1)
                    st.rerun()

# === TAB 4: CONFIG ===
with tab4:
    st.subheader("⚙️ Konfigurasi Tag")
    flat = [{"Tag":k, "Warna":v.get("color",""), "Sinonim":v.get("desc","")} for k,v in tags_map.items()]
    st.dataframe(pd.DataFrame(flat), use_container_width=True, hide_index=True)
    
    with st.expander("➕ Tambah / Update Tag"):
        with st.form("conf_f", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1: n_name = st.text_input("Nama Tag (ex: ED)")
            with c2: n_col = st.selectbox("Warna Badge", list(utils.COLOR_PALETTE.keys()))
            n_desc = st.text_input("Sinonim / Kepanjangan Singkatan", placeholder="ex: Emergency, Poli, Medical Record, Hemodialysis")
            
            if st.form_submit_button("Simpan"):
                if n_name:
                    hex_c = utils.COLOR_PALETTE[n_col]["hex"]
                    tags_map[n_name] = {"color": hex_c, "desc": n_desc}
                    utils.save_tags_config(tags_map)
                    st.toast("Konfigurasi Tersimpan!"); time.sleep(1); st.rerun()

# === TAB 5: ANALYTICS (FEEDBACK LOOP) ===
with tab5:
    st.subheader("📈 Pencarian Gagal (User Feedback)")
    st.caption("Daftar kata kunci yang dicari User tapi hasilnya < 32% (Tidak Relevan).")
    
    if utils.os.path.exists(FAILED_SEARCH_LOG):
        df_log = pd.read_csv(FAILED_SEARCH_LOG)
        
        col1, col2 = st.columns([4, 1])
        with col1:
            st.metric("Total Miss", len(df_log))
        with col2:
            if st.button("🗑️ Clear Log"):
                utils.os.remove(FAILED_SEARCH_LOG)
                st.rerun()
                
        if not df_log.empty:
            df_log = df_log.sort_values(by="Timestamp", ascending=False)
            st.dataframe(df_log, use_container_width=True)
    else:
        st.info("Belum ada data pencarian gagal. Sistem bekerja dengan baik!")