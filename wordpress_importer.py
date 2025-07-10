import requests
import os
import re
import json
import datetime
import time
import google.generativeai as genai
from bs4 import BeautifulSoup # Import BeautifulSoup4

# --- Konfigurasi ---
# Gunakan GitHub Secrets untuk WORDPRESS_BLOG_ID agar lebih aman
# Ganti '143986468' dengan ID blog WordPress Anda jika Anda menguji secara lokal tanpa secret.
BLOG_ID = os.environ.get('WORDPRESS_BLOG_ID', '143986468')
API_BASE_URL = f"https://public-api.wordpress.com/rest/v1.1/sites/{BLOG_ID}/posts"
POST_DIR = '_posts'
STATE_FILE = 'published_posts.json' # File untuk melacak postingan yang sudah diterbitkan

# --- Konfigurasi Gemini API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Pastikan API key tersedia
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set. Please set it in your GitHub Secrets or local environment.")

genai.configure(api_key=GEMINI_API_KEY)
# Menggunakan Gemini 1.5 Flash karena ini yang paling mungkin berfungsi dengan API gratis Anda
# dan optimal untuk efisiensi.
gemini_model = genai.GenerativeModel() 

# Buat folder _posts jika belum ada
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

# Fungsi untuk membersihkan HTML dan mempertahankan struktur paragraf dengan BeautifulSoup
def clean_html_to_markdown_text(html_content):
    """
    Menggunakan BeautifulSoup untuk mengurai HTML dan mengekstrak teks,
    mempertahankan pemisahan paragraf dengan double newline.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')

    # Hilangkan elemen script dan style
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()

    # Ubah tag <br> menjadi newline eksplisit
    for br_tag in soup.find_all('br'):
        br_tag.replace_with('\n')

    # Proses untuk mendapatkan teks dengan pemisahan paragraf yang baik
    output_parts = []
    # Tag-tag yang biasanya menandakan blok atau paragraf baru
    block_tags = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'ul', 'ol', 'pre', 'blockquote']

    # Jika body memiliki konten langsung tanpa tag blok, tambahkan itu
    if soup.body and isinstance(soup.body.contents[0], str):
        text = soup.body.contents[0].strip()
        if text:
            output_parts.append(text)
            output_parts.append('\n\n') # Tambahkan pemisah setelah teks langsung di body

    for element in soup.find_all(block_tags):
        text_content = element.get_text(separator=' ', strip=True) # strip=True menghapus whitespace di awal/akhir
        if text_content: # Pastikan ada konten teks
            output_parts.append(text_content)
        
        # Tambahkan double newline setelah tag blok
        # Hindari menambahkan newline berlebihan jika sudah ada di elemen berikutnya
        # Atau jika ini elemen terakhir
        if element.name in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'pre', 'blockquote']:
            # Periksa sibling berikutnya untuk menghindari double newline berlebih
            next_s = element.next_sibling
            while next_s and (next_s.name is None or next_s.name == 'br' or (isinstance(next_s, str) and next_s.strip() == '')):
                next_s = next_s.next_sibling
            
            if next_s and next_s.name in block_tags: # Jika sibling berikutnya juga tag blok, tambahkan pemisah
                 if output_parts and output_parts[-1] != '\n\n': # Pastikan tidak ada double newline berturut-turut
                     output_parts.append('\n\n')
            elif not next_s: # Jika ini elemen terakhir, tambahkan pemisah kecuali sudah ada
                if output_parts and output_parts[-1] != '\n\n':
                    output_parts.append('\n\n')
            # Jika ini bukan elemen terakhir dan sibling berikutnya bukan tag blok,
            # mungkin ini inline, jadi tidak perlu double newline.
    
    clean_text = ''.join(output_parts)
    
    # Bersihkan multiple newlines menjadi double newline saja, dan leading/trailing whitespace
    clean_text = re.sub(r'\n{2,}', '\n\n', clean_text).strip()
    
    return clean_text


def remove_anchor_tags(html_content):
    """Menghapus semua tag <a> tapi mempertahankan teks di dalamnya."""
    return re.sub(r'<a[^>]*>(.*?)<\/a>', r'\1', html_content)

def sanitize_filename(title):
    """Membersihkan judul agar cocok untuk nama file."""
    clean_title = re.sub(r'[^\w\s-]', '', title).strip().lower()
    return re.sub(r'[-\s]+', '-', clean_title)

def replace_custom_words(text):
    """Menerapkan penggantian kata khusus pada teks."""
    processed_text = text
    # Urutkan dari kata terpanjang ke terpendek untuk menghindari penggantian parsial
    sorted_replacements = sorted(REPLACEMENT_MAP.items(), key=lambda item: len(item[0]), reverse=True)
    for old_word, new_word in sorted_replacements:
        # Gunakan regex case-insensitive untuk mencocokkan kata secara keseluruhan
        pattern = re.compile(r'\b' + re.escape(old_word) + r'\b', re.IGNORECASE)
        processed_text = pattern.sub(new_word, processed_text)
    return processed_text

# --- Fungsi Edit 300 Kata Pertama dengan Gemini AI ---
def edit_first_300_words_with_gemini(post_id, post_title, full_text_content):
    """
    Mengirim 300 kata pertama ke Gemini AI untuk diedit,
    dan menggabungkannya kembali dengan sisa artikel.
    """
    words = full_text_content.split()
    
    if len(words) < 50:
        print(f"[{post_id}] Artikel terlalu pendek (<50 kata) untuk diedit oleh Gemini AI. Melewati pengeditan.")
        return full_text_content
        
    first_300_words_list = words[:300]
    rest_of_article_list = words[300:]
    
    first_300_words_text = " ".join(first_300_words_list)
    rest_of_article_text = " ".join(rest_of_article_list)

    print(f"🤖 Memulai pengeditan Gemini AI untuk artikel ID: {post_id} - '{post_title}' ({len(first_300_words_list)} kata pertama)...")
    
    try:
        # Instruksi prompt yang lebih baik untuk menjaga paragraf
        prompt = (
            f"Cerita Berikut adalah cuplikan dari 300 kata pertama dari cerita utuhnya, Perbaiki tata bahasa, ejaan, dan tingkatkan keterbacaan paragraf berikut. "
            f"pharaprse signikatif setiap kata, dan buat agar lebih mengalir sehingga 300 kata pertama ini beda dari aslinya:\n\n"
            f"{first_300_words_text}"
        )
        
        response = gemini_model.generate_content(prompt)
        edited_text_from_gemini = response.text
        
        print(f"✅ Gemini AI selesai mengedit bagian pertama artikel ID: {post_id}.")
        
        # Bersihkan ulang output Gemini AI untuk memastikan format paragraf yang konsisten
        # Ini penting jika Gemini tidak selalu mengembalikan double newline
        cleaned_edited_text = clean_html_to_markdown_text(edited_text_from_gemini) 
        
        # Gabungkan bagian yang diedit dengan sisa artikel.
        # Tambahkan double newline eksplisit di antara kedua bagian untuk pemisah yang jelas.
        # Pastikan sisa_artikel juga memiliki format paragraf yang benar (seharusnya sudah dari clean_html_to_markdown_text di fetch_all_and_process_posts)
        final_combined_text = cleaned_edited_text.strip() + "\n\n" + rest_of_article_text.strip()
        
        # Final cleanup untuk seluruh teks setelah penggabungan
        return clean_html_to_markdown_text(final_combined_text)
        
    except Exception as e:
        print(f"❌ Error saat mengedit dengan Gemini AI untuk artikel ID: {post_id} - {e}. Menggunakan teks asli untuk bagian ini.")
        return full_text_content

# --- Fungsi untuk memuat dan menyimpan status postingan yang sudah diterbitkan ---
def load_published_posts_state():
    """Memuat ID postingan yang sudah diterbitkan dari file state."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                print(f"Warning: {STATE_FILE} is corrupted or empty. Starting with an empty published posts list.")
                return set()
    return set()

