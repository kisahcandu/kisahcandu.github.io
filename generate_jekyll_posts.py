import requests
import os
import re
import json
import datetime
import google.generativeai as genai
from google.generativeai import GenerativeModel

# --- Konfigurasi ---
BLOG_ID = os.environ.get('WORDPRESS_BLOG_ID', '143986468')
API_BASE_URL = f"https://public-api.wordpress.com/rest/v1.1/sites/{BLOG_ID}/posts"

# --- Konfigurasi Gemini AI ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY_PLACEHOLDER')
genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL = GenerativeModel('gemini-1.5-flash')

# --- Direktori Output ---
POST_DIR = '_posts'
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
    """Menghapus semua tag HTML, termasuk <img> dan div, hanya menyisakan teks."""
    html_no_images = re.sub(r'<img[^>]*>', '', html)
    html_no_divs = re.sub(r'</?div[^>]*>', '', html_no_images)
    clean_text = re.sub('<[^<]+?>', '', html_no_divs)
    return clean_text

def remove_anchor_tags(html_content):
    """Menghapus tag <a> tetapi mempertahankan teks di dalamnya."""
    return re.sub(r'<a[^>]*>(.*?)<\/a>', r'\1', html_content)

def sanitize_filename(title):
    """Membersihkan judul untuk digunakan sebagai nama file Jekyll."""
    clean_title = re.sub(r'[^\w\s-]', '', title).strip().lower()
    return re.sub(r'[-\s]+', '-', clean_title)

def replace_custom_words(text):
    """Mengganti kata-kata spesifik dalam teks dengan padanan yang ditentukan."""
    processed_text = text
    for old_word, new_word in REPLACEMENT_MAP.items():
        pattern = r'\b' + re.escape(old_word) + r'\b'
        processed_text = re.sub(pattern, new_word, processed_text, flags=re.IGNORECASE)
    return processed_text

# --- Gemini AI Integration ---
def paraphrase_with_gemini(text_content):
    """
    Melakukan paraphrase teks menggunakan Gemini AI.
    Mengatur alur dinamis agar artikel unik dan tidak terdeteksi sebagai duplikat.
    """
    if not text_content or text_content.strip() == "":
        print("Skipping paraphrase: text content is empty.")
        return ""

    prompt = (
        "Paraphrase teks berikut agar menjadi unik, segar, dan tidak terdeteksi sebagai duplikat. "
        "Pertahankan semua informasi, fakta, dan alur cerita asli. "
        "Gunakan gaya penulisan yang dinamis dan bervariasi, seolah-olah ditulis oleh seorang narator yang menarik. "
        "Pastikan struktur paragraf dan sub-judul (jika ada) tetap terjaga. "
        "Teks asli:\n\n"
        f"'{text_content}'"
    )

    try:
        response = GEMINI_MODEL.generate_content(prompt)
        paraphrased_text = response.text
        if not paraphrased_text:
            print("Warning: Gemini AI returned an empty response. Using original text.")
            return text_content
        return paraphrased_text
    except Exception as e:
        print(f"Error paraphrasing with Gemini AI: {e}")
        return text_content

# === Ambil semua postingan dari WordPress.com API ===
def fetch_and_process_posts():
    """Mengambil semua postingan dari WordPress.com API dan memprosesnya dengan Gemini AI."""
    all_posts = []
    offset = 0
    per_request_limit = 100

    print("📥 Mengambil artikel dari WordPress.com API dan memulai proses paraphrase...")

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

        for post in posts_batch:
            print(f"Processing Post ID: {post.get('ID')}, Title: '{post.get('title')}'")
            raw_content = post.get('content', '')

            clean_text = remove_anchor_tags(raw_content)
            clean_text_for_ai = strip_html_and_divs(clean_text)
            paraphrased_text = paraphrase_with_gemini(clean_text_for_ai)
            final_processed_text = replace_custom_words(paraphrased_text)

            post['processed_markdown_content'] = final_processed_text

            snippet_text = final_processed_text
            # Pastikan snippet tidak terlalu panjang dan tanpa newline
            post['description_snippet'] = snippet_text[:200].replace('\n', ' ').strip()
            if len(snippet_text) > 200:
                post['description_snippet'] += "..."

            all_posts.append(post)

        offset += len(posts_batch)
        if offset >= total_found:
            break

    return all_posts

# === Hasilkan file Markdown untuk Jekyll ===
def generate_jekyll_markdown_posts(posts_data):
    """Menghasilkan file Markdown untuk setiap postingan dengan YAML Front Matter."""
    for post in posts_data:
        try:
            post_date_obj = datetime.datetime.fromisoformat(post['date'].replace('Z', '+00:00'))
        except ValueError:
            print(f"Warning: Could not parse date for post '{post.get('title')}'. Using current UTC time.")
            post_date_obj = datetime.datetime.now(datetime.timezone.utc)

        jekyll_date_str = post_date_obj.strftime('%Y-%m-%d %H:%M:%S %z')

        filename_prefix = post_date_obj.strftime('%Y-%m-%d')
        filename = f"{filename_prefix}-{sanitize_filename(post['title'])}.md"
        filepath = os.path.join(POST_DIR, filename)

        categories_list = []
        tags_list = []
        if post.get('categories'):
            categories_list = [data['name'] for slug, data in post['categories'].items() if data.get('name')]
        if post.get('tags'):
            tags_list = [data['name'] for slug, data in post['tags'].items() if data.get('name')]

        author_name = "Om Sugeng"

        description_text = post.get('description_snippet', '')
        # Gunakan json.dumps untuk memastikan string di-escape dengan benar untuk YAML
        # Ini akan otomatis menambahkan kutip ganda dan escape jika diperlukan
        escaped_title = json.dumps(post['title'])
        escaped_description = json.dumps(description_text)
        escaped_author = json.dumps(author_name)
        
        # --- Membuat YAML Front Matter ---
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

        article_content = post['processed_markdown_content']

        full_markdown_content = yaml_front_matter + article_content

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_markdown_content)
        print(f"✅ Generated Jekyll Markdown post: {filepath}")

# === Eksekusi Utama ===
if __name__ == '__main__':
    if GEMINI_API_KEY == 'YOUR_GEMINI_API_KEY_PLACEHOLDER':
        print("Peringatan: GEMINI_API_KEY belum disetel. Pastikan Anda mengaturnya sebagai GitHub Secret!")
    
    print("🚀 Memulai proses generasi postingan Jekyll (.md) ke GitHub Actions...")
    try:
        posts = fetch_and_process_posts()
        print(f"✅ Total artikel yang berhasil diproses: {len(posts)}.")
        
        posts.sort(key=lambda x: datetime.datetime.fromisoformat(x['date'].replace('Z', '+00:00')), reverse=True)

        generate_jekyll_markdown_posts(posts)
        
        print("\n🎉 Proses Selesai!")
        print(f"File Markdown untuk Jekyll sudah ada di folder: **{POST_DIR}/**")
        print("GitHub Actions akan melakukan commit dan push file-file ini ke repositori Anda.")
        print("\nAnda sekarang bisa mengandalkan Jekyll (atau GitHub Pages) untuk membangun situs Anda.")

    except Exception as e:
        print(f"❌ Terjadi kesalahan fatal: {e}")
