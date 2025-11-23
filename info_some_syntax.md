Menurut dokumentasi terbaru Streamlit, penggunaan parameter yang benar adalah width="stretch". 
use_container_width=True sudah tidak digunakan lagi (deprecated) dan akan dihapus pada rilis mendatang (setelah 31 Desember 2025). 
Berikut adalah panduan migrasi yang disarankan:
Untuk perilaku yang sebelumnya didapatkan dengan use_container_width=True, gunakan width="stretch".
Untuk perilaku yang sebelumnya didapatkan dengan use_container_width=False, gunakan width="content". 