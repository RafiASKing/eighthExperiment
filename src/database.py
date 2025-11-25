# --- 1. FORCE USE NEW SQLITE (Wajib Paling Atas untuk Docker/Linux) ---
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

# --- 2. IMPORTS LENGKAP ---
import chromadb
import pandas as pd
import streamlit as st
import time
import functools
import random
import os
from google import genai
from google.genai import types
from .config import GOOGLE_API_KEY, DB_PATH, COLLECTION_NAME
from .utils import clean_text_for_embedding, load_tags_config

# --- 3. RETRY DECORATOR (SAFE CONCURRENCY) ---
def retry_on_lock(max_retries=10, base_delay=0.1):
    """
    Menangani error 'Database Locked' pada SQLite dengan Jitter Backoff.
    Aman digunakan oleh Streamlit maupun Bot eksternal.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    err_msg = str(e).lower()
                    if "locked" in err_msg or "busy" in err_msg:
                        retries += 1
                        sleep_time = base_delay * (1 + random.random())
                        time.sleep(sleep_time)
                    else:
                        raise e
            raise Exception("Database sedang sibuk (High Traffic), silakan coba lagi sesaat.")
        return wrapper
    return decorator

# --- 4. RAW FUNCTIONS (UNTUK BOT WA / API) ---
# Fungsi-fungsi ini TIDAK menggunakan @st.cache, jadi aman dipanggil script luar.

def _get_ai_client_raw():
    """Membuat koneksi ke Google Gemini (Tanpa Cache Streamlit)"""
    return genai.Client(api_key=GOOGLE_API_KEY)

def _get_db_client_raw():
    """
    Logika Cerdas:
    Cek apakah ada ENV Host Server?
    - Ada: Pake Mode Server (Production/Docker) 🚀
    - Ga ada: Pake Mode File (Local Laptop) 📂
    """
    host = os.getenv("CHROMA_HOST")
    port = os.getenv("CHROMA_PORT")

    if host and port:
        # Client-Server Mode
        return chromadb.HttpClient(host=host, port=int(port))
    else:
        # Local Mode (Fallback)
        return chromadb.PersistentClient(path=DB_PATH)

def _generate_embedding_raw(text):
    """Generate Embedding langsung (Tanpa Cache Streamlit)"""
    client = _get_ai_client_raw()
    try:
        response = client.models.embed_content(
            model="models/gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"⚠️ Error Embedding AI: {e}")
        return []

# --- 5. STREAMLIT CACHED FUNCTIONS (UNTUK WEB APP) ---
# Fungsi ini khusus untuk Web App agar performa cepat (pake cache).

@st.cache_resource(show_spinner=False)
def get_db_client():
    return _get_db_client_raw()

@st.cache_resource(show_spinner=False)
def get_ai_client():
    return _get_ai_client_raw()

def get_collection():
    client = get_db_client()
    return client.get_or_create_collection(name=COLLECTION_NAME)

@st.cache_data(show_spinner=False)
def generate_embedding_cached(text):
    # Wrapper agar embedding di-cache oleh Streamlit
    return _generate_embedding_raw(text)

# --- 6. INTERNAL HELPER (ID GENERATOR) ---
def _get_next_id_internal(collection):
    data = collection.get(include=[])
    existing_ids = data['ids']
    
    if not existing_ids: return "1"
    
    numeric_ids = []
    for x in existing_ids:
        if x.isdigit(): 
            numeric_ids.append(int(x))
    
    if not numeric_ids: return "1"
    return str(max(numeric_ids) + 1)

# --- 7. CORE LOGIC (READ - USER WEB APP) ---
@retry_on_lock()
def search_faq(query_text, filter_tag=None, n_results=50):
    """
    Digunakan oleh app.py (Web). Menggunakan Embedding Ter-Cache.
    """
    col = get_collection()
    vec = generate_embedding_cached(query_text) # Pake Cache
    
    if not vec: 
        return {"ids": [[]], "metadatas": [[]], "distances": [[]]}

    # Pre-Filtering logic
    where_clause = {"tag": filter_tag} if (filter_tag and filter_tag != "Semua Modul") else None
    
    return col.query(
        query_embeddings=[vec],
        n_results=n_results,
        where=where_clause
    )

@retry_on_lock()
def get_all_faqs_sorted():
    col = get_collection()
    data = col.get(include=['metadatas'])
    
    results = []
    if data['ids']:
        for i, doc_id in enumerate(data['ids']):
            meta = data['metadatas'][i]
            try: id_num = int(doc_id)
            except: id_num = 0
            
            meta['id'] = doc_id
            meta['id_num'] = id_num
            results.append(meta)
            
    results.sort(key=lambda x: x.get('id_num', 0), reverse=True)
    return results

def get_unique_tags_from_db():
    col = get_collection()
    data = col.get(include=['metadatas'])
    unique_tags = set()
    if data['metadatas']:
        for meta in data['metadatas']:
            if meta and meta.get('tag'):
                unique_tags.add(meta['tag'])
    return sorted(list(unique_tags))

# --- 8. CORE LOGIC (WRITE - ADMIN) ---
# Admin selalu diakses via Streamlit, jadi aman pakai retry dan logic biasa.

@st.cache_data(show_spinner=False)
def get_all_data_as_df():
    col = get_collection()
    data = col.get(include=['metadatas', 'documents'])
    
    if not data['ids']: return pd.DataFrame()
    
    rows = []
    for i, doc_id in enumerate(data['ids']):
        meta = data['metadatas'][i]
        rows.append({
            "ID": doc_id,
            "Tag": meta.get('tag'),
            "Judul": meta.get('judul'),
            "Jawaban": meta.get('jawaban_tampil'),
            "Keyword": meta.get('keywords_raw'),
            "Gambar": meta.get('path_gambar'),
            "Source": meta.get('sumber_url'),
            "AI Context": data['documents'][i] if data['documents'] else ""
        })
    
    df = pd.DataFrame(rows)
    df['ID_Num'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0)
    return df.sort_values('ID_Num', ascending=False).drop(columns=['ID_Num'])

@retry_on_lock()
def upsert_faq(doc_id, tag, judul, jawaban, keyword, img_paths, src_url):
    col = get_collection()
    
    final_id = str(doc_id)
    if doc_id == "auto" or doc_id is None:
        final_id = _get_next_id_internal(col)
    
    clean_jawaban = clean_text_for_embedding(jawaban)
    
    try:
        tags_config = load_tags_config()
        tag_desc = tags_config.get(tag, {}).get("desc", "")
    except:
        tag_desc = ""
    
    domain_str = f"{tag} ({tag_desc})" if tag_desc else tag

    # Format Embedding HyDE
    text_embed = f"""DOMAIN: {domain_str}
