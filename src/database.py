# --- 1. FORCE USE NEW SQLITE (Wajib di Paling Atas) ---
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass 

# --- 2. IMPORTS ---
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

def build_context_text(judul, jawaban, keyword, tag):
    tags_cfg = load_tags_config()
    
    # Ambil context dari config
    tag_data = tags_cfg.get(tag, {})
    
    if isinstance(tag_data, dict):
        extra_context = tag_data.get("desc", "")
    else:
        extra_context = "" 

    return f"""Modul Sistem: {tag}
Konsep Terkait: {extra_context}

Masalah/Pertanyaan:
{judul}

Solusi/Langkah-langkah:
{jawaban}

Keyword Tambahan:
{keyword}"""

# --- CORE FEATURES (USER) ---

def search_faq(query_text, filter_tag=None, n_results=50):
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

def get_all_faqs_sorted():
    """Mengambil SEMUA metadata urut ID terbaru (untuk Pagination)"""
    collection = get_collection()
    data = collection.get(include=['metadatas'])
    
    results = []
    if data['ids']:
        for i, doc_id in enumerate(data['ids']):
            meta = data['metadatas'][i]
            
            try: id_num = int(doc_id)
            except: id_num = 0
                
            results.append({
                "id": doc_id,
                "id_num": id_num, 
                "tag": meta.get('tag', 'Umum'),
                "judul": meta.get('judul', '-'),
                "jawaban_tampil": meta.get('jawaban_tampil', ''),
                "path_gambar": meta.get('path_gambar', 'none'),
                "sumber_url": meta.get('sumber_url', '')
            })
    
    # Sort Descending (Terbaru diatas)
    results.sort(key=lambda x: x['id_num'], reverse=True)
    return results

def get_unique_tags_from_db():
    collection = get_collection()
    data = collection.get(include=['metadatas'])
    unique_tags = set()
    if data['metadatas']:
        for meta in data['metadatas']:
            if meta.get('tag'): unique_tags.add(meta['tag'])
    return sorted(list(unique_tags))

# --- CORE FEATURES (ADMIN) ---

def get_all_data_as_df():
    collection = get_collection()
    data = collection.get(include=['metadatas', 'documents', 'embeddings'])
    
    if not data['ids']: return pd.DataFrame()
    
    rows = []
    for i, doc_id in enumerate(data['ids']):
        meta = data['metadatas'][i]
        rows.append({
            "ID": doc_id,
            "Tag": meta.get('tag', '-'),
            "Judul": meta.get('judul', '-'),
            "Jawaban": meta.get('jawaban_tampil', ''),
            "Keyword": meta.get('keywords_raw', ''),
            "Gambar": meta.get('path_gambar', 'none'),
            "Source": meta.get('sumber_url', ''),
            "AI Context": data['documents'][i] if data['documents'] else ""
        })
    
    df = pd.DataFrame(rows)
    df['ID_Num'] = pd.to_numeric(df['ID'], errors='coerce')
    df = df.sort_values('ID_Num', ascending=False).drop(columns=['ID_Num'])
    return df

def upsert_faq(doc_id, tag, judul, jawaban, keyword, img_paths, src_url):
    collection = get_collection()
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