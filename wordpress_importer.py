import requests
import os
import re
import json
import datetime
import time # Untuk menambahkan delay pada retry
import google.generativeai as genai
from google.generativeai import GenerativeModel

# --- Konfigurasi ---
# Gunakan GitHub Secrets untuk WORDPRESS_BLOG_ID agar lebih aman
BLOG_ID = os.environ.get('WORDPRESS_BLOG_ID', '143986468') 
API_BASE_URL = f"https://public-api.wordpress.com/rest/v1.1/sites/{BLOG_ID}/posts"
POST_DIR = '_posts'
STATE_FILE = 'published_posts.json' # File untuk melacak postingan yang sudah diterbitkan

# Konfigurasi Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY belum diatur di variabel lingkungan. Harap atur di GitHub Secrets.")

genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL = GenerativeModel('gemini-1.5-flash') # Menggunakan model yang terbukti jalan

os.makedirs(POST_DIR, exist_ok=True)

# --- Penggantian Kata Khusus ---
REPLACEMENT_MAP = {
    "memek": "serambi lempit",
    "kontol": "rudal",
    "ngentot": "menggenjot",
    "vagina": "serambi lempit",
    "penis": "rudal",
    "seks": "bercinta",
    "mani": "kenikmatan",
    "sex": "bercinta"
}

# === Utilitas ===
def strip_html_and_divs(html):
    """
    Menghapus sebagian besar tag HTML, kecuali yang esensial,
    dan mengganti </p> dengan dua newline untuk pemisahan paragraf.
    """
    html_with_newlines = re.sub(r'</p>', r'\n\n', html, flags=re.IGNORECASE)
    html_no_images = re.sub(r'<img[^>]*>', '', html_with_newlines)
    html_no_divs = re.sub(r'</?div[^>]*>', '', html_no_images, flags=re.IGNORECASE)
    clean_text = re.sub('<[^<]+?>', '', html_no_divs)
    clean_text = re.sub(r'\n{3,}', r'\n\n', clean_text).strip()
    return clean_text

def remove_anchor_tags(html_content):
    """Menghapus tag <a> tetapi mempertahankan teks di dalamnya."""
    return re.sub(r'<a[^>]*>(.*?)<\/a>', r'\1', html_content)

def sanitize_filename(title):
    """
    Membersihkan judul untuk digunakan sebagai nama file Jekyll.
    Penggantian kata khusus sudah diasumsikan telah diterapkan pada judul sebelum memanggil fungsi ini.
    """
    clean_title = re.sub(r'[^\w\s-]', '', title).strip().lower()
    return re.sub(r'[-\s]+', '-', clean_title)

def replace_custom_words(text):
    """
    Mengganti kata-kata spesifik dalam teks dengan padanan yang ditentukan,
    termasuk jika ada imbuhan yang menempel.
    """
    processed_text = text
    # Mengubah urutan penggantian dari yang lebih panjang ke yang lebih pendek
    sorted_replacements = sorted(REPLACEMENT_MAP.items(), key=lambda item: len(item[0]), reverse=True)
    
    for old_word, new_word in sorted_replacements:
        # Menghilangkan \b (word boundary) agar penggantian berlaku juga untuk imbuhan
        pattern = re.compile(re.escape(old_word), re.IGNORECASE)
        processed_text = pattern.sub(new_word, processed_text)
    return processed_text

