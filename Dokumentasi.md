</dokumentasi_perjalanan_pengembangan>

Berikut adalah dokumen **Rekap Evolusi Teknis & Architecture Decision Record (ADR)** yang telah dirapikan. Dokumen ini menggabungkan seluruh riwayat pengembangan, mulai dari kendala awal hingga solusi "Golden Master" saat ini.

---

# 🚀 Journey of Development: Fast Cognitive Search System 

Dokumen ini merekam evolusi teknis sistem, mencakup masalah yang dihadapi, keputusan arsitektur yang diambil, dan alasan strategis di baliknya.

---

## 🧠 Bagian 1: Core Intelligence & Search Logic (Otak Sistem)

Fokus pada akurasi pencarian, efisiensi AI, dan relevansi jawaban medis.

### 1.1. Logika Filtering (Pre-Filtering vs Post-Filtering)
*   **Masalah:** Awalnya menggunakan *Post-Filtering* (Cari Top 10 global dulu, baru saring Tag).
    *   *Risiko:* Jika user mencari "Obat" tapi filter "IGD", dan Top 10 didominasi "Farmasi", hasil IGD menjadi kosong padahal datanya ada di ranking 11.
*   **Keputusan:** Implementasi **Pre-Filtering (Native ChromaDB `where` clause)**.
*   **Mekanisme:** Sistem menyaring tumpukan data berdasarkan Tag *sebelum* AI melakukan ranking semantic.
*   **Benefit:** **Akurasi 100%**. User medis dijamin menemukan data spesifik modul (misal: ED/IGD) jika data memang tersedia.

### 1.2. Penanganan Noise AI (Data Quality)
*   **Masalah:** Kode visual seperti `[GAMBAR 1]` ikut di-embed ke AI. Akibatnya, jika user mencari kata "Gambar", semua artikel muncul di ranking atas (Hallucination by Keyword).
*   **Keputusan:** Implementasi **Text Cleaner (`clean_text_for_embedding`)**.
*   **Mekanisme:** Teks yang dikirim ke Gemini dibersihkan dari tag gambar, namun tetap mempertahankan Markdown penting.
*   **Benefit:** AI murni fokus pada **konteks medis** (gejala, solusi, error code), bukan instruksi visual.

### 1.3. Latency & Performance (Caching)
*   **Masalah:** Sistem melakukan *re-run* embedding ke Google API setiap kali user mengganti filter, menyebabkan *lag* 0.5 - 1 detik dan boros kuota.
*   **Keputusan:** Implementasi **Caching Strategy (`@st.cache_data`)**.
*   **Benefit:** Pergantian filter kini **INSTANT (0 detik)** dan menghemat biaya API call secara signifikan.

### 1.4. Confidence Threshold (Pencegahan Halusinasi)
*   **Masalah:** Sistem "memaksa" memberikan jawaban meskipun user mengetik kata acak/kasar, berpotensi memberikan info medis yang salah.
*   **Keputusan:** Menambahkan **Confidence Threshold (>25%)**.
*   **Benefit:** Lebih baik sistem menjawab "Tidak ditemukan" daripada memberikan jawaban yang menyesatkan di lingkungan rumah sakit.

### 1.5. Universal Semantic Structure (Manual HyDE Strategy)
*   **Masalah:** Terjadi *Semantic Gap* (Kesenjangan Bahasa) antara User dan Dokumen.
    *   *Contoh:* User mengetik bahasa panik/slang ("Gak bisa masuk", "Tombol mati"), sedangkan Dokumen menggunakan bahasa teknis/baku ("Gagal Autentikasi", "Sistem Offline").
    *   *Risiko:* AI gagal mencocokkan keduanya karena kosa katanya terlalu berbeda, meskipun maksudnya sama.
*   **Keputusan:** Implementasi **Structured Embedding dengan Strategi HyDE (Hypothetical Document Embeddings)**.
*   **Mekanisme:**
    *   Mengubah struktur teks yang di-embed dari sekadar gabungan teks menjadi format semantik yang tegas:
        ```text
        DOMAIN: ED (IGD, Emergency)  <-- Konteks Modul + Sinonim
        DOKUMEN: Cara Login          <-- Judul Resmi
        VARIASI PERTANYAAN USER: Gak bisa masuk, Lupa password <-- Bahasa User (HyDE)
        ISI KONTEN: ...              <-- Solusi Teknis
        ```
    *   Admin diinstruksikan mengisi kolom "Keyword" dengan **variasi pertanyaan user**, bukan sekadar kata kunci kaku.
