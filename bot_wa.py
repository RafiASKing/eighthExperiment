import os
import requests
import uvicorn
import re
import base64
import mimetypes
import json
import sys
import time
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
from src import database

# Load Environment Variables
load_dotenv()

app = FastAPI()

# --- KONFIGURASI ---
WA_BASE_URL = os.getenv("WA_BASE_URL", "http://wppconnect:21465")
# Masukkan SECRET KEY (misal: THISISMYSECURETOKEN), nanti bot otomatis ubah jadi token
WA_SECRET_KEY = os.getenv("WA_SESSION_KEY", "THISISMYSECURETOKEN") 
WA_SESSION_NAME = "mysession"

# Variable Global untuk menyimpan Token Bearer
CURRENT_TOKEN = None

# --- FUNGSI LOGGING ---
def log(message):
    print(message, flush=True)

# --- FUNGSI AUTH OTOMATIS ---
def get_headers():
    global CURRENT_TOKEN
    if not CURRENT_TOKEN:
        log("🔄 Token kosong. Mencoba generate token baru...")
        generate_token()
    
    return {
        "Authorization": f"Bearer {CURRENT_TOKEN}",
        "Content-Type": "application/json"
    }

def generate_token():
    global CURRENT_TOKEN
    try:
        # Endpoint generate token menggunakan Secret Key
        url = f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/{WA_SECRET_KEY}/generate-token"
        r = requests.post(url)
        if r.status_code == 200 or r.status_code == 201:
            resp = r.json()
            # Ambil token dari respons
            token = resp.get("token") or resp.get("session") 
            # (Tergantung versi WPP, kadang token ada di key berbeda)
            
            # WPPConnect versi baru return structure: {"status": "success", "token": "..."}
            if not token and "full" in resp:
                 # Kadang return 'full': 'session:token'
                 token = resp["full"].split(":")[-1]

            if token:
                CURRENT_TOKEN = token
                log(f"✅ Berhasil Generate Token: {str(token)[:15]}...")
            else:
                log(f"❌ Gagal Parse Token dari respon: {resp}")
        else:
            log(f"❌ Gagal Generate Token (Status {r.status_code}): {r.text}")
    except Exception as e:
        log(f"❌ Error Connection saat Auth: {e}")

# --- FUNGSI UTILITY ---
def get_base64_image(file_path):
    try:
        clean_path = file_path.replace("\\", "/")
        if not os.path.exists(clean_path): return None, None
        mime_type, _ = mimetypes.guess_type(clean_path)
        if not mime_type: mime_type = "image/jpeg"
        with open(clean_path, "rb") as image_file:
            raw_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:{mime_type};base64,{raw_base64}", os.path.basename(clean_path)
    except: return None, None

def send_wpp_text(phone, message):
    if not phone or str(phone) == "None":
        log("⚠️ Batal kirim pesan karena nomor tujuan 'None'")
        return

    url = f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/send-message"
    payload = {"phone": phone, "message": message, "isGroup": False}
    try:
        # Gunakan get_headers() agar selalu pakai token terbaru
        r = requests.post(url, json=payload, headers=get_headers())
        log(f"📤 Balas ke {phone}: {r.status_code}")
        if r.status_code == 401:
            log("🔄 Token Expired/Salah. Regenerating...")
            generate_token() # Coba refresh token kalau gagal
    except Exception as e:
        log(f"❌ Error Kirim Text: {e}")

def send_wpp_image(phone, file_path, caption=""):
    if not phone: return
    url = f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/send-image"
    base64_str, _ = get_base64_image(file_path)
    if not base64_str: return
    payload = {"phone": phone, "base64": base64_str, "caption": caption, "isGroup": False}
    try:
        requests.post(url, json=payload, headers=get_headers())
        log(f"🖼️ Kirim Gambar ke {phone}")
    except Exception as e:
        log(f"❌ Error Kirim Gambar: {e}")