# --- Gemini AI Integration ---
def paraphrase_text_with_gemini(text_content, max_retries=5, chunk_size=3000, retry_delay=5): # Max retries ditingkatkan, ada delay
    """
    Melakukan paraphrase teks menggunakan Gemini AI, memecah teks menjadi chunk jika terlalu panjang,
    dan mengatur alur dinamis agar artikel unik dan tidak terdeteksi sebagai duplikat.
    """
    if not text_content or text_content.strip() == "":
        print("Skipping paraphrase: text content is empty.")
        return ""

    chunks = []
    current_chunk = []
    current_length = 0
    
    # Memisahkan berdasarkan dua newline untuk paragraf
    paragraphs = text_content.split('\n\n') 

    for para in paragraphs:
        # Cek jika paragraf saat ini akan melebihi chunk_size
        if current_length + len(para) + 2 > chunk_size and current_chunk: # +2 untuk '\n\n'
            chunks.append('\n\n'.join(current_chunk))
            current_chunk = [para]
            current_length = len(para)
        else:
            current_chunk.append(para)
            current_length += len(para) + 2 # Tambah panjang paragraf dan pemisah

    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    paraphrased_chunks = []
    print(f"Jumlah bagian teks yang akan diparafrase: {len(chunks)}")

    for i, chunk in enumerate(chunks):
        # Prompt yang dimodifikasi untuk gaya informal dan tanpa sastra
        prompt = (
            "Parafrase ulang teks berikut agar jadi unik dan tidak terdeteksi duplikat. "
            "Gunakan bahasa yang **santai, informal, dan mudah dimengerti**, seperti obrolan sehari-hari. "
            "**Hindari diksi atau gaya bahasa yang puitis, kiasan, atau terlalu sastra.** "
            "Pastikan semua informasi dan fakta penting tetap ada dan alur cerita asli tidak berubah. "
            "Pertahankan struktur paragraf dan sub-judul (jika ada). "
            "Teks asli:\n\n"
            f"'{chunk}'" # Menggunakan chunk di sini
        )
        
        retries = 0
        while retries < max_retries:
            try:
                print(f"Memproses parafrase bagian {i+1}/{len(chunks)}... (Percobaan {retries+1}/{max_retries})")
                response = GEMINI_MODEL.generate_content(prompt)
                
                if response and response.text:
                    paraphrased_chunks.append(response.text.strip())
                    break # Berhasil, keluar dari loop retry
                else:
                    print(f"⚠️ Respon kosong dari Gemini untuk bagian {i+1}. Menunggu {retry_delay} detik sebelum mencoba lagi...")
                    time.sleep(retry_delay) # Tambahkan delay
                    retries += 1
            except Exception as e:
                print(f"❌ Error saat memparafrase bagian {i+1}: {e}. Menunggu {retry_delay} detik sebelum mencoba lagi...")
                time.sleep(retry_delay) # Tambahkan delay
                retries += 1
        
        if retries == max_retries:
            print(f"🚫 Gagal memparafrase bagian {i+1} setelah {max_retries} percobaan. Menggunakan teks asli.")
            paraphrased_chunks.append(chunk) # Gunakan teks asli jika gagal

    return "\n\n".join(paraphrased_chunks)


def load_published_posts_state():
    """Memuat daftar ID postingan yang sudah diterbitkan dari state file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                # Jika file corrupt, mulai dari set kosong
                print(f"Warning: {STATE_FILE} is corrupted or empty. Starting with an empty published posts list.")
                return set()
    return set()

def save_published_posts_state(published_ids):
    """Menyimpan daftar ID postingan yang sudah diterbitkan ke state file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(list(published_ids), f)