def save_published_posts_state(published_ids):
    """Menyimpan ID postingan yang sudah diterbitkan ke file state."""
    with open(STATE_FILE, 'w') as f:
        json.dump(list(published_ids), f)

# === Ambil semua postingan dari WordPress.com API ===
def fetch_all_and_process_posts():
    """
    Mengambil semua postingan dari WordPress.com API, membersihkan HTML (dengan BeautifulSoup),
    dan menerapkan penggantian kata khusus. TIDAK ADA PENGEDITAN AI DI SINI.
    """
    all_posts_raw = []
    offset = 0
    per_request_limit = 100

    print("📥 Mengambil semua artikel dari WordPress.com API (pembersihan HTML dengan BeautifulSoup)...")

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
        processed_title = replace_custom_words(original_title)
        post['processed_title'] = processed_title

        # --- Pemrosesan Konten Awal (Pembersihan HTML dengan BeautifulSoup & Penggantian Kata) ---
        raw_content = post.get('content', '')
        
        # Langkah 1: Hapus tag <a> dulu
        content_no_anchors = remove_anchor_tags(raw_content)
        
        # Langkah 2: Gunakan BeautifulSoup untuk membersihkan dan memformat paragraf
        # Ini akan menghasilkan teks dengan pemisah paragraf yang benar (\n\n)
        cleaned_formatted_content = clean_html_to_markdown_text(content_no_anchors)
        
        # Langkah 3: Terapkan Penggantian Kata Khusus pada konten yang sudah bersih
        content_after_replacements = replace_custom_words(cleaned_formatted_content)

        # Simpan konten yang sudah bersih dan diganti kata-katanya
        # Ini adalah input untuk Gemini AI atau sisa artikel jika tidak diedit
        post['raw_cleaned_content'] = content_after_replacements 
        
        # Snippet untuk deskripsi, diambil dari konten yang sudah bersih
        snippet_text = content_after_replacements
        post['description_snippet'] = snippet_text[:200].replace('\n', ' ').strip()
        if len(snippet_text) > 200:
            post['description_snippet'] += "..."
        
        # Pastikan ID post ada di dictionary
        post['ID'] = post.get('ID') 
        processed_posts.append(post)

    return processed_posts

