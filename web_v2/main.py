from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import sys
import markdown
import re
import math # Penting untuk hitung halaman

# Setup path agar bisa import dari folder src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import database, utils

app = FastAPI()

# --- SETUP STATIC FILES ---
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/images", StaticFiles(directory=os.path.join(os.path.dirname(current_dir), "images")), name="images")

templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))
TAGS_MAP = utils.load_tags_config()

# --- HELPER: TEXT PROCESSOR ---
def fix_markdown_format(text):
    """
    Memperbaiki teks agar List dan Baris Baru terbaca oleh Markdown standar.
    """
    if not text: return ""

    # 1. Paksa List Angka (1. dst) punya enter ganda sebelumnya
    # Pola: (Huruf/Titik) -> Enter -> (Angka)(Titik)(Spasi)
    # Diubah jadi: (Huruf/Titik) -> Enter -> Enter -> (Angka)...
    text = re.sub(r'([^\n])\n(\d+\.\s)', r'\1\n\n\2', text)
    
    # 2. Paksa List Bullet (- dst) punya enter ganda sebelumnya
    text = re.sub(r'([^\n])\n(-\s)', r'\1\n\n\2', text)

    return text

def process_content_to_html(text_markdown, img_path_str):
    if not text_markdown: return ""
    
    # LANGKAH 1: Perbaiki format teks mentah dulu (Regex)
    text_markdown = fix_markdown_format(text_markdown)
    
    # LANGKAH 2: Convert Markdown -> HTML
    # 'nl2br': Mengubah newlines (\n) menjadi <br> (agar enter terbaca)
    # 'extra': Support fitur markdown tambahan (tabel, dll)
    # 'sane_lists': Agar list angka/bullet tidak tercampur aduk
    try:
        html_content = markdown.markdown(
            text_markdown, 
            extensions=['nl2br', 'extra', 'sane_lists']
        )
    except Exception as e:
        # Fallback jika extension error, pakai basic saja
        print(f"Markdown Error: {e}")
        html_content = markdown.markdown(text_markdown)

    # LANGKAH 3: Parse Image Paths (Logic Gambar SAMA SEPERTI SEBELUMNYA)
    img_list = []
    if img_path_str and str(img_path_str).lower() != 'none':
        raw_paths = img_path_str.split(';')
        for p in raw_paths:
            clean = p.replace("\\", "/").strip()
            if clean.startswith("./images"):
                clean = clean[1:] 
            img_list.append(clean)

    # LANGKAH 4: Replace [GAMBAR X] dengan HTML <img>
    pattern = re.compile(r'\[GAMBAR\s*(\d+)\]', re.IGNORECASE)
    
    def replace_match(match):
        try:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(img_list):
                return f'''
                <div class="img-container">
                    <img src="{img_list[idx]}" alt="Gambar {idx+1}" loading="lazy" onclick="window.open(this.src, '_blank');">
                    <span class="img-caption">Gambar {idx+1} (Klik untuk perbesar)</span>
                </div>
                '''
            return ""
        except: return ""

    html_content = pattern.sub(replace_match, html_content)

    # Fallback Gallery
    if "[GAMBAR" not in text_markdown.upper() and img_list:
        html_content += "<hr class='img-divider'><div class='gallery-grid'>"
        for img in img_list:
             html_content += f'<div class="img-card"><img src="{img}" onclick="window.open(this.src, \'_blank\');"></div>'
        html_content += "</div>"

    return html_content
    
    def replace_match(match):
        try:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(img_list):
                return f'''
                <div class="img-container">
                    <img src="{img_list[idx]}" alt="Gambar {idx+1}" loading="lazy" onclick="window.open(this.src, '_blank');">
                    <span class="img-caption">Gambar {idx+1} (Klik untuk perbesar)</span>
                </div>
                '''
            return ""
        except: return ""

    html_content = pattern.sub(replace_match, html_content)

    # 4. Fallback Gallery (Jika gambar ada tapi tag tidak ditulis)
    if "[GAMBAR" not in text_markdown.upper() and img_list:
        html_content += "<hr class='img-divider'><div class='gallery-grid'>"
        for img in img_list:
             html_content += f'<div class="img-card"><img src="{img}" onclick="window.open(this.src, \'_blank\');"></div>'
        html_content += "</div>"

    return html_content

# --- MAIN ENDPOINT ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, q: str = "", tag: str = "Semua Modul", page: int = 0):
    
    ITEMS_PER_PAGE = 10
    results = []
    total_pages = 1
    is_search_mode = False

    # Ambil list tag untuk dropdown
    try: db_tags = database.get_unique_tags_from_db()
    except: db_tags = []
    all_tags = ["Semua Modul"] + (db_tags if db_tags else [])

    # === SKENARIO 1: SEARCH MODE (Top 3) ===
    if q.strip():
        is_search_mode = True
        raw = database.search_faq(q, filter_tag=tag, n_results=20)
        
        if raw and raw['ids'][0]:
            temp_results = []
            for i in range(len(raw['ids'][0])):
                meta = raw['metadatas'][0][i]
                dist = raw['distances'][0][i]
                score = max(0, (1 - dist) * 100)
                
                # Syarat Relevansi > 32%
                if score > 32:
                    meta['score'] = int(score)
                    if score > 80: meta['score_class'] = "score-high"
                    elif score > 50: meta['score_class'] = "score-med"
                    else: meta['score_class'] = "score-low"
                    
                    # Tambahkan warna badge
                    tag_info = TAGS_MAP.get(meta['tag'], {})
                    meta['badge_color'] = tag_info.get('color', '#808080')
                    
                    temp_results.append(meta)
            
            # Sortir Score Tertinggi -> Ambil Top 3 Saja (Request User)
            temp_results.sort(key=lambda x: x['score'], reverse=True)
            results = temp_results[:3]

    # === SKENARIO 2: BROWSE MODE (Terbaru + Paginasi) ===
    else:
        # Ambil semua data terurut ID Descending (Terbaru)
        raw_all = database.get_all_faqs_sorted()
        
        # Filter Tag Manual (karena Chroma get() tidak support where complex di versi lama)
        if tag != "Semua Modul":
            filtered_data = [x for x in raw_all if x.get('tag') == tag]
        else:
            filtered_data = raw_all
            
        # Hitung Paginasi
        total_docs = len(filtered_data)
        total_pages = math.ceil(total_docs / ITEMS_PER_PAGE)
        
        # Guard: jangan sampai page melebihi total
        if page >= total_pages: page = 0
        if page < 0: page = 0
        
        start = page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        
        # Slice data untuk halaman ini
        sliced_data = filtered_data[start:end]
        
        for meta in sliced_data:
            # Setup metadata default untuk tampilan
            meta['score'] = None # Tidak ada score relevansi kalau mode browse
            tag_info = TAGS_MAP.get(meta['tag'], {})
            meta['badge_color'] = tag_info.get('color', '#808080')
            results.append(meta)

    # === PROCESS CONTENT UNTUK SEMUA HASIL ===
    for item in results:
        item['html_content'] = process_content_to_html(
            item.get('jawaban_tampil', ''), 
            item.get('path_gambar', '')
        )

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "results": results, 
        "query": q, 
        "current_tag": tag,
        "all_tags": all_tags,
        
        # Data Paginasi
        "page": page,
        "total_pages": total_pages,
        "is_search_mode": is_search_mode,
        "total_items": len(results)
    })

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)