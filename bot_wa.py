import os
import requests
import uvicorn
import re
import base64
import mimetypes
import json
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
from src import database

# Load Environment Variables
load_dotenv()

app = FastAPI()

# --- KONFIGURASI WPPCONNECT ---
# Menggunakan settingan yang sudah terbukti jalan tadi
WA_BASE_URL = os.getenv("WA_BASE_URL", "http://wppconnect:21465")
WA_SESSION_KEY = os.getenv("WA_SESSION_KEY", "THISISMYSECURETOKEN")
WA_SESSION_NAME = "mysession"

HEADERS = {
    "Authorization": f"Bearer {WA_SESSION_KEY}",
    "Content-Type": "application/json"
}

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
    url = f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/send-message"
    payload = {"phone": phone, "message": message, "isGroup": False}
    try:
        r = requests.post(url, json=payload, headers=HEADERS)
        print(f"📤 Balas ke {phone}: {r.status_code}") # Log status kirim
    except Exception as e:
        print(f"❌ Error Kirim Text: {e}")

def send_wpp_image(phone, file_path, caption=""):
    url = f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/send-image"
    base64_str, _ = get_base64_image(file_path)
    if not base64_str: return
    payload = {"phone": phone, "base64": base64_str, "caption": caption, "isGroup": False}
    try:
        requests.post(url, json=payload, headers=HEADERS)
        print(f"🖼️ Kirim Gambar ke {phone}")
    except Exception as e:
        print(f"❌ Error Kirim Gambar: {e}")

def process_logic(remote_jid, sender_name, message_body, is_group, has_mention):
    """ LOGIKA PROSES PESAN """
    print(f"⚙️ Memproses Pesan: '{message_body}' dari {sender_name}")
    
    # Logic trigger
    should_reply = False
    if not is_group: should_reply = True
    elif has_mention or "@faq" in message_body.lower(): should_reply = True
    
    if not should_reply: 
        print("⚠️ Pesan diabaikan (Tidak memenuhi syarat trigger)")
        return

    clean_query = message_body.replace("@faq", "").strip()
    clean_query = re.sub(r'@\d+', '', clean_query).strip()

    if not clean_query:
        send_wpp_text(remote_jid, f"Halo {sender_name}, silakan ketik pertanyaanmu.")
        return

    print(f"🔍 Mencari di Database: '{clean_query}'")
    try:
        results = database.search_faq_for_bot(clean_query, filter_tag="Semua Modul")
    except Exception as e:
        print(f"❌ Database Error: {e}")
        send_wpp_text(remote_jid, "Maaf, database sedang gangguan.")
        return
    
    if not results or not results['ids'][0]:
        send_wpp_text(remote_jid, f"🙏 Maaf {sender_name}, tidak ditemukan jawaban untuk: *'{clean_query}'*.")
        return

    meta = results['metadatas'][0][0]
    # Handle distance calculation correctly
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
        
        # Filter Event: Terima onMessage ATAU onAnyMessage
        if event not in ["onMessage", "onAnyMessage"]:
            # Abaikan event sampah (biar log gak penuh)
            return {"status": "ignored_event"}

        data = body.get("data", {})
        
        # Cek Data Diri Sendiri
        if data.get("fromMe", False) is True:
            print("🚫 Pesan dari diri sendiri (diabaikan)")
            return {"status": "ignored_self"}

        # Ambil Data Pengirim
        remote_jid = data.get("from")
        if not remote_jid: remote_jid = data.get("chatId")

        # Cek Broadcast
        if "status@broadcast" in str(remote_jid): return {"status": "ignored_status"}

        # Ambil Body Pesan
        message_body = data.get("body", "") or data.get("content", "") or data.get("caption", "")
        
        # DEBUG: Print isi pesan yang diterima
        print(f"📨 [PESAN MASUK] Dari: {remote_jid} | Isi: {message_body}")

        sender_name = data.get("sender", {}).get("pushname", "User")
        is_group = data.get("isGroupMsg", False) or "@g.us" in str(remote_jid)
        
        has_mention = False
        if data.get("mentionedJidList"): has_mention = True

        # Eksekusi Logic
        background_tasks.add_task(process_logic, remote_jid, sender_name, message_body, is_group, has_mention)
            
        return {"status": "success"}

    except Exception as e:
        print(f"❌ Webhook Error Fatal: {e}")
        return {"status": "error"}

@app.on_event("startup")
async def startup_event():
    print("🚀 Bot WA Siap! Menunggu pesan...")
    # Trigger start session (optional, just to be safe)
    try:
        requests.post(
            f"{WA_BASE_URL}/api/{WA_SESSION_NAME}/start-session",
            json={"webhook": "http://faq-bot:8000/webhook"},
            headers=HEADERS
        )
    except: pass

if __name__ == "__main__":
    uvicorn.run("bot_wa:app", host="0.0.0.0", port=8000)