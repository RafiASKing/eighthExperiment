from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import sys
import markdown
import re

# Setup path agar bisa import dari folder src (naik satu level)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import database, utils

app = FastAPI()

# 1. SETUP STATIC FILES
# - 'static' untuk CSS/JS custom kita
# - 'images' untuk folder upload gambar agar bisa diakses browser
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
os.makedirs(static_dir, exist_ok=True) # Buat folder static jika belum ada

app.mount("/static", StaticFiles(directory=static_dir), name="static")
# Mounting folder images dari root project
app.mount("/images", StaticFiles(directory=os.path.join(os.path.dirname(current_dir), "images")), name="images")

templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))
TAGS_MAP = utils.load_tags_config()

# --- HELPER: TEXT & IMAGE PROCESSOR ---
def process_content_to_html(text_markdown, img_path_str):
    """
    Mengubah Markdown -> HTML
    Mengubah [GAMBAR X] -> <img src="...">
    """
    # 1. Convert Markdown basic (Bold, List, etc) ke HTML
    html_content = markdown.markdown(text_markdown)

    # 2. Siapkan list path gambar
    img_list = []
    if img_path_str and str(img_path_str).lower() != 'none':
        # Split dan bersihkan path
        raw_paths = img_path_str.split(';')
        for p in raw_paths:
            # Ubah path lokal "./images/..." menjadi URL "/images/..."
            clean = p.replace("\\", "/").strip()
            if clean.startswith("./images"):
                clean = clean[1:] # Hapus titik di depan, jadi /images/...
            img_list.append(clean)

    # 3. Replace Tag [GAMBAR X] dengan <img> HTML
    # Pola regex untuk menangkap [GAMBAR 1], [GAMBAR 12], dst
    pattern = re.compile(r'\[GAMBAR\s*(\d+)\]', re.IGNORECASE)
    
    def replace_match(match):
        try:
            # Ambil angka di dalam tag (mulai dari 1)
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(img_list):
                # Return tag IMG HTML yang responsif
                return f'''
                <div class="img-container">
                    <img src="{img_list[idx]}" alt="Gambar {idx+1}" loading="lazy" onclick="window.open(this.src, '_blank');">
                    <span class="img-caption">Gambar {idx+1} (Klik untuk perbesar)</span>
                </div>
                '''
            else:
                return f'<span class="img-error">(Gambar #{idx+1} tidak ditemukan)</span>'
        except:
            return ""

    html_content = pattern.sub(replace_match, html_content)

    # 4. Jika masih ada sisa gambar yang belum dipanggil tag, taruh di bawah (Fallback)
    # (Logic sederhana: kalau tidak ada tag [GAMBAR] sama sekali tapi ada file)
    if "[GAMBAR" not in text_markdown.upper() and img_list:
        html_content += "<hr class='img-divider'>"
        html_content += "<div class='gallery-grid'>"
        for img in img_list:
             html_content += f'''
                <div class="img-card">
                    <img src="{img}" loading="lazy" onclick="window.open(this.src, '_blank');">
                </div>
             '''
        html_content += "</div>"

    return html_content

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, q: str = "", tag: str = "Semua Modul"):
    results = []
    
    # Ambil list tag unik untuk Dropdown
    try:
        db_tags = database.get_unique_tags_from_db()
    except:
        db_tags = []
    all_tags = ["Semua Modul"] + (db_tags if db_tags else [])

    if q:
        # Search Logic
        raw = database.search_faq(q, filter_tag=tag, n_results=20)
        
        if raw and raw['ids'][0]:
            for i in range(len(raw['ids'][0])):
                meta = raw['metadatas'][0][i]
                dist = raw['distances'][0][i]
                score = max(0, (1 - dist) * 100)
                
                # Filter Relevansi (Bisa disesuaikan, misal > 30%)
                if score > 30:
                    meta['score'] = int(score)
                    
                    # Formatting Warna Score
                    if score > 80: meta['score_class'] = "score-high"
                    elif score > 50: meta['score_class'] = "score-med"
                    else: meta['score_class'] = "score-low"

                    # Ambil warna badge
                    tag_info = TAGS_MAP.get(meta['tag'], {})
                    meta['badge_color'] = tag_info.get('color', '#808080')
                    
                    # PROSES KONTEN JADI HTML DI SINI
                    meta['html_content'] = process_content_to_html(
                        meta.get('jawaban_tampil', ''), 
                        meta.get('path_gambar', '')
                    )
                    
                    results.append(meta)
            
            # Sortir by Score Tertinggi
            results.sort(key=lambda x: x['score'], reverse=True)
            results = results[:10] # Ambil Top 10

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "results": results, 
        "query": q, 
        "current_tag": tag,
        "all_tags": all_tags
    })

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)