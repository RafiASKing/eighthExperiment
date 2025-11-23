import streamlit as st
import pandas as pd
import time
from src import database, utils

# --- AUTH ---
if 'auth' not in st.session_state: st.session_state.auth = False

def login():
    if st.session_state.pass_input == "veven": 
        st.session_state.auth = True
    else:
        st.error("Password salah")

if not st.session_state.auth:
    st.title("🔒 Admin Login")
    st.text_input("Password", type="password", key="pass_input", on_change=login)
    st.stop()

# --- MAIN UI ---
st.title("🛠️ Admin Console")
tags_map = utils.load_tags_config()
tab1, tab2, tab3, tab4 = st.tabs(["📊 List Data", "➕ Tambah", "✏️ Edit/Hapus", "⚙️ Config Tags"])

# === TAB 1: LIST ===
with tab1:
    df = database.get_all_data_as_df()
    st.dataframe(df, use_container_width=True, hide_index=True)

# === TAB 2: TAMBAH (AUTO CLEAR) ===
with tab2:
    st.info("Form otomatis reset setelah simpan.")
    coll = database.get_collection()
    next_id = utils.get_next_id_safe(coll)
    st.markdown(f"**Next ID:** `{next_id}`")

    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns([1, 3])
        with c1: i_tag = st.selectbox("Modul", list(tags_map.keys()))
        with c2: i_judul = st.text_input("Judul")
            
        i_jawab = st.text_area("Jawaban", height=150)
        i_key = st.text_input("Keyword Tambahan")
        i_src = st.text_input("Source URL")
        i_imgs = st.file_uploader("Gambar", accept_multiple_files=True)
        
        if st.form_submit_button("💾 SIMPAN DATA", type="primary"):
            if not i_judul or not i_jawab:
                st.error("Wajib isi Judul & Jawaban!")
            else:
                try:
                    with st.spinner("Menyimpan..."):
                        real_coll = database.get_collection()
                        safe_id = utils.get_next_id_safe(real_coll)
                        paths = utils.save_uploaded_images(i_imgs, i_judul, i_tag)
                        database.upsert_faq(safe_id, i_tag, i_judul, i_jawab, i_key, paths, i_src)
                        st.toast(f"✅ Data ID {safe_id} Tersimpan!")
                        time.sleep(1)
                        st.rerun()
                except Exception as e: st.error(f"Error: {e}")

# === TAB 3: EDIT ===
with tab3:
    df = database.get_all_data_as_df()
    if not df.empty:
        opts = [f"{r['ID']} | {r['Judul']}" for _, r in df.iterrows()]
        sel = st.selectbox("Pilih Data", opts)
        sel_id = sel.split(" | ")[0]
        
        row = df[df['ID'] == sel_id].iloc[0]
        with st.form("edit_form"):
            curr_tag = row['Tag']
            idx_tag = list(tags_map.keys()).index(curr_tag) if curr_tag in tags_map else 0
            
            e_tag = st.selectbox("Modul", list(tags_map.keys()), index=idx_tag)
            e_judul = st.text_input("Judul", value=row['Judul'])
            e_jawab = st.text_area("Jawaban", value=row['Jawaban'])
            e_key = st.text_input("Keyword", value=row['Keyword'])
            e_src = st.text_input("URL", value=row['Source'])
            
            st.markdown(f"**Gambar:** `{row['Gambar']}`")
            e_imgs = st.file_uploader("Upload Gambar Baru (Overwrite)", accept_multiple_files=True)
            
            c_up, c_del = st.columns(2)
            if c_up.form_submit_button("💾 UPDATE"):
                final_path = row['Gambar']
                if e_imgs: final_path = utils.save_uploaded_images(e_imgs, e_judul, e_tag)
                database.upsert_faq(sel_id, e_tag, e_judul, e_jawab, e_key, final_path, e_src)
                st.toast("Update Berhasil!", icon="✅")
                time.sleep(1)
                st.rerun()
                
            if c_del.form_submit_button("🗑️ HAPUS", type="primary"):
                database.delete_faq(sel_id)
                st.toast("Data dihapus.", icon="🗑️")
                time.sleep(1)
                st.rerun()

# === TAB 4: CONFIG TAGS ===
with tab4:
    st.header("🎨 Atur Kategori & Warna")
    
    # Flatten Data for Table
    flat_data = []
    for tag, val in tags_map.items():
        color = val.get("color", "#808080") if isinstance(val, dict) else val
        desc = val.get("desc", "") if isinstance(val, dict) else ""
        flat_data.append({"Tag": tag, "Warna": color, "Deskripsi AI": desc})
        
    st.dataframe(pd.DataFrame(flat_data), use_container_width=True, hide_index=True)
    st.divider()
    
    with st.form("tag_form", clear_on_submit=True):
        st.subheader("Tambah / Edit Tag")
        c_name = st.text_input("Nama Tag", placeholder="Contoh: Gizi")
        c_label = st.selectbox("Pilih Warna", list(utils.COLOR_PALETTE.keys()))
        c_desc = st.text_area("Context AI", placeholder="Sinonim modul...")
        
        if st.form_submit_button("Simpan Tag"):
            if c_name:
                hex_code = utils.COLOR_PALETTE[c_label]["hex"]
                tags_map[c_name] = {"color": hex_code, "desc": c_desc}
                utils.save_tags_config(tags_map)
                st.toast(f"Tag {c_name} tersimpan!", icon="✅")
                time.sleep(1)
                st.rerun()
                
    st.divider()
    d_tag = st.selectbox("Hapus Tag", list(tags_map.keys()))
    if st.button("Hapus Tag Terpilih"):
        del tags_map[d_tag]
        utils.save_tags_config(tags_map)
        st.rerun()