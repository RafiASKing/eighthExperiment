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
WA_SECRET_KEY = os.getenv("WA_SESSION_KEY", "THISISMYSECURETOKEN") 
WA_SESSION_NAME = "mysession"

# Ganti dengan IP/Domain Web V2 kamu
WEB_V2_URL = "http://43.218.92.10:8080/" 

# --- LOAD IDENTITIES DARI .ENV ---
# Pastikan di .env sudah ada: BOT_IDENTITIES=628xxx,244xxx
raw_ids = os.getenv("BOT_IDENTITIES", "")
# Ubah string jadi list, hilangkan spasi jika ada
MY_IDENTITIES = [x.strip() for x in raw_ids.split(",") if x.strip()]

# Variable Global Auth
CURRENT_TOKEN = None

# --- FUNGSI LOGGING ---
def log(message):
    print(message, flush=True)

# --- FUNGSI AUTH ---
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
        url = f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/{WA_SECRET_KEY}/generate-token"
        r = requests.post(url)
        if r.status_code in [200, 201]:
            resp = r.json()
            token = resp.get("token") or resp.get("session") 
            if not token and "full" in resp: token = resp["full"].split(":")[-1]
            if token:
                CURRENT_TOKEN = token
                log(f"✅ Berhasil Generate Token.")
            else: log(f"❌ Gagal Parse Token.")
        else: log(f"❌ Gagal Generate Token: {r.status_code}")
    except Exception as e: log(f"❌ Error Auth: {e}")

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
    if not phone or str(phone) == "None": return
    url = f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/send-message"
    is_group_msg = "@g.us" in str(phone)
    
    # UPGRADE: "Jurus Mabuk" (Double Parameter)
    # Kita taruh linkPreview di luar DAN di dalam 'options'
    # Biar versi WPPConnect manapun tetap nurut.
    payload = {
        "phone": phone, 
        "message": message, 
        "isGroup": is_group_msg,
        "linkPreview": False,   # Cara Lama (Legacy)
        "options": {
            "linkPreview": False, # Cara Baru (Standard)
            "createChat": True
        }
    }
    
    try:
        r = requests.post(url, json=payload, headers=get_headers())
        log(f"📤 Balas ke {phone}: {r.status_code}")
        if r.status_code == 401: generate_token()
    except Exception as e: log(f"❌ Error Kirim Text: {e}")

def send_wpp_image(phone, file_path, caption=""):
    if not phone: return
    url = f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/send-image"
    base64_str, _ = get_base64_image(file_path)
    if not base64_str: return
    is_group_msg = "@g.us" in str(phone)
    payload = {"phone": phone, "base64": base64_str, "caption": caption, "isGroup": is_group_msg}
    try: requests.post(url, json=payload, headers=get_headers())
    except: pass

