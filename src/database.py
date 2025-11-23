try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass # Fallback jika pysqlite3 belum terinstall/tidak perlu

import chromadb
import pandas as pd
from google import genai
from google.genai import types
from .config import GOOGLE_API_KEY, DB_PATH, COLLECTION_NAME
from .utils import load_tags_config


# --- SETUP CLIENTS ---
client_ai = genai.Client(api_key=GOOGLE_API_KEY)
client_db = chromadb.PersistentClient(path=DB_PATH)

def get_collection():
    return client_db.get_or_create_collection(name=COLLECTION_NAME)

def generate_embedding(text):
    response = client_ai.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
    )
    return response.embeddings[0].values

# --- LOGIKA CONTEXT BARU (Dari Request Kamu) ---
def build_context_text(judul, jawaban, keyword, tag):
    tags_cfg = load_tags_config()
    
    # Ambil context dari config (asumsi struktur JSON baru)
    # Jika masih struktur lama (hanya warna), default string kosong
    tag_data = tags_cfg.get(tag, {})
    
    # Fallback jika JSON masi format simple key:value warna
    if isinstance(tag_data, str): 
        extra_context = "" 
    else:
        extra_context = tag_data.get("context", "")

    return f"""Modul Sistem: {tag}
Sinonim/Konteks tambahan: {extra_context}

Masalah/Pertanyaan:
{judul}

Solusi/Langkah-langkah:
{jawaban}

Keyword Tambahan (Slang/Error Code):
{keyword}"""

# --- CORE FEATURES ---
def get_unique_tags_from_db():
    """Mengambil semua tag unik yang BENAR-BENAR ADA di database"""
    collection = get_collection()
    # Kita hanya butuh metadata, jangan load dokumen/image path biar cepat
    data = collection.get(include=['metadatas'])
    
    unique_tags = set()
    if data['metadatas']:
        for meta in data['metadatas']:
            # Handle jaga-jaga kalau ada data lama tanpa key 'tag'
            tag = meta.get('tag')
            if tag:
                unique_tags.add(tag)
                
    return sorted(list(unique_tags))

def search_faq(query_text, filter_tag=None, n_results=3):
    collection = get_collection()
    
    resp = client_ai.models.embed_content(
        model="models/gemini-embedding-001",
        contents=query_text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
    )
    q_vec = resp.embeddings[0].values
    
    where_clause = {"tag": filter_tag} if (filter_tag and filter_tag != "Semua Modul") else None
    
    results = collection.query(
        query_embeddings=[q_vec],
        n_results=n_results,
        where=where_clause
    )
    return results

# --- UPDATE: MENAMPILKAN CONTEXT & EMBEDDING ---
def get_all_data_as_df():
    collection = get_collection()
    data = collection.get(include=['metadatas', 'documents', 'embeddings'])
    
    if not data['ids']: return pd.DataFrame()
    
    rows = []
    # Ambil list embeddings ke variabel dulu biar aman
    all_embeddings = data.get('embeddings') 
    
    for i, doc_id in enumerate(data['ids']):
        meta = data['metadatas'][i]
        
        # Ambil Context
        context_full = data['documents'][i] if data['documents'] else ""
        
        # --- PERBAIKAN ERROR VALUE ERROR DI SINI ---
        # Cek pakai len() agar aman untuk NumPy Array maupun List
        embed_vec = []
        if all_embeddings is not None and len(all_embeddings) > 0:
            embed_vec = all_embeddings[i]
            
        # Preview 5 angka pertama
        embed_preview = str(embed_vec[:5]) + "..." if len(embed_vec) > 0 else "[]"
        # -------------------------------------------

        rows.append({
            "ID": doc_id,
            "Tag": meta.get('tag', '-'),
            "Judul": meta.get('judul', '-'),
            "Jawaban": meta.get('jawaban_tampil', ''),
            "Keyword": meta.get('keywords_raw', ''),
            "Gambar": meta.get('path_gambar', 'none'),
            "Source": meta.get('sumber_url', ''),
            "AI Context": context_full,
            "Embed Vector": embed_preview
        })
    
    df = pd.DataFrame(rows)
    df['ID_Num'] = pd.to_numeric(df['ID'], errors='coerce')
    df = df.sort_values('ID_Num', ascending=False).drop(columns=['ID_Num'])
    return df


def upsert_faq(doc_id, tag, judul, jawaban, keyword, img_paths, src_url):
    collection = get_collection()
    # Panggil logic combiner baru
    text_embed = build_context_text(judul, jawaban, keyword, tag)
    vector = generate_embedding(text_embed)
    
    collection.upsert(
        ids=[str(doc_id)],
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

def delete_faq(doc_id):
    collection = get_collection()
    collection.delete(ids=[str(doc_id)])