*   **Benefit:**
    1.  **Telepathic Search:** Sistem mengerti "Bahasa Lapangan" user.
    2.  **Universal Robustness:** Struktur ini agnostik (tidak terikat RS), siap digunakan untuk domain lain (Banking, HR, Logistik) tanpa ubah kodingan.

---

## 🎨 Bagian 2: User Experience (Interface & Flow)

Fokus pada kemudahan penggunaan bagi perawat/dokter dan kejelasan informasi.

### 2.1. Mengatasi "Blank Screen Syndrome"
*   **Masalah:** Saat aplikasi dibuka, layar kosong hanya berisi search bar. User baru bingung harus melakukan apa.
*   **Keputusan:** Implementasi **Browse Mode (Mode Jelajah)**.
*   **Mekanisme:** Jika search bar kosong $\rightarrow$ Tampilkan data terbaru (ID Terbesar). Jika terisi $\rightarrow$ Masuk Search Mode.
*   **Benefit:** Meningkatkan *discoverability*. User langsung melihat update SOP terbaru tanpa perlu mengetik.

### 2.2. Struktur Visual (Hybrid Inline Image)
*   **Masalah:** Gambar menumpuk di bawah teks (Galeri). Sulit dipahami untuk SOP langkah-demi-langkah.
*   **Keputusan:** Fitur **Inline Image (`[GAMBAR X]`)**.
*   **Mekanisme:** Gambar diselipkan secara natural di antara paragraf teks.
*   **Benefit:** Instruksi menjadi runut dan mudah dibaca (Teks -> Gambar -> Teks).

### 2.3. Explainable AI (Transparansi)
*   **Masalah:** User tidak tahu apakah hasil pencarian ini valid atau sekadar keyword matching.
*   **Keputusan:** Menambahkan **Confidence Score Badge**.
*   **Mekanisme:** Menampilkan persentase relevansi dengan kode warna (Hijau/Orange/Merah).
*   **Benefit:** Memberikan efek psikologis "Trust" kepada user bahwa sistem benar-benar "berpikir".

### 2.4. Navigasi & Scalability
*   **Masalah:** Menampilkan 50+ hasil sekaligus membuat UI panjang (*Infinite Scroll*) dan berat.
*   **Keputusan:** Implementasi **Pagination System** (10 item per halaman).
*   **Benefit:** UI bersih, ringan, dan terlihat profesional.

### 2.5. Visual Consistency (Single Source of Truth)
*   **Masalah:** Awalnya warna badge (label kategori) di-hardcode di dalam script.
    *   *Risiko 1:* Jika Admin ingin mengubah warna "IGD" dari Merah ke Biru, harus memanggil programmer untuk edit kode.
    *   *Risiko 2:* Tanpa pembatasan, Admin mungkin memilih warna yang merusak kontras (misal: teks putih di background kuning terang).
*   **Keputusan:** Implementasi **Dynamic JSON Configuration (`tags_config.json`)** dengan **Restricted Palette**.
*   **Mekanisme:**
    *   App User dan Admin membaca file konfigurasi yang sama di folder `data/`.
    *   Pilihan warna di Admin **dibatasi** pada palet resmi (Merah, Hijau, Biru, Orange, Ungu, Abu) yang sudah dikalibrasi agar enak dilihat.
*   **Benefit:**
    1.  **Konsistensi:** User tidak bingung dengan warna-warni liar.
    2.  **Fleksibilitas:** Admin bisa menambah/mengedit modul tanpa menyentuh satu baris kode pun.

### 2.6. Closed Loop Support (Contextual Call-to-Action)
*   **Masalah:** Pesan error "Data Tidak Ditemukan" adalah jalan buntu (*Dead End*). User frustrasi dan masalah tidak terselesaikan.
*   **Keputusan:** Integrasi **Direct Support Link (WhatsApp Bot)** pada kondisi *No Result*.
*   **Mekanisme:**
    *   Jika relevansi < 25%, sistem menampilkan tombol "Chat WhatsApp Support".
    *   **Auto-Fill Message:** Link WA otomatis terisi dengan draf pesan: *"Halo Admin, saya cari solusi tentang [Query User] tapi tidak ketemu..."*