# === Ambil semua postingan dari WordPress.com API ===
def fetch_all_and_process_posts():
    """Mengambil semua postingan dari WordPress.com API dan memprosesnya."""
    all_posts_raw = []
    offset = 0
    per_request_limit = 100

    print("📥 Mengambil semua artikel dari WordPress.com API untuk identifikasi...")

    while True:
        params = {
            'number': per_request_limit,
            'offset': offset,
            'status': 'publish',
            'fields': 'ID,title,content,excerpt,categories,tags,date'
        }
        res = requests.get(API_BASE_URL, params=params)

        if res.status_code != 200:
            raise Exception(f"Gagal mengambil data dari WordPress.com API: {res.status_code} - {res.text}. "
                            f"Pastikan BLOG_ID Anda benar dan blog Anda dapat diakses secara publik.")
            
        data = res.json()
        posts_batch = data.get("posts", [])
        total_found = data.get('found', 0)

        if not posts_batch:
            break

        all_posts_raw.extend(posts_batch)
        offset += len(posts_batch)
        if offset >= total_found:
            break
            
    processed_posts = []
    for post in all_posts_raw:
        # --- Pemrosesan Judul ---
        original_title = post.get('title', '')
        # Parafrase judul terlebih dahulu (menggunakan fungsi paraphrase yang diadaptasi)
        paraphrased_title = paraphrase_text_with_gemini(original_title, chunk_size=200) # Ukuran chunk lebih kecil untuk judul
        # Lalu terapkan penggantian kata khusus
        processed_title = replace_custom_words(paraphrased_title)
        post['processed_title'] = processed_title # Simpan judul yang sudah bersih

        # --- Pemrosesan Konten ---
        raw_content = post.get('content', '')
        clean_text_before_paraphrase = remove_anchor_tags(raw_content)
        # Menggunakan strip_html_and_divs untuk mengubah <p> menjadi \n\n
        clean_text_before_paraphrase = strip_html_and_divs(clean_text_before_paraphrase)
        
        # Parafrase konten dengan Gemini AI
        print(f"Memulai parafrase konten untuk '{processed_title}'...")
        paraphrased_content = paraphrase_text_with_gemini(clean_text_before_paraphrase)
        
        # Langsung terapkan penggantian kata khusus pada konten yang sudah diparafrase
        final_processed_text = replace_custom_words(paraphrased_content) 
        post['processed_markdown_content'] = final_processed_text

        snippet_text = final_processed_text
        post['description_snippet'] = snippet_text[:200].replace('\n', ' ').strip()
        if len(snippet_text) > 200:
            post['description_snippet'] += "..."
        processed_posts.append(post)

    return processed_posts

# === Hasilkan file Markdown untuk Jekyll ===
def generate_jekyll_markdown_post(post):
    """
    Menghasilkan satu file Markdown untuk postingan tunggal.
    Tanggal postingan akan mengikuti tanggal saat skrip dijalankan.
    """
    # Mengatur tanggal postingan ke tanggal dan waktu saat ini (lokal atau UTC)
    # Ini akan selalu menggunakan tanggal saat GitHub Action dijalankan
    post_date_obj = datetime.datetime.now(datetime.timezone.utc) 

    # Format tanggal untuk Jekyll
    jekyll_date_str = post_date_obj.strftime('%Y-%m-%d %H:%M:%S %z')

    # Gunakan judul yang sudah diproses untuk nama file
    filename_prefix = post_date_obj.strftime('%Y-%m-%d')
    # Gunakan 'processed_title' yang sudah bersih untuk permalink / nama file
    filename = f"{filename_prefix}-{sanitize_filename(post['processed_title'])}.md"
    filepath = os.path.join(POST_DIR, filename)

    categories_list = []
    tags_list = []
    if post.get('categories'):
        categories_list = [data['name'] for slug, data in post['categories'].items() if data.get('name')]
    if post.get('tags'):
        tags_list = [data['name'] for slug, data in post['tags'].items() if data.get('name')]

    author_name = "Om Sugeng"

    description_text = post.get('description_snippet', '')
    
    # Gunakan 'processed_title' untuk front matter title
    escaped_title = json.dumps(post['processed_title']) 
    escaped_description = json.dumps(description_text)
    escaped_author = json.dumps(author_name)
    
    # --- Membuat YAML Front Matter ---
    front_matter_lines = [
        "---",
        f"layout: post",
        f"title: {escaped_title}", # Judul yang sudah bersih
        f"author: {escaped_author}",
        f"date: {jekyll_date_str}", 
    ]
    if description_text:
        front_matter_lines.append(f"description: {escaped_description}")
    if categories_list:
        front_matter_lines.append(f"categories: {json.dumps(categories_list)}")
    if tags_list:
        front_matter_lines.append(f"tags: {json.dumps(tags_list)}")
    
    front_matter_lines.append("---")
    yaml_front_matter = "\n".join(front_matter_lines) + "\n\n"

    article_content = post['processed_markdown_content']

    full_markdown_content = yaml_front_matter + article_content

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(full_markdown_content)
    print(f"✅ Generated Jekyll Markdown post: {filepath}")

