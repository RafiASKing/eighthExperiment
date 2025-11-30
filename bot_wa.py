import os
import requests
import uvicorn
import re
import base64
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
from src import database

# Load Environment Variables
load_dotenv()

app = FastAPI()

# Konfigurasi Evolution API
# Default URL container internal. Ganti instance jika perlu.
EVO_BASE_URL = os.getenv("EVO_BASE_URL", "http://evolution-api:8081")
EVO_API_KEY = os.getenv("EVO_API_KEY", "admin123")
INSTANCE_NAME = "faq_bot" 

def get_base64_image(file_path):
    """
    Encode gambar lokal ke Base64 Murni.
    Evolution API lebih simpel, tidak butuh header 'data:image...'
    """
    try:
        clean_path = file_path.replace("\\", "/")
        if not os.path.exists(clean_path): return None, None
        
        with open(clean_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        # Evolution butuh filename dan base64 string saja
        return encoded_string, os.path.basename(clean_path)
    except Exception as e:
        print(f"❌ Gagal encode gambar: {e}")
        return None, None

def send_evo_text(remote_jid, text):
    """Kirim Teks via Evolution API"""
    url = f"{EVO_BASE_URL}/message/sendText/{INSTANCE_NAME}"
    headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
    
    # Pastikan nomor formatnya benar (hapus @s.whatsapp.net jika ada, tapi Evolution biasanya pintar)
    if "@" in remote_jid: remote_jid = remote_jid.split("@")[0]

    payload = {
        "number": remote_jid, 
        "text": text
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        # print(f"📤 Sent Text: {r.status_code}")
    except Exception as e:
        print(f"❌ Error Send Text: {e}")

def send_evo_image(remote_jid, file_path, caption=""):
    """Kirim Gambar via Evolution API"""
    url = f"{EVO_BASE_URL}/message/sendMedia/{INSTANCE_NAME}"
    headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
    
    if "@" in remote_jid: remote_jid = remote_jid.split("@")[0]

    base64_str, filename = get_base64_image(file_path)
    if not base64_str: return

    payload = {
        "number": remote_jid,
        "medias": [{
            "type": "image",
            "caption": caption,
            "data": base64_str,
            "fileName": filename
        }]
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"🖼️ Sent Image: {r.status_code}")
    except Exception as e:
        print(f"❌ Error Send Image: {e}")

def process_logic(remote_jid, sender_name, message_body, is_group, has_mention):
    """
    Otak Bot:
    - Balas jika Chat Pribadi (PC)
    - Balas jika Grup DAN (Dimention ATAU ada keyword @faq)
    """
    
    # 1. LOGIKA TRIGGER
    should_reply = False
    
    if not is_group:
        # PC: Selalu balas
        should_reply = True
    else:
        # Group: Cek trigger
        if has_mention:
            should_reply = True
        elif "@faq" in message_body.lower():
            should_reply = True
            
    if not should_reply: return

    # 2. CLEANING QUERY
    # Hapus @faq dan mention format WA (@628123...) agar search bersih
    clean_query = message_body.replace("@faq", "").strip()
    clean_query = re.sub(r'@\d+', '', clean_query).strip()

    if not clean_query:
        send_evo_text(remote_jid, f"Halo {sender_name}, silakan ketik pertanyaanmu.")
        return

    print(f"🔍 Searching: '{clean_query}' (From: {sender_name})")

    # 3. SEARCH DATABASE
    results = database.search_faq_for_bot(clean_query, filter_tag="Semua Modul")
    
    reply_text = ""
    list_gambar_to_send = []

    if not results or not results['ids'][0]:
        reply_text = f"🙏 Maaf {sender_name}, tidak ditemukan jawaban untuk: *'{clean_query}'*."
        send_evo_text(remote_jid, reply_text)
        return
    else:
        # Ambil Top 1
        meta = results['metadatas'][0][0]
        dist = results['distances'][0][0]
        score = max(0, (1 - dist) * 100)

        # Ambang batas kepercayaan (bisa diatur)
        if score < 60:
             reply_text = f"🤔 Kurang yakin ({score:.0f}%):\n\n"
        else:
             reply_text = f"🤖 *FAQ Assistant* ({score:.0f}%)\n\n"

        judul = meta['judul']
        jawaban_raw = meta['jawaban_tampil']
        
        # 4. PARSING GAMBAR (Fitur Request Kamu)
        # Ambil path gambar dari database
        raw_paths = meta.get('path_gambar', 'none')
        img_db_list = []
        if raw_paths and str(raw_paths).lower() != 'none':
             paths = raw_paths.split(';')
             for p in paths:
                 # Normalisasi path windows/linux
                 img_db_list.append(p.strip().replace("\\", "/"))

        # Fungsi ganti teks [GAMBAR 1] -> (Lihat Gambar)
        def replace_tag(match):
            try:
                # match.group(1) itu angkanya (1, 2, dst)
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(img_db_list):
                    list_gambar_to_send.append(img_db_list[idx])
                    return f"*( 👇 Lihat Gambar {idx+1} )*"
                return ""
            except: return ""

        # Lakukan penggantian teks
        jawaban_processed = re.sub(r'\[GAMBAR\s*(\d+)\]', replace_tag, jawaban_raw, flags=re.IGNORECASE)
        
        # Fallback: Jika ada gambar tapi tidak ditulis [GAMBAR X] di teks, kirim semua
        if not list_gambar_to_send and img_db_list:
            list_gambar_to_send = img_db_list

        # Susun Pesan
        reply_text += f"❓ *{judul}*\n✅ {jawaban_processed}\n"
        if meta.get('sumber_url'): reply_text += f"\n🔗 {meta.get('sumber_url')}"

        # 5. KIRIM HASIL
        send_evo_text(remote_jid, reply_text)
        
        # Kirim Gambar Asli
        for i, img_path in enumerate(list_gambar_to_send):
            send_evo_image(remote_jid, img_path, caption=f"Gambar #{i+1} untuk {judul}")

@app.post("/webhook")
async def evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook Handler - Menerima data dari Evolution API
    """
    try:
        body = await request.json()
        
        # Struktur Evolution: { "event": "...", "data": { ... } }
        event_type = body.get("event")
        data = body.get("data", {})
        
        # Kita hanya peduli kalau ada pesan masuk (messages.upsert)
        if event_type == "messages.upsert":
            msg = data
            
            # 1. Cek Pesan Diri Sendiri (Abaikan)
            if msg.get("key", {}).get("fromMe"): return {"status": "ignored_self"}
            
            # 2. Ambil Nomor Pengirim (Remote JID)
            remote_jid = msg.get("key", {}).get("remoteJid")
            
            # Abaikan status broadcast WhatsApp
            if "status@broadcast" in remote_jid: return {"status": "ignored_status"}

            # 3. Ambil Isi Pesan
            message_body = ""
            # Pesan Text Biasa
            if "conversation" in msg.get("message", {}):
                message_body = msg["message"]["conversation"]
            # Pesan Text dengan Format (Bold/Reply/Mention)
            elif "extendedTextMessage" in msg.get("message", {}):
                message_body = msg["message"]["extendedTextMessage"].get("text", "")
            # Kalau gambar caption
            elif "imageMessage" in msg.get("message", {}):
                message_body = msg["message"]["imageMessage"].get("caption", "")

            sender_name = msg.get("pushName", "User")
            
            # 4. Cek Tipe Chat (Grup atau Pribadi)
            is_group = "@g.us" in remote_jid
            
            # 5. Cek Mention (LOGIKA YANG SAYA KEMBALIKAN)
            has_mention = False
            if is_group:
                # Di Evolution, mention ada di dalam extendedTextMessage > contextInfo > mentionedJid
                context_info = msg.get("message", {}).get("extendedTextMessage", {}).get("contextInfo", {})
                mentioned_jids = context_info.get("mentionedJid", [])
                
                # Jika list mentionedJid TIDAK kosong, berarti ada yang ditag.
                # Asumsi: Kalau bot ada di grup dan ada tag, kemungkinan besar bot yang ditag
                # (Karena kita gak bisa cek nomor sendiri secara dinamis tanpa API call tambahan)
                if mentioned_jids:
                    has_mention = True

            # Jalankan logika utama di background
            background_tasks.add_task(
                process_logic, 
                remote_jid, 
                sender_name, 
                message_body, 
                is_group, 
                has_mention
            )
            
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}

@app.get("/")
def home():
    return {"status": "Evolution Bot Running", "engine": "Evolution API v2"}

if __name__ == "__main__":
    # Port 8000 sesuai docker-compose
    uvicorn.run("bot_wa:app", host="0.0.0.0", port=8000)