*   **Benefit:**
    1.  **Psikologis:** User merasa "diurus" meskipun jawaban belum ada di database.
    2.  **Ticket Automation:** Tim IT langsung mendapat laporan spesifik tentang apa yang dicari user, mempercepat perbaikan konten (Feedback Loop Aktif).

---

## 🛠️ Bagian 3: Admin Workflow & Operations

Fokus pada keamanan data, kemudahan input, dan feedback loop.

### 3.1. Zero-Error Input Workflow
*   **Masalah:** Admin melakukan *Blind Input* (Langsung Save tanpa tahu hasil jadinya), rawan typo format.
*   **Keputusan:** Menambahkan **Preview Mode** sebelum Submit.
*   **Benefit:** Admin bisa memvalidasi tampilan visual sebelum data dipublish ke User.

### 3.2. Smart Typing Experience
*   **Masalah:** Admin harus mengetik kode `[GAMBAR 1]` secara manual. Rawan salah ketik dan melelahkan.
*   **Keputusan:** Implementasi **Smart Toolbar (📸 Auto-Counter)**.
*   **Mekanisme:** Satu tombol pintar yang otomatis menghitung urutan gambar dan menyisipkan tag yang sesuai.
*   **Benefit:** UX *Don't make me think*. Mempercepat proses input data hingga 2x lipat.

### 3.3. Data Safety (Anti-Amnesia)
*   **Masalah:** Jika Admin menekan tombol "Edit Lagi" atau reload, data yang sudah diketik hilang.
*   **Keputusan:** Implementasi **Session State Draft**.
*   **Benefit:** Menjaga *mental state* admin. Data input persisten sampai benar-benar disimpan.

### 3.4. Feedback Loop (Analytics)
*   **Masalah:** Admin tidak tahu apa yang dicari user namun belum ada jawabannya di database.
*   **Keputusan:** Fitur **Log Pencarian Gagal (Analytics Tab)**.
*   **Benefit:** *Data Driven Development*. Admin membuat konten baru berdasarkan kebutuhan riil di lapangan.

### 3.5. Maintenance (Zombie Cleaner)
*   **Masalah:** Menghapus data di database tidak menghapus file gambar di folder server (Storage Leak).
*   **Keputusan:** Logic **Deep Delete** (Hapus DB = Hapus File Fisik).
*   **Benefit:** Server tetap bersih dari file sampah (*maintenance free*).

---

## 🏗️ Bagian 4: Architecture & Robustness

Fokus pada fondasi teknis, keamanan, dan deployment.

### 4.1. Security Standard
*   **Masalah:** API Key dan Password hardcoded di dalam script. Berisiko tinggi jika source code bocor.
*   **Keputusan:** Migrasi ke **Environment Variables (`.env`)**.
*   **Benefit:** Memenuhi standar keamanan Enterprise.

### 4.2. Code Structure (Modularity)
*   **Masalah:** Kode awal berupa *Spaghetti Code* (semua dalam satu file).
*   **Keputusan:** Refactoring ke struktur **Modular** (`src/database`, `src/utils`, `src/config`).
*   **Benefit:** Mudah dibaca, mudah di-maintenance, dan siap untuk migrasi ke framework lebih besar (FastAPI) di masa depan.

### 4.3. Concurrency Handling
*   **Masalah:** Database SQLite sering *crash* ("Locked") jika diakses banyak user bersamaan.
*   **Keputusan:** Implementasi **`@retry_on_lock` Decorator dengan Jitter**.
*   **Benefit:** Sistem menjadi *robust* (tahan banting) menangani antrian request tanpa perlu setup database server yang berat.

---

## 📱 Bagian 5: Omnichannel Expansion (WhatsApp Integration)

Fokus pada perluasan aksesibilitas sistem agar bisa dijangkau oleh staf medis melalui HP tanpa perlu login komputer.

### 5.1. Decoupled Architecture (Microservice Approach)
*   **Masalah:** Awalnya logika pencarian terikat erat (*tightly coupled*) di dalam `app.py` Streamlit. Membuat skrip Bot WA terpisah menjadi mustahil karena error dependency `streamlit` context.
*   **Keputusan:** Refactoring `database.py` menjadi pola **Hybrid Access**.
*   **Mekanisme:**
    1.  **Raw Logic Layer:** Fungsi murni Python untuk koneksi DB & Embedding (tanpa cache). Digunakan oleh Bot WA.
    2.  **Cached Wrapper Layer:** Membungkus Raw Logic dengan `@st.cache_data`. Digunakan oleh Web App untuk performa.
