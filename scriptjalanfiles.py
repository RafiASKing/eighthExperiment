import os

def combine_files(root_dir, output_file, extensions):
    """
    Menggabungkan file kode proyek yang relevan ke dalam satu output file.
    """
    # 1. Folder yang Harus Dikecualikan (Excluding Directories)
    # Ini akan mencegah os.walk menelusuri isi folder ini.
    EXCLUDE_DIRS = ['venv', '.git', '__pycache__', 'node_modules', 'images', 'data', '.env', 'Dokumentasi.md'] 
    
    # 2. File yang Harus Dikecualikan Meskipun Ekstensinya Cocok (Excluding Specific Files)
    # File data atau dokumen yang tidak relevan untuk LLM.
    EXCLUDE_FILES = ['faq_data.xlsx', 'scriptjalanfiles.py', 'single_script_for_llm.txt'] # scriptjalanfiles.py diabaikan agar tidak menggabungkan dirinya sendiri
    
    # 3. Ekstensi File yang Diinginkan
    FILE_EXTENSIONS = [
        '.py', '.toml', '.json', '.md', '.txt', 
        '.yml', '.yaml', # Dockerfile dan docker-compose tidak punya ekstensi, tapi .yml/yaml adalah relevan
    ] 

    with open(output_file, 'w', encoding='utf-8') as outfile:
        print(f"Memulai penggabungan file dari {root_dir}...")
        
        for root, dirs, files in os.walk(root_dir):
            
            # Modifikasi list 'dirs' agar os.walk tidak menelusuri folder yang dikecualikan
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file_name in files:
                file_path_relative = os.path.join(root, file_name)
                
                # Cek jika file ini ada di list pengecualian spesifik
                if file_name in EXCLUDE_FILES:
                    print(f"--- MENGABAIKAN: {file_path_relative} (Spesifik) ---")
                    continue
                
                # Cek apakah ekstensi file termasuk yang diinginkan
                if any(file_name.endswith(ext) for ext in FILE_EXTENSIONS):
                    
                    # Tambahan khusus: Dockerfile dan file tanpa ekstensi (seperti .env)
                    is_special_file = file_name in ['Dockerfile', 'docker-compose.yml', '.env', '.gitignore']
                    
                    if not any(file_name.endswith(ext) for ext in FILE_EXTENSIONS) and not is_special_file:
                        continue # Lewati jika bukan ekstensi yang dicari DAN bukan file spesial
                        
                    # Lanjut proses jika ekstensi cocok atau file spesial
                    header = f"======== FILE: {file_path_relative} ========\n"
                    outfile.write(header)
                    
                    try:
                        with open(file_path_relative, 'r', encoding='utf-8') as infile:
                            outfile.write(infile.read())
                        outfile.write("\n\n") # Pemisah
                        print(f"+++ BERHASIL: {file_path_relative} +++")
                        
                    except UnicodeDecodeError as e:
                        # Jika gagal decode, coba encoding lain atau error handler 'ignore'
                        print(f"!!! Peringatan: UnicodeDecodeError pada {file_path_relative}. Mencoba ignore. !!!")
                        try:
                            with open(file_path_relative, 'r', encoding='utf-8', errors='ignore') as infile:
                                outfile.write(infile.read())
                            outfile.write("\n\n")
                            print(f"+++ BERHASIL (dengan ignore): {file_path_relative} +++")
                        except Exception as inner_e:
                            print(f"!!! GAGAL: {file_path_relative} tidak dapat dibaca. Error: {inner_e}")
                            
                    except Exception as e:
                        print(f"!!! GAGAL: {file_path_relative} tidak dapat dibaca. Error: {e}")

# Konfigurasi Utama
STARTING_DIR = '.' 
OUTPUT_NAME = 'single_script_for_llm.txt'
# Note: Ekstensi yang relevan sudah ditentukan di dalam fungsi di atas

combine_files(STARTING_DIR, OUTPUT_NAME, []) # List ekstensi kosong karena filter ada di dalam fungsi
print(f"\n✅ Selesai! File gabungan '{OUTPUT_NAME}' siap untuk Vibecoding.")