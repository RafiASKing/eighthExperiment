# Gunakan Python versi ringan
FROM python:3.10-slim

# Set folder kerja
WORKDIR /app

# [TAMBAHAN PENTING] Install build tools untuk ChromaDB & SQLite
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements dan install dulu (biar caching jalan)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kode proyek
COPY . .

# Buka port Streamlit
EXPOSE 8501

# Command jalanin aplikasi (Kita pakai app user sebagai default)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]