*   **Benefit:** **Code Reusability**. Satu otak (core logic) dipakai oleh dua tubuh (Web & WA) secara simultan tanpa konflik.

### 5.2. Context-Aware Group Logic (Etika Robot)
*   **Masalah:** Saat bot dimasukkan ke Grup WA RS, bot menjawab *semua* chat yang masuk (termasuk percakapan santai), menyebabkan SPAM.
*   **Keputusan:** Implementasi **Selective Trigger Logic**.
*   **Mekanisme:**
    *   **Private Chat:** Bot selalu menjawab.
    *   **Group Chat:** Bot **DIAM** kecuali dipanggil (Mention `@Bot`, `@628...`, atau keyword `min/tolong/tanya`).
*   **Benefit:** **User Experience yang Sopan**. Bot tidak mengganggu dinamika grup manusia, hanya muncul saat dibutuhkan.

### 5.3. Gateway Strategy (Hackathon Speed)
*   **Masalah:** Menggunakan WhatsApp Official API (BSP) membutuhkan verifikasi bisnis Meta (Facebook) yang memakan waktu 24-48 jam. Tidak kekejar untuk deadline lomba.
*   **Keputusan:** Menggunakan **Unofficial Gateway (Fonnte) + Webhook**.
*   **Mekanisme:** Fonnte bertindak sebagai "Jembatan" yang meneruskan pesan WA ke server backend (Python FastAPI) via HTTP POST.
*   **Benefit:** **Instant Deployment**. Bot bisa hidup dalam hitungan menit tanpa birokrasi legalitas.

---

## 🧠 Bagian 6: Adaptive Intelligence Configuration

Fokus pada fleksibilitas logika AI tanpa perlu mengubah kode sumber (Hardcoding).

### 6.1. Dynamic Thresholding (Environment Variables)
*   **Masalah:** Menentukan seberapa "Pede" bot menjawab (Score > 80%?) atau seberapa "Beda" jawaban 1 dan 2 (Gap > 10%?) adalah angka subjektif. Jika di-hardcode, mengubahnya butuh restart/deploy ulang.
*   **Keputusan:** Memindahkan parameter logika ke **Environment Variables (`.env`)**.
    *   `BOT_MIN_SCORE`: Batas minimum kemiripan.
    *   `BOT_MIN_GAP`: Jarak aman antara ranking 1 dan 2.
*   **Benefit:** **Operational Agility**. Admin bisa mengubah sifat bot (dari "Galak/Pelit Jawaban" menjadi "Ramah/Mudah Menjawab") hanya dengan edit text file di server, tanpa menyentuh kodingan.

### 6.2. Trap-Keywords Strategy
*   **Masalah:** User sering menyimpan nomor bot dengan nama acak (misal: "Robot RS", "Si Pinter"). Logika deteksi mention `@628...` sering gagal.
*   **Keputusan:** Implementasi **Generic Trigger List**.
*   **Mekanisme:** Bot tidak hanya mendeteksi nomor HP-nya sendiri, tapi juga bereaksi pada kata kunci sosial: *"Admin", "Min", "Tolong", "Tanya", "Help"*.
*   **Benefit:** **High Availability**. Bot tetap responsif meskipun user tidak tahu cara mention yang benar.

---

## 🌐 Bagian 7: Connectivity & Deployment

### 7.1. Tunneling for POC (Ngrok)
*   **Masalah:** Mendemokan integrasi WhatsApp (Internet Public) ke Server Laptop (Localhost) tidak bisa dilakukan secara langsung karena terhalang NAT/Firewall.
*   **Keputusan:** Menggunakan **Ngrok Secure Tunnels**.
*   **Benefit:** Memungkinkan demo **Live Real-time** kepada juri menggunakan infrastruktur laptop lokal, namun tetap terintegrasi dengan dunia luar (WhatsApp).

---

## 📊 Ringkasan: Before vs After

