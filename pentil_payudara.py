import requests
import os
import re
import json
import datetime
import time

# --- Konfigurasi ---
# Gunakan GitHub Secrets untuk WORDPRESS_BLOG_ID agar lebih aman
BLOG_ID = os.environ.get('WORDPRESS_BLOG_ID', '143986468')
API_BASE_URL = f"https://public-api.wordpress.com/rest/v1.1/sites/{BLOG_ID}/posts"
POST_DIR = '_posts'
STATE_FILE = 'published_posts.json' # File untuk melacak postingan yang sudah diterbitkan

# --- Konfigurasi Gemini API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Pastikan API key tersedia
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set. Please set it in your GitHub Secrets or local environment.")

import google.generativeai as genai
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

# FUNGSI BARU UNTUK EKSTRAKSI GAMBAR
def extract_first_image_url(html_content):
    """
    Mencari URL gambar pertama di dalam konten HTML.
    """
    # Regex untuk mencari tag <img> dan mengambil nilai src
    match = re.search(r'<img[^>]+src="([^"]+)"', html_content, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

# FUNGSI PEMBESIHAN LAMA YANG DIKEMBALIKAN (Menggunakan Regex)
def strip_html_and_divs(html):
    """
    Menghapus sebagian besar tag HTML, kecuali yang esensial,
    dan mengganti </p> dengan dua newline untuk pemisahan paragraf.
    """
    html_with_newlines = re.sub(r'</p>', r'\n\n', html, flags=re.IGNORECASE)
    # Hapus tag <img> dan <div> serta </div>
    html_no_images = re.sub(r'<img[^>]*>', '', html_with_newlines)
    html_no_divs = re.sub(r'</?div[^>]*>', '', html_no_images, flags=re.IGNORECASE)
    # Hapus semua tag HTML yang tersisa
    clean_text = re.sub('<[^<]+?>', '', html_no_divs)
    # Normalisasi multiple newlines menjadi double newline
    clean_text = re.sub(r'\n{3,}', r'\n\n', clean_text).strip()
    return clean_text

def remove_anchor_tags(html_content):
    """Menghapus tag <a> tapi mempertahankan teks di dalamnya."""
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
        # Menghilangkan \b (word boundary) agar penggantian berlaku juga untuk imbuhan
        pattern = re.compile(re.escape(old_word), re.IGNORECASE)
        processed_text = pattern.sub(new_word, processed_text)
    return processed_text

# --- Fungsi Edit 300 Kata Pertama dengan Gemini AI ---
def edit_first_300_words_with_gemini(post_id, post_title, full_text_content):
    """
    Mengirim 300 kata pertama ke Gemini AI untuk diedit,
    dan menggabungkannya kembali dengan sisa artikel,
    mempertahankan format paragraf sisa artikel.
    """
    words = full_text_content.split()

    if len(words) < 50:
        print(f"[{post_id}] Artikel terlalu pendek (<50 kata) untuk diedit oleh Gemini AI. Melewati pengeditan.")
        return full_text_content

    # Hitung jumlah karakter untuk 300 kata pertama
    char_count_for_300_words = 0
    word_count = 0
    
    for i, word in enumerate(words):
        if word_count < 300:
            char_count_for_300_words += len(word)
            if i < len(words) - 1:
                char_count_for_300_words += 1 
            word_count += 1
        else:
            break
            
    char_count_for_300_words = min(char_count_for_300_words, len(full_text_content))

    first_300_words_original_string = full_text_content[:char_count_for_300_words].strip()
    rest_of_article_text = full_text_content[char_count_for_300_words:].strip()

    print(f"🤖 Memulai pengeditan Gemini AI untuk artikel ID: {post_id} - '{post_title}' ({len(first_300_words_original_string.split())} kata pertama)...")

    try:
        prompt = (
            f"Cerita Berikut adalah cuplikan dari 300 kata pertama dari cerita utuhnya, Perbaiki tata bahasa, ejaan, dan tingkatkan keterbacaan paragraf berikut. "
            f"Paraphrase signifikan setiap kata, dan buat agar lebih mengalir sehingga 300 kata pertama ini beda dari aslinya:\n\n"
            f"{first_300_words_original_string}"
        )

        response = gemini_model.generate_content(prompt)
        edited_text_from_gemini = response.text

        print(f"✅ Gemini AI selesai mengedit bagian pertama artikel ID: {post_id}.")

        cleaned_edited_text = strip_html_and_divs(edited_text_from_gemini)

        # Gabungkan bagian yang diedit dengan sisa artikel.
        final_combined_text = cleaned_edited_text.strip() + "\n\n" + rest_of_article_text.strip()

        # Final cleanup untuk seluruh teks setelah penggabungan
        return strip_html_and_divs(final_combined_text)

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
    Mengambil semua postingan dari WordPress.com API, membersihkan HTML (dengan strip_html_and_divs),
    dan menerapkan penggantian kata khusus.
    """
    all_posts_raw = []
    offset = 0
    per_request_limit = 100

    print("📥 Mengambil semua artikel dari WordPress.com API (pembersihan HTML dengan strip_html_and_divs)...")

    while True:
        params = {
            'number': per_request_limit,
            'offset': offset,
            'status': 'publish',
            'fields': 'ID,title,content,excerpt,categories,tags,date,featured_image' # Tetap minta featured_image
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

        # --- Pemrosesan Konten Awal ---
        raw_content = post.get('content', '')

        # Langkah 1: Ekstrak gambar dari konten sebelum membersihkan HTML
        content_image_url = extract_first_image_url(raw_content)
        post['content_image_url'] = content_image_url

        # Langkah 2: Hapus tag <a>
        content_no_anchors = remove_anchor_tags(raw_content)

        # Langkah 3: Gunakan strip_html_and_divs untuk membersihkan dan memformat paragraf
        cleaned_formatted_content = strip_html_and_divs(content_no_anchors)

        # Langkah 4: Terapkan Penggantian Kata Khusus
        content_after_replacements = replace_custom_words(cleaned_formatted_content)

        post['raw_cleaned_content'] = content_after_replacements

        # Snippet untuk deskripsi
        snippet_text = content_after_replacements
        post['description_snippet'] = snippet_text[:200].replace('\n', ' ').strip()
        if len(snippet_text) > 200:
            post['description_snippet'] += "..."

        # Ambil URL gambar unggulan dari API
        featured_image_url = post.get('featured_image')
        post['featured_image_url'] = featured_image_url

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

    author_name = "Om Sugeng"

    description_text = post.get('description_snippet', '')
    
    # Prioritaskan featured_image_url, jika tidak ada, gunakan content_image_url
    image_to_use = post.get('featured_image_url') or post.get('content_image_url')

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
    
    # Tambahkan gambar hanya jika ada gambar yang ditemukan (featured atau dari konten)
    if image_to_use:
        front_matter_lines.append(f"image: {json.dumps(image_to_use)}")
    
    if categories_list:
        front_matter_lines.append(f"categories: {json.dumps(categories_list)}")
    if tags_list:
        front_matter_lines.append(f"tags: {json.dumps(tags_list)}")

    front_matter_lines.append("---")
    yaml_front_matter = "\n".join(front_matter_lines) + "\n\n"

    # Konten artikel yang sudah diedit Gemini
    article_content = post['processed_markdown_content']

    full_markdown_content = yaml_front_matter + article_content

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(full_markdown_content)
    print(f"✅ Generated Jekyll Markdown post: {filepath}")

# === Eksekusi Utama ===
if __name__ == '__main__':
    print(f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] Starting Jekyll post generation process...")
    print("🚀 Mengambil semua artikel WordPress.")
    print("🤖 Fitur Pengeditan 300 Kata Pertama oleh Gemini AI DIAKTIFKAN.")
    print("🖼️ Mencoba mengambil gambar unggulan dari API. Jika tidak ada, mencoba mengambil gambar pertama dari konten artikel.")

    try:
        # 1. Muat daftar postingan yang sudah diterbitkan
        published_ids = load_published_posts_state()
        print(f"Ditemukan {len(published_ids)} postingan yang sudah diterbitkan sebelumnya.")

        # 2. Ambil semua postingan dari API WordPress dan lakukan pre-processing
        all_posts_preprocessed = fetch_all_and_process_posts()
        print(f"Total {len(all_posts_preprocessed)} artikel ditemukan dan diproses awal dari WordPress API.")

        # 3. Filter postingan yang belum diterbitkan
        unpublished_posts = [post for post in all_posts_preprocessed if str(post['ID']) not in published_ids]
        print(f"Ditemukan {len(unpublished_posts)} artikel yang belum diterbitkan.")

        if not unpublished_posts:
            print("\n🎉 Tidak ada artikel baru yang tersedia untuk diterbitkan hari ini. Proses selesai.")
            exit()

        # 4. Urutkan postingan yang belum diterbitkan dari yang TERBARU
        unpublished_posts.sort(key=lambda x: datetime.datetime.fromisoformat(x['date'].replace('Z', '+00:00')), reverse=True)

        # 5. Pilih satu postingan untuk diterbitkan hari ini
        post_to_publish = unpublished_posts[0]

        print(f"🌟 Menerbitkan artikel berikutnya: '{post_to_publish.get('processed_title')}' (ID: {post_to_publish.get('ID')})")

        # LAKUKAN PENGEDITAN AI
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

    except Exception as e:
        print(f"❌ Terjadi kesalahan fatal: {e}")
        import traceback
        traceback.print_exc()