def process_logic(remote_jid, sender_name, message_body, is_group, mentioned_list):
    log(f"⚙️ Memproses Pesan: '{message_body}' dari {sender_name} (Group: {is_group})")
    
    should_reply = False
    
    # === LOGIKA PEMISAH (GRUP vs JAPRI) ===
    if not is_group:
        # KASUS JAPRI (DM):
        # Selalu jawab! Gak perlu nunggu di-tag.
        should_reply = True
    else:
        # KASUS GRUP:
        # Harus ada keyword @faq ATAU Bot di-mention
        if "@faq" in message_body.lower():
            should_reply = True
        
        # Cek Mention ID (Support Multiple ID dari .env)
        if mentioned_list and not should_reply:
            for mentioned_id in mentioned_list:
                for my_id in MY_IDENTITIES:
                    if str(my_id) in str(mentioned_id):
                        should_reply = True
                        log(f"🔔 Saya di-tag di Grup (via ID: {my_id})! Membalas...")
                        break
                if should_reply: break
    
    if not should_reply: 
        # Kalau di grup dan ga dipanggil, diam aja.
        return

    # --- BERSIHKAN QUERY ---
    # Hapus tag @faq dan mention bot biar pencarian bersih
    clean_query = message_body.replace("@faq", "")
    for identity in MY_IDENTITIES:
        clean_query = clean_query.replace(f"@{identity}", "") 
    
    # Hapus sisa-sisa format mention (@628xxx)
    clean_query = re.sub(r'@\d+', '', clean_query).strip()

    if not clean_query:
        # Kalau cuma nge-tag doang tanpa nanya
        send_wpp_text(remote_jid, f"Halo {sender_name}, silakan ketik pertanyaan Anda.")
        return

    log(f"🔍 Mencari: '{clean_query}'")
    try:
        results = database.search_faq_for_bot(clean_query, filter_tag="Semua Modul")
    except:
        send_wpp_text(remote_jid, "Maaf, database sedang gangguan.")
        return
    
    if not results or not results['ids'][0]:
        # Footer Gagal (Clean Text)
        fail_msg = f"Maaf, tidak ditemukan hasil yang relevan untuk: '{clean_query}'\n\n"
        fail_msg += f"Silakan cari manual di: {WEB_V2_URL}"
        send_wpp_text(remote_jid, fail_msg)
        return

    meta = results['metadatas'][0][0]
    score = max(0, (1 - results['distances'][0][0]) * 100)
    
    # --- UPGRADE 2: HEADER CLEAN & OBJEKTIF ---
    if score >= 60:
        header = f"*Relevansi: {score:.0f}%*\n"
    else:
        header = f"*[Relevansi Rendah: {score:.0f}%]*\n" 

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

    # Susun Bubble Utama
    final_text = f"{header}\n"
    final_text += f"Pertanyaan / Topik:\n"
    final_text += f"*{judul}*\n\n"
    final_text += f"Jawaban / Penjelasan:\n"
    final_text += f"{jawaban_processed}"
    
    # Sumber (Clean Note)
    sumber_raw = meta.get('sumber_url')
    sumber = str(sumber_raw).strip() if sumber_raw else ""

    if len(sumber) > 3:
        if "http" in sumber.lower():
            final_text += f"\n\n\nSumber: {sumber}"
        else:
            final_text += f"\n\n\nNote: {sumber}"

    # 1. Kirim Jawaban Teks
    send_wpp_text(remote_jid, final_text)
    
    # 2. Kirim Gambar (Jika ada)
    for i, img in enumerate(list_gambar_to_send):
        time.sleep(0.5) 
        send_wpp_image(remote_jid, img, caption=f"Lampiran {i+1}")

    # --- UPGRADE 3: Footer Bubble Terpisah ---
    footer_text = "------------------------------\n"
    footer_text += "Bukan jawaban yang dimaksud?\n\n"
    footer_text += f"1. Cek FaQs dan SOPs Lengkap: {WEB_V2_URL}\n"
    footer_text += "2. Atau gunakan *kalimat lebih spesifik* beserta nama modul (ex: IGD/ED/IPD).\n"
    footer_text += "Contoh: \"Gimana cara edit obat di EMR ED Pharmacy?\""
    
    time.sleep(0.5)
    send_wpp_text(remote_jid, footer_text)

@app.post("/webhook")
async def wpp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        event = body.get("event")

        # Cek event standar
        if event not in ["onMessage", "onAnyMessage", "onmessage"]:
            return {"status": "ignored_event"}

        data = body.get("data") or body 
        
        # Abaikan pesan dari diri sendiri
        if data.get("fromMe", False) is True: return {"status": "ignored_self"}

        # Ambil ID Pengirim
        remote_jid = data.get("from") or data.get("chatId") or data.get("sender", {}).get("id")
        if not remote_jid or "status@broadcast" in str(remote_jid): return {"status": "ignored_status"}

        message_body = data.get("body") or data.get("content") or data.get("caption") or ""
        
        sender_name = data.get("sender", {}).get("pushname", "User")
        
        # Penentuan Grup vs Japri
        is_group = data.get("isGroupMsg", False) or "@g.us" in str(remote_jid)
        
        mentioned_list = data.get("mentionedJidList", [])

        background_tasks.add_task(process_logic, remote_jid, sender_name, message_body, is_group, mentioned_list)
        return {"status": "success"}

    except Exception as e:
        log(f"❌ Webhook Error: {e}")
        return {"status": "error"}

@app.on_event("startup")
async def startup_event():
    log(f"🚀 Bot WA Start! Identities Loaded: {len(MY_IDENTITIES)}")
    generate_token()
    try:
        requests.post(
            f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/start-session",
            json={"webhook": "http://faq-bot:8000/webhook"},
            headers=get_headers()
        )
    except: pass

if __name__ == "__main__":
    uvicorn.run("bot_wa:app", host="0.0.0.0", port=8000)