| Aspek | Status Awal (Before) | Status Final (Golden Master) |
| :--- | :--- | :--- |
| **Logic Search** | Post-Filter (Rawan Data Hilang) | **Pre-Filter (Akurasi 100%)** |
| **AI Context** | Tercemar Noise Visual | **Bersih (Text Cleaner)** |
| **Embedding Strategy** | Flat Text (Rawan Meleset) | **Structured HyDE (Universal & Robust)** |
| **Tampilan User** | Blank Screen & Galeri Menumpuk | **Browse Mode & Inline Image** |
| **Handling No Result** | Jalan Buntu (Pesan Error) | **Call-to-Action (WhatsApp Integration)** |
| **Admin Input** | Manual & Rawan Typo | **Smart Toolbar & Preview Mode** |
| **Keamanan** | Hardcoded Credentials | **Environment Variables (.env)** |
| **Stabilitas** | Rawan Crash (SQLite Locked) | **Robust (Retry Mechanism)** |
| **Aksesibilitas** | Web Only (Harus Login PC) | **Omnichannel (Web + WhatsApp 24/7)** |
| **Arsitektur DB** | Tightly Coupled (Streamlit Only) | **Hybrid Microservice (Web & API Ready)** |
| **Logika WA** | Spammy (Jawab Semua) | **Context-Aware (Sopan di Grup)** |
| **Config AI** | Hardcoded di Python | **Dynamic Config (.env)** |
| **Trigger Bot** | Kaku (@Nomor) | **Fleksibel (Natural Language Triggers)** |

### 🗺️ Arsitektur Sistem Final

```mermaid
graph TD
    UserWA[User WhatsApp] -->|Chat| WA_Server[WhatsApp Server]
    WA_Server -->|Push| Fonnte[Fonnte Gateway]
    Fonnte -->|Webhook POST| Ngrok[Ngrok Tunnel]
    Ngrok -->|Forward| FastAPI[Bot Service (FastAPI)]
    
    UserWeb[User Browser] -->|HTTP| Streamlit[Web App (Streamlit)]
    
    FastAPI -->|Raw Query| ChromaDB[(Vector Database)]
    Streamlit -->|Cached Query| ChromaDB
    
    ChromaDB <-->|Embedding| GeminiAI[Google Gemini API]
```

### ✅ Status Sistem Saat Ini
Sistem telah berevolusi dari sekadar *Prototype* menjadi aplikasi **Production-Ready** skala departemen dengan karakteristik:
1.  **High Accuracy:** Logika pencarian yang matang.
2.  **User Centric:** Interface yang memandu user.
3.  **Low Maintenance:** Fitur pembersihan otomatis dan logging.
4.  **Secure:** Pemisahan kredensial dari kode.

</dokumentasi_perjalanan_pengembangan>

<dokumentasi_perjalanan_pengembangan_setelahnya_lagi>
# 📑 Technical Incident Report: Vector Database State Desynchronization

**Tanggal:** 24 November 2025  
**Komponen:** ChromaDB (Local Persistence)  
**Tipe Error:** `chromadb.errors.InternalError: Error finding id`  
**Status Akhir:** ✅ **RESOLVED (Recovered via Service Restart)**

---

## 1. Deskripsi Insiden (What Happened)
Saat dilakukan pengujian sistem (User Search), aplikasi mengalami kegagalan fungsi dengan gejala:
1.  **Search Freeze:** Hasil pencarian mengembalikan dokumen yang sama berulang-ulang (*stuck results*) atau crash total.
2.  **Error Log:** Muncul pesan `InternalError: Error finding id`, mengindikasikan kegagalan sistem dalam mencocokkan ID dari *Vector Index* ke *Metadata Store*.
3.  **Partial Availability:** Panel Admin (CRUD) tetap dapat diakses dan menampilkan data tabel dengan normal, menandakan kerusakan tidak bersifat total pada layer penyimpanan data teks (SQLite).

## 2. Tindakan Perbaikan (Resolution)
Dilakukan **Service Restart** (bukan penghapusan data):
*   **Command:** `docker compose down` diikuti `docker compose up --build`.
*   **Hasil:** Sistem kembali normal. Error hilang, dan fungsi pencarian berjalan akurat kembali. Tidak ditemukan kehilangan data mayor.

---

## 3. Analisis Teknis (Technical Analysis)

Berdasarkan fakta bahwa sistem pulih hanya dengan *restart*, berikut adalah diagnosis teknis mendalam:

### A. Hipotesis Utama: In-Memory Index Desynchronization (Probabilitas ~90%)
Penyebab paling logis adalah ketidakcocokan antara **State Aplikasi di RAM** dengan **Data Persisten di Disk**.