DOKUMEN: {judul}
VARIASI PERTANYAAN USER: {keyword}
ISI KONTEN: {clean_jawaban}"""
    
    # Gunakan cached embedding agar konsisten, toh ini proses lambat (write)
    vector = generate_embedding_cached(text_embed)
    
    col.upsert(
        ids=[final_id],
        embeddings=[vector],
        documents=[text_embed],
        metadatas=[{
            "tag": tag, 
            "judul": judul, 
            "jawaban_tampil": jawaban, 
            "keywords_raw": keyword,
            "path_gambar": img_paths,
            "sumber_url": src_url
        }]
    )
    return final_id

@retry_on_lock()
def delete_faq(doc_id):
    col = get_collection()
    try:
        data = col.get(ids=[str(doc_id)], include=['metadatas'])
        if data['metadatas'] and len(data['metadatas']) > 0:
            meta = data['metadatas'][0]
            img_str = meta.get('path_gambar', 'none')
            if img_str and img_str.lower() != 'none':
                paths = img_str.split(';')
                for p in paths:
                    clean_path = p.replace("\\", "/")
                    if os.path.exists(clean_path):
                        try:
                            os.remove(clean_path)
                            print(f"🗑️ Zombie File Deleted: {clean_path}")
                        except Exception as e:
                            print(f"⚠️ Gagal hapus file {clean_path}: {e}")
    except Exception as e:
        print(f"⚠️ Error cleaning images: {e}")

    col.delete(ids=[str(doc_id)])

# --- 9. SPECIAL FUNCTION FOR BOT WA (NO STREAMLIT DEPENDENCY) ---
@retry_on_lock()
def search_faq_for_bot(query_text, filter_tag="Semua Modul"):
    """
    Fungsi khusus untuk Bot WA / API External.
    MANDIRI: Membuka koneksi sendiri, Embedding sendiri tanpa Cache Streamlit.
    """
    # 1. Buka Koneksi Raw (Tanpa st.cache_resource)
    client = _get_db_client_raw()
    col = client.get_or_create_collection(name=COLLECTION_NAME)
    
    # 2. Embedding Raw (Tanpa st.cache_data)
    vec = _generate_embedding_raw(query_text)
    
    if not vec: 
        return None # Return None jika gagal embedding

    # 3. Filtering Logic
    where_clause = {"tag": filter_tag} if (filter_tag and filter_tag != "Semua Modul") else None
    
    # 4. Query
    results = col.query(
        query_embeddings=[vec],
        n_results=5, # Ambil Top 5 aja buat Bot
        where=where_clause
    )
    
    return results