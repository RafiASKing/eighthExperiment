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

# Variable Global
CURRENT_TOKEN = None
# --- UPDATE DI SINI: NOMOR BOT HARDCODED ---
# Agar logika filter mention langsung jalan tanpa perlu fetch ke API
MY_NUMBER = "6281311933544"

# --- FUNGSI LOGGING ---
def log(message):
    print(message, flush=True)

# --- FUNGSI AUTH & IDENTITY ---
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
                # Kita tetap coba fetch data terbaru, tapi kalau gagal, kita pakai MY_NUMBER yg hardcoded
                fetch_my_number()
            else: log(f"❌ Gagal Parse Token.")
        else: log(f"❌ Gagal Generate Token: {r.status_code}")
    except Exception as e: log(f"❌ Error Auth: {e}")

def fetch_my_number():
    global MY_NUMBER
    try:
        # Minta info device ke WPPConnect
        url = f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/host-device"
        r = requests.get(url, headers=get_headers())
        if r.status_code == 200:
            data = r.json().get("response", {})
            wid = data.get("wid", {}).get("user")
            if wid:
                MY_NUMBER = wid
                log(f"🤖 Bot mengenali dirinya (Updated from API): {MY_NUMBER}")
            else:
                log(f"⚠️ API Fetch kosong. Menggunakan nomor hardcoded: {MY_NUMBER}")
        else:
            log(f"⚠️ Gagal fetch host-device ({r.status_code}). Menggunakan nomor hardcoded: {MY_NUMBER}")
    except Exception as e:
        log(f"⚠️ Error fetch identity: {e}. Menggunakan nomor hardcoded: {MY_NUMBER}")

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
    payload = {"phone": phone, "message": message, "isGroup": is_group_msg}
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
    log(f"⚙️ Memproses Pesan: '{message_body}' dari {sender_name}")
    
    should_reply = False
    
    if not is_group:
        # Chat Pribadi: Selalu balas
        should_reply = True
    else:
        # Grup Logic
        # 1. Cek keyword global
        if "@faq" in message_body.lower():
            should_reply = True
        
        # 2. Cek apakah saya (Bot) di-tag
        # Logic: Cek apakah MY_NUMBER (62813...) ada di dalam salah satu ID yang dimention
        if mentioned_list:
            for mentioned_id in mentioned_list:
                if str(MY_NUMBER) in str(mentioned_id):
                    should_reply = True
                    log("🔔 Saya di-tag! Membalas...")
                    break
            
            if not should_reply:
                log(f"⚠️ Ada tag di grup, tapi bukan ke saya ({MY_NUMBER}). Cuekin.")
        
        if not should_reply and not mentioned_list:
             log("⚠️ Chat grup biasa tanpa tag/keyword. Cuekin.")

    if not should_reply: return

    # --- PROSES DATABASE ---
    clean_query = message_body.replace("@faq", "").strip()
    clean_query = re.sub(r'@\d+', '', clean_query).strip()

    if not clean_query:
        send_wpp_text(remote_jid, f"Halo {sender_name}, ada yang bisa dibantu?")
        return

    log(f"🔍 Mencari: '{clean_query}'")
    try:
        results = database.search_faq_for_bot(clean_query, filter_tag="Semua Modul")
    except:
        send_wpp_text(remote_jid, "Maaf, database gangguan.")
        return
    
    if not results or not results['ids'][0]:
        send_wpp_text(remote_jid, f"🙏 Tidak ditemukan jawaban untuk: *'{clean_query}'*.")
        return

    meta = results['metadatas'][0][0]
    score = max(0, (1 - results['distances'][0][0]) * 100)
    
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

        if event not in ["onMessage", "onAnyMessage", "onmessage"]:
            return {"status": "ignored_event"}

        data = body.get("data") or body 
        
        if data.get("fromMe", False) is True: return {"status": "ignored_self"}

        remote_jid = data.get("from") or data.get("chatId") or data.get("sender", {}).get("id")
        if not remote_jid or "status@broadcast" in str(remote_jid): return {"status": "ignored_status"}

        message_body = data.get("body") or data.get("content") or data.get("caption") or ""
        
        log(f"📨 [PESAN MASUK] Group: {'@g.us' in str(remote_jid)} | Isi: {message_body}")

        sender_name = data.get("sender", {}).get("pushname", "User")
        is_group = data.get("isGroupMsg", False) or "@g.us" in str(remote_jid)
        
        mentioned_list = data.get("mentionedJidList", [])

        background_tasks.add_task(process_logic, remote_jid, sender_name, message_body, is_group, mentioned_list)
        return {"status": "success"}

    except Exception as e:
        log(f"❌ Webhook Error: {e}")
        return {"status": "error"}

@app.on_event("startup")
async def startup_event():
    log(f"🚀 Bot WA Start! Identity Hardcoded: {MY_NUMBER}")
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