1.  **Stale Memory State:**
    ChromaDB memuat struktur grafik pencarian (HNSW Index) ke dalam RAM (Memori) agar cepat. Saat terjadi *glitch* (misal: koneksi terputus saat *writing* atau *race condition*), representasi index di RAM menjadi "kotor" atau tidak valid, sementara file fisik di harddisk sebenarnya masih aman.
    *   *Gejala:* Aplikasi di RAM mencoba mengakses ID yang menurutnya ada, tapi saat dicek ke Disk, ID tersebut tidak valid/terkunci.

2.  **Zombie File Locks:**
    Proses Docker sebelumnya mungkin tidak melepaskan "kunci" (lock) pada file database secara sempurna. Akibatnya, proses baru tidak bisa membaca index, menyebabkan error `Error finding id`.

    **Mengapa Restart Berhasil?**
    Restart container memaksa OS untuk:
    *   Membersihkan memori (RAM) yang korup/kotor.
    *   Memutus paksa semua *File Locks* yang nyangkut.
    *   Memuat ulang (Reload) index bersih dari Disk ke RAM.

### B. Hipotesis Sekunder: Minor Uncommitted Transaction (Probabilitas ~10%)
Ada kemungkinan kecil terjadi kegagalan pada transaksi terakhir (*Last Write Lost*).

*   Karena ChromaDB menggunakan SQLite dengan mode WAL (*Write-Ahead Logging*), transaksi yang belum tuntas saat terjadi crash mungkin dibatalkan (*Rollback*) secara otomatis saat sistem dinyalakan kembali.
*   **Dampak:** Database selamat dan sehat, namun 1-2 baris data terakhir yang diinput tepat sebelum crash mungkin hilang (tidak tersimpan). Hal ini dianggap *acceptable risk* dibandingkan kerusakan total database.

---

## 4. Kesimpulan & Justifikasi (Verdict)

Keputusan untuk **TIDAK menghapus database** dan hanya melakukan restart terbukti tepat karena:

1.  **Integritas Data Fisik:** Kerusakan hanya terjadi pada level *Runtime Application* (Memori), bukan pada *Physical Storage* (Disk).
2.  **ACID Compliance:** Sistem database (SQLite) berhasil menjalankan mekanisme *Recovery* saat startup, menjaga konsistensi data.

**Catatan untuk Dokumentasi:**
Insiden ini mengonfirmasi bahwa arsitektur sistem memiliki tingkat **Resiliensi (Ketahanan)** yang cukup baik terhadap gangguan sesaat (*transient faults*), namun operator harus waspada terhadap potensi hilangnya data transaksi terakhir (*last committed data*) jika terjadi crash saat proses simpan.

</dokumentasi_perjalanan_pengembangan_setelahnya_lagi>


</dokumentasi_perjalanan_pengembangan_setelahnya_lagi2>
Saat ini saya menggunakan mode **Embedded (Local File)**.
*   **Kelebihan:** Cepat, tanpa setup server, tinggal import library python.
*   **Kelemahan:** **Tidak didesain untuk multi-container.** Saat Admin (Container A) mau nulis, dan User (Container B) mau baca file yang sama secara bersamaan, OS akan bilang "STOP! File lagi dipake!", lalu terjadilah crash atau corruption tadi.

---

### 🚀 Solusi "Production Grade": Migrasi ke Client-Server Mode

Untuk memperbaiki ini **SECARA PERMANEN** (biar mau dihajar 100 user + 1 admin ngedit barengan gak akan crash), kita harus memisahkan Database ke Container sendiri.

Ini adalah standar industri. **Admin dan User App tidak boleh pegang file database langsung.** Mereka harus ngomong via API ke "Server Database".

Apakah kamu berani mengubah struktur `docker-compose` dan `database.py` sedikit? Kalau iya, ini fix permanennya.

### Langkah 1: Ubah `docker-compose.yml`
Tambahkan service baru bernama `chromadb` (ini server databasenya). Dan pastikan service lain terhubung ke network yang sama.

Ubah file `docker-compose.yml` kamu jadi seperti ini (saya kasih tanda bagian barunya):