# === Hasilkan file Markdown untuk Jekyll ===
def generate_jekyll_markdown_post(post):
    """Menghasilkan file Markdown Jekyll dari data postingan yang sudah diproses."""
    post_date_obj = datetime.datetime.now(datetime.timezone.utc)
    jekyll_date_str = post_date_obj.strftime('%Y-%m-%d %H:%M:%S %z')
    filename_prefix = post_date_obj.strftime('%Y-%m-%d')
    filename = f"{filename_prefix}-{sanitize_filename(post['processed_title'])}.md"
    filepath = os.path.join(POST_DIR, filename)

    categories_list = []
    tags_list = []
    if post.get('categories'):
        categories_list = [data['name'] for slug, data in post['categories'].items() if data.get('name')]
    if post.get('tags'):
        tags_list = [data['name'] for slug, data in post['tags'].items() if data.get('name')]

    author_name = "Om Sugeng" # Anda bisa ubah ini atau ambil dari API jika tersedia

    description_text = post.get('description_snippet', '')
    
    # Escape nilai untuk YAML Front Matter
    escaped_title = json.dumps(post['processed_title'])
    escaped_description = json.dumps(description_text)
    escaped_author = json.dumps(author_name)
    
    front_matter_lines = [
        "---",
        f"layout: post",
        f"title: {escaped_title}",
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

    # Konten artikel yang sudah diedit Gemini (atau asli jika tidak diedit)
    article_content = post['processed_markdown_content']

    full_markdown_content = yaml_front_matter + article_content

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(full_markdown_content)
    print(f"✅ Generated Jekyll Markdown post: {filepath}")

# === Eksekusi Utama ===
if __name__ == '__main__':
    print(f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] Starting Jekyll post generation process...")
    print("🚀 Mengambil semua artikel WordPress (pembersihan HTML dengan BeautifulSoup, TANPA pengeditan AI di tahap ini).")
    print("🗓️ Tanggal postingan Jekyll akan mengikuti tanggal saat ini (saat GitHub Action dijalankan).")
    print("✨ Penggantian kata khusus diterapkan pada judul dan konten (termasuk imbuhan).")
    print("🤖 Fitur Pengeditan 300 Kata Pertama oleh Gemini AI DIAKTIFKAN, hanya untuk **satu artikel terbaru yang akan dipublikasikan**.")
    print("✍️ Menggunakan format paragraf standar yang diperbaiki dengan BeautifulSoup.")
    
    try:
        # 1. Muat daftar postingan yang sudah diterbitkan
        published_ids = load_published_posts_state()
        print(f"Ditemukan {len(published_ids)} postingan yang sudah diterbitkan sebelumnya.")

        # 2. Ambil semua postingan dari API WordPress dan lakukan pre-processing awal saja
        all_posts_preprocessed = fetch_all_and_process_posts()
        print(f"Total {len(all_posts_preprocessed)} artikel ditemukan dan diproses awal dari WordPress API.")

        # 3. Filter postingan yang belum diterbitkan berdasarkan ID dari file state
        unpublished_posts = [post for post in all_posts_preprocessed if str(post['ID']) not in published_ids]
        print(f"Ditemukan {len(unpublished_posts)} artikel yang belum diterbitkan.")
        
        if not unpublished_posts:
            print("\n🎉 Tidak ada artikel baru yang tersedia untuk diterbitkan hari ini. Proses selesai.")
            print("GitHub Actions akan melakukan commit jika ada perubahan pada state file (misal, pertama kali dijalankan).")
            exit()

        # 4. Urutkan postingan yang belum diterbitkan dari yang TERBARU ke TERLAMA
        # Menggunakan tanggal 'date' dari API WordPress.
        unpublished_posts.sort(key=lambda x: datetime.datetime.fromisoformat(x['date'].replace('Z', '+00:00')), reverse=True)

        # 5. Pilih satu postingan untuk diterbitkan hari ini (yang paling baru dari yang belum diterbitkan)
        post_to_publish = unpublished_posts[0]
        
        print(f"🌟 Menerbitkan artikel berikutnya: '{post_to_publish.get('processed_title')}' (ID: {post_to_publish.get('ID')})")
        
        # LAKUKAN PENGEDITAN AI HANYA PADA post_to_publish INI
        final_processed_content = edit_first_300_words_with_gemini(
            post_to_publish['ID'], 
            post_to_publish['processed_title'], 
            post_to_publish['raw_cleaned_content']
        )
        post_to_publish['processed_markdown_content'] = final_processed_content
        
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
        # Tambahkan ini untuk melihat traceback lengkap di log GitHub Actions
        import traceback
        traceback.print_exc()