# === Eksekusi Utama ===
if __name__ == '__main__':
    print(f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] Starting Jekyll post generation process...")
    print("🚀 Mengambil artikel WordPress TERBARU untuk diproses.")
    print("🗓️ Tanggal postingan Jekyll akan mengikuti tanggal saat ini (saat GitHub Action dijalankan).")
    print("✨ Penggantian kata khusus diterapkan pada judul dan konten (termasuk imbuhan).")
    print("💡 Konten akan diparafrase menggunakan Gemini AI dengan gaya informal dan tanpa diksi/sastra.")
    print("✍️ Menggunakan format paragraf standar dari WordPress (tag <p> diubah jadi double newline).")
    
    try:
        # 1. Muat daftar postingan yang sudah diterbitkan
        published_ids = load_published_posts_state()
        print(f"Ditemukan {len(published_ids)} postingan yang sudah diterbitkan sebelumnya.")

        # 2. Ambil semua postingan dari API
        # PENTING: Fungsi ini sekarang akan memproses parafrase dan penggantian kata untuk SEMUA artikel yang diambil.
        # Ini dilakukan agar kita bisa memfilter mana yang BARU diproses setelah semua siap.
        all_posts = fetch_all_and_process_posts()
        print(f"Total {len(all_posts)} artikel ditemukan dari WordPress API.")

        # 3. Filter postingan yang belum diterbitkan berdasarkan ID dari file state
        unpublished_posts = [post for post in all_posts if str(post['ID']) not in published_ids]
        print(f"Ditemukan {len(unpublished_posts)} artikel yang belum diterbitkan.")
        
        if not unpublished_posts:
            print("\n🎉 Tidak ada artikel baru yang tersedia untuk diterbitkan hari ini. Proses selesai.")
            # Commit diperlukan meskipun tidak ada postingan baru, untuk push perubahan pada published_posts.json
            print("GitHub Actions akan melakukan commit jika ada perubahan pada state file (misal, pertama kali dijalankan).")
            exit()

        # 4. Urutkan postingan yang belum diterbitkan dari yang TERBARU ke TERLAMA
        # Ini memastikan kita selalu mempublikasikan artikel terbaru yang belum pernah diproses
        unpublished_posts.sort(key=lambda x: datetime.datetime.fromisoformat(x['date'].replace('Z', '+00:00')), reverse=True)

        # 5. Pilih satu postingan untuk diterbitkan hari ini (yang paling baru dari yang belum diterbitkan)
        post_to_publish = unpublished_posts[0]
        
        print(f"🌟 Menerbitkan artikel berikutnya: '{post_to_publish.get('title')}' (ID: {post_to_publish.get('ID')})")
        
        # 6. Hasilkan file Markdown untuk postingan yang dipilih
        generate_jekyll_markdown_post(post_to_publish) 
        
        # 7. Tambahkan ID postingan ke daftar yang sudah diterbitkan dan simpan state
        published_ids.add(str(post_to_publish['ID']))
        save_published_posts_state(published_ids)
        print(f"✅ State file '{STATE_FILE}' diperbarui.")
        
        print("\n🎉 Proses Selesai!")
        print(f"File Markdown untuk Jekyll sudah ada di folder: **{POST_DIR}/**")
        print("GitHub Actions akan melakukan commit dan push file-file ini ke repositori Anda.")
        print("\nAnda sekarang bisa mengandalkan Jekyll (atau GitHub Pages) untuk membangun situs Anda.")

    except Exception as e:
        print(f"❌ Terjadi kesalahan fatal: {e}")