```yaml
version: '3'

services:
  # --- SERVICE BARU: DATABASE SERVER ---
  chroma-server:
    image: chromadb/chroma:latest
    container_name: faq_chroma_db
    restart: always
    ports:
      - "8005:8000"
    volumes:
      # Data disimpan di sini, aman terkelola server
      - ./data/chroma_data:/chroma/chroma 
    environment:
      - IS_PERSISTENT=TRUE
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3

  # --- SERVICE 1: USER APP ---
  faq-user:
    build: .
    # ... (settingan lain sama)
    depends_on:
      - chroma-server # Tunggu DB nyala dulu
    environment:
      - CHROMA_HOST=chroma-server # Kasih tau alamat server DB
      - CHROMA_PORT=8000

  # --- SERVICE 2: ADMIN APP ---
  faq-admin:
    build: .
    # ... (settingan lain sama)
    depends_on:
      - chroma-server
    environment:
      - CHROMA_HOST=chroma-server
      - CHROMA_PORT=8000

  # --- SERVICE 3: BOT WA ---
  faq-bot:
    build: .
    # ... (settingan lain sama)
    depends_on:
      - chroma-server
    environment:
      - CHROMA_HOST=chroma-server
      - CHROMA_PORT=8000
```

*(Jangan lupa tambahkan `env_file: .env` di service user/admin/bot seperti biasa)*.

### Langkah 2: Ubah `src/database.py`
Sekarang kita ubah cara connect-nya. Dari "Baca File" jadi "Panggil Server".

Buka `src/database.py`, ubah fungsi `_get_db_client_raw`:

```python
# Import os di paling atas
import os

# ...

def _get_db_client_raw():
    """
    Membuat koneksi ke ChromaDB.
    Cek apakah ada Environment Variable CHROMA_HOST.
    Jika ada -> Pakai Mode Client-Server (Production Stable).
    Jika tidak -> Pakai Mode Local File (Fallback).
    """
    host = os.getenv("CHROMA_HOST")
    port = os.getenv("CHROMA_PORT")

    if host and port:
        # MODE PRODUCTION (STABIL) 🚀
        # Menggunakan HttpClient untuk ngobrol sama Container sebelah
        return chromadb.HttpClient(host=host, port=int(port))
    else:
        # MODE LAMA (RAWAN CRASH) ⚠️
        return chromadb.PersistentClient(path=DB_PATH)
```

### Langkah 3: Bersih-bersih & Restart
Karena struktur databasenya berubah (dari file `faq_db` lokal jadi dikelola server chroma), kamu harus **Input Ulang Data** (atau migrasi ribet, tapi mending input ulang biar bersih).

1.  Matikan Docker: `docker compose down`
2.  Hapus folder `data/faq_db` (Data lama yang format file lokal).
3.  Nyalakan dengan struktur baru: `docker compose up --build -d`

---

### ⚖️ Pertimbangan buat Kamu (Mepet Lomba)

**Apakah ini *Worth It* dilakukan sekarang?**

*   **JIKA IYA (Pindah ke Server Mode):**
    *   ✅ **Crash Hilang 100%:** Server ChromaDB yang ngatur antrian. Admin Save + User Search barengan? Gak masalah.
    *   ✅ **Performance:** Lebih cepat karena index di-handle di memori server khusus.
    *   ❌ **Effort:** Kamu harus input data ulang dari nol.

*   **JIKA TIDAK (Stay di Local Mode):**
    *   ✅ **Effort:** Gak perlu ubah kodingan dan docker.
    *   ❌ **Risiko:** Masih ada potensi crash kalau dipaksa kerja berat barengan. Tapi kalau pas demo cuma Search doang (gak ada save), sebenernya aman.

**Rekomendasi Saya:**
Kalau kamu punya waktu **2-3 jam** hari ini, **LAKUKAN MIGRASI INI.**
Ini membuat jawaban kamu ke juri soal "Scalability" jadi valid.

> *"Juri: Kalau usernya 1000 orang gimana?"*
> *"Kamu: Aman Pak, kami menggunakan arsitektur Client-Server terpisah untuk Vector Database, bukan embedded file."*

</dokumentasi_perjalanan_pengembangan_setelahnya_lagi2>




</next_pengembangan>
Fixing masalah write db, aku masih bingung mau ngelakuin yang disuruh bagian "dokumentasi_perjalanan_pengembangan_setelahnya_lagi" apa tidak?
</next_pengembangan>



Berikut untuk codesnya yang terbaru:

<kode_baru>



</kode_baru>

Kira-kira seperti ini projectku. apakah siap untuk dilombakan? tinggal 1 minggu lagi ini btw, hehe...., apa bisa gak ya aku fix masalah write db ini