def process_logic(remote_jid, sender_name, message_body, is_group, has_mention):
    log(f"⚙️ Memproses Pesan: '{message_body}' dari {sender_name}")
    
    if not message_body:
        log("⚠️ Pesan kosong, diabaikan.")
        return

    # Logic trigger
    should_reply = False
    if not is_group: should_reply = True
    elif has_mention or "@faq" in message_body.lower(): should_reply = True
    
    if not should_reply: 
        log("⚠️ Pesan diabaikan (Tidak memenuhi syarat trigger)")
        return

    clean_query = message_body.replace("@faq", "").strip()
    clean_query = re.sub(r'@\d+', '', clean_query).strip()

    if not clean_query:
        send_wpp_text(remote_jid, f"Halo {sender_name}, silakan ketik pertanyaanmu.")
        return

    log(f"🔍 Mencari di Database: '{clean_query}'")
    try:
        results = database.search_faq_for_bot(clean_query, filter_tag="Semua Modul")
    except Exception as e:
        log(f"❌ Database Error: {e}")
        send_wpp_text(remote_jid, "Maaf, database sedang gangguan.")
        return
    
    if not results or not results['ids'][0]:
        send_wpp_text(remote_jid, f"🙏 Maaf {sender_name}, tidak ditemukan jawaban untuk: *'{clean_query}'*.")
        return

    meta = results['metadatas'][0][0]
    dist = results['distances'][0][0]
    score = max(0, (1 - dist) * 100)
    
    reply_prefix = f"🤖 *FAQ Assistant* ({score:.0f}%)\n\n" if score >= 60 else f"🤔 Kurang yakin ({score:.0f}%):\n\n"
    judul = meta['judul']
    jawaban_raw = meta['jawaban_tampil']
    
    # Parsing Gambar
    raw_paths = meta.get('path_gambar', 'none')
    img_db_list = []
    if raw_paths and str(raw_paths).lower() != 'none':
        img_db_list = [p.strip().replace("\\", "/") for p in raw_paths.split(';')]

    list_gambar_to_send = []
    def replace_tag(match):
        try:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(img_db_list):
                list_gambar_to_send.append(img_db_list[idx])
                return f"*( 👇 Lihat Gambar {idx+1} )*"
            return ""
        except: return ""

    jawaban_processed = re.sub(r'\[GAMBAR\s*(\d+)\]', replace_tag, jawaban_raw, flags=re.IGNORECASE)
    if not list_gambar_to_send and img_db_list: list_gambar_to_send = img_db_list

    final_text = f"{reply_prefix}❓ *{judul}*\n✅ {jawaban_processed}"
    if meta.get('sumber_url'): final_text += f"\n🔗 {meta.get('sumber_url')}"

    send_wpp_text(remote_jid, final_text)
    for i, img in enumerate(list_gambar_to_send):
        send_wpp_image(remote_jid, img, caption=f"Gambar #{i+1}")

@app.post("/webhook")
async def wpp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        event = body.get("event")
        
        # --- DEBUG RAW JSON (KUNCI DIAGNOSA) ---
        # Ini akan memunculkan SEMUA isi data yang dikirim WPPConnect
        # Kalau masih error, copy log bagian ini dan kasih ke saya
        log(f"📦 [RAW JSON]: {json.dumps(body)}")

        if event not in ["onMessage", "onAnyMessage", "onmessage"]:
            return {"status": "ignored_event"}

        data = body.get("data", {})
        
        # Cek Data Diri Sendiri
        if data.get("fromMe", False) is True:
            return {"status": "ignored_self"}

        # --- SMART PARSER (Mencari nomor HP di berbagai lokasi) ---
        remote_jid = data.get("from")
        if not remote_jid: remote_jid = data.get("chatId")
        if not remote_jid: remote_jid = data.get("sender", {}).get("id")
        
        if not remote_jid or "status@broadcast" in str(remote_jid): 
            return {"status": "ignored_status"}

        # --- SMART PARSER (Mencari isi pesan) ---
        message_body = data.get("body")
        if not message_body: message_body = data.get("content")
        if not message_body: message_body = data.get("caption")
        if not message_body: message_body = "" # Hindari NoneType error

        log(f"📨 [PESAN MASUK] Dari: {remote_jid} | Isi: {message_body}")

        sender_name = data.get("sender", {}).get("pushname", "User")
        is_group = data.get("isGroupMsg", False) or "@g.us" in str(remote_jid)
        has_mention = bool(data.get("mentionedJidList"))

        background_tasks.add_task(process_logic, remote_jid, sender_name, message_body, is_group, has_mention)
        return {"status": "success"}

    except Exception as e:
        log(f"❌ Webhook Error: {e}")
        return {"status": "error"}

@app.on_event("startup")
async def startup_event():
    log("🚀 Bot WA Start! Menyiapkan Token...")
    # 1. Generate Token Dulu
    generate_token()
    
    # 2. Register Webhook
    try:
        requests.post(
            f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/start-session",
            json={"webhook": "http://faq-bot:8000/webhook"},
            headers=get_headers()
        )
        log("✅ Webhook Registered.")
    except Exception as e:
        log(f"⚠️ Gagal Register Webhook: {e}")

if __name__ == "__main__":
    uvicorn.run("bot_wa:app", host="0.0.0.0", port=8000)