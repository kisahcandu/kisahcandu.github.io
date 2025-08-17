import requests
import os
import re
import json
import datetime
import time
import google.generativeai as genai

# --- Konfigurasi ---
BLOG_ID = os.environ.get('WORDPRESS_BLOG_ID', '143986468')
API_BASE_URL = f"https://public-api.wordpress.com/rest/v1.1/sites/{BLOG_ID}/posts"
POST_DIR = '_posts'
STATE_FILE = 'published_posts.json'
# --- Konfigurasi Gemini API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")
genai.configure(api_key=GEMINI_API_KEY)

# Menggunakan Gemini 1.5 Pro karena ini yang paling kuat untuk tugas penulisan kreatif
gemini_model = genai.GenerativeModel("gemini-2.5-flash")

# Buat folder _posts jika belum ada
os.makedirs(POST_DIR, exist_ok=True)

# --- Penggantian Kata Khusus ---
REPLACEMENT_MAP = {
    "memek": "serambi lempit",
    "kontol": "rudal",
    "ngentot": "menyetubuhi",
    "vagina": "serambi lempit",
    "penis": "rudal",
}

# === Utilitas ===
def extract_first_image_url(html_content):
    match = re.search(r'<img[^>]+src="([^"]+)"', html_content, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def strip_html_and_divs(html):
    html_with_newlines = re.sub(r'</p>', r'\n\n', html, flags=re.IGNORECASE)
    html_no_images = re.sub(r'<img[^>]*>', '', html_with_newlines)
    html_no_divs = re.sub(r'</?div[^>]*>', '', html_no_images, flags=re.IGNORECASE)
    clean_text = re.sub('<[^<]+?>', '', html_no_divs)
    clean_text = re.sub(r'\n{3,}', r'\n\n', clean_text).strip()
    return clean_text

def remove_anchor_tags(html_content):
    return re.sub(r'<a[^>]*>(.*?)<\/a>', r'\1', html_content)

def sanitize_filename(title):
    clean_title = re.sub(r'[^\w\s-]', '', title).strip().lower()
    return re.sub(r'[-\s]+', '-', clean_title)

def replace_custom_words(text):
    processed_text = text
    sorted_replacements = sorted(REPLACEMENT_MAP.items(), key=lambda item: len(item[0]), reverse=True)
    for old_word, new_word in sorted_replacements:
        pattern = re.compile(re.escape(old_word), re.IGNORECASE)
        processed_text = pattern.sub(new_word, processed_text)
    return processed_text

# --- Fungsi Edit Seluruh Artikel dengan Gemini AI ---
def edit_full_article_with_gemini(post_id, post_title, full_text_content):
    if len(full_text_content.split()) < 50:
        print(f"[{post_id}] Artikel terlalu pendek. Melewati pengeditan.")
        return full_text_content

    print(f"🤖 Memulai pengeditan Gemini AI untuk artikel ID: {post_id} - '{post_title}'...")

    # Set parameter yang akan membuat hasil lebih mirip gaya kita
    generation_config = {
        "temperature": 1.0, 
        "max_output_tokens": 8192 # Setting ini penting biar ceritanya panjang
    }

    # Prompt yang udah kita sesuaikan
    prompt = (
    f"Kamu adalah penulis cerita yang ahli dalam membangun ketegangan dan adegan romansa. "
    f"Tugasmu adalah menulis ulang cerita berikut. "
    f"Fokus pada interaksi karakter yang intens dan detail emosi yang kuat. "
    f"Tambahkan adegan-adegan baru untuk memperpanjang alur cerita. "
    f"Buat cerita ini jadi sangat panjang, minimal 2000 kata, dengan dialog yang hidup. "
    f"Pastikan narasi mengalir dengan lancar dan mudah dipahami. "
    f"Pertahankan esensi dan adegan intim. "
    f"tulis langsung cerita, tanpa prolog atau konfirmasi dari anda, contoh 'Baik, saya akan menulis ulang cerita ini dengan fokus pada ketegangan yang dibangun, interaksi karakter yang intens, detail emosi yang kuat, dan pengembangan alur cerita yang signifikan. Target 2000 kata akan saya penuhi dengan memperpanjang adegan yang ada dan menambahkan adegan baru'. "
    f"Berikut adalah cerita aslinya:\n\n"
    f"{full_text_content}"
)
    try:
        response = gemini_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        edited_text_from_gemini = response.text
        
        # --- Bagian yang aku tambahin, bro! ---
        # Ini buat bersihin teks awal yang gak penting
        # Kita cari judulnya, terus ambil semua teks setelah judul
        clean_text_start_index = edited_text_from_gemini.find(post_title)
        if clean_text_start_index != -1:
            edited_text_from_gemini = edited_text_from_gemini[clean_text_start_index:]

        print(f"✅ Gemini AI selesai mengedit seluruh artikel ID: {post_id}.")
        cleaned_edited_text = strip_html_and_divs(edited_text_from_gemini)
        return cleaned_edited_text

    except Exception as e:
        print(f"❌ Error saat mengedit dengan Gemini AI untuk artikel ID: {post_id} - {e}. Menggunakan teks asli.")
        return full_text_content

# --- Fungsi untuk memuat dan menyimpan status postingan yang sudah diterbitkan ---
def load_published_posts_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                print(f"Warning: {STATE_FILE} is corrupted or empty.")
                return set()
    return set()

def save_published_posts_state(published_ids):
    with open(STATE_FILE, 'w') as f:
        json.dump(list(published_ids), f)

# === Ambil semua postingan dari WordPress.com API ===
def fetch_all_and_process_posts():
    all_posts_raw = []
    offset = 0
    per_request_limit = 100
    print("📥 Mengambil semua artikel dari WordPress.com API...")

    while True:
        params = {
            'number': per_request_limit,
            'offset': offset,
            'status': 'publish',
            'fields': 'ID,title,content,excerpt,categories,tags,date,featured_image'
        }
        res = requests.get(API_BASE_URL, params=params)

        if res.status_code != 200:
            raise Exception(f"Gagal mengambil data dari WordPress.com API: {res.status_code} - {res.text}")

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
        original_title = post.get('title', '')
        processed_title = replace_custom_words(original_title)
        post['processed_title'] = processed_title
        raw_content = post.get('content', '')
        content_image_url = extract_first_image_url(raw_content)
        post['content_image_url'] = content_image_url
        content_no_anchors = remove_anchor_tags(raw_content)
        cleaned_formatted_content = strip_html_and_divs(content_no_anchors)
        content_after_replacements = replace_custom_words(cleaned_formatted_content)
        post['raw_cleaned_content'] = content_after_replacements
        snippet_text = content_after_replacements
        post['description_snippet'] = snippet_text[:200].replace('\n', ' ').strip()
        if len(snippet_text) > 200:
            post['description_snippet'] += "..."
        featured_image_url = post.get('featured_image')
        post['featured_image_url'] = featured_image_url
        post['ID'] = post.get('ID')
        processed_posts.append(post)
    return processed_posts

# === Hasilkan file Markdown untuk Jekyll ===
def generate_jekyll_markdown_post(post):
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
    image_to_use = post.get('featured_image_url') or post.get('content_image_url')

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
    if image_to_use:
        front_matter_lines.append(f"image: {json.dumps(image_to_use)}")
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
    try:
        published_ids = load_published_posts_state()
        print(f"Ditemukan {len(published_ids)} postingan yang sudah diterbitkan sebelumnya.")
        all_posts_preprocessed = fetch_all_and_process_posts()
        print(f"Total {len(all_posts_preprocessed)} artikel ditemukan.")
        unpublished_posts = [post for post in all_posts_preprocessed if str(post['ID']) not in published_ids]
        print(f"Ditemukan {len(unpublished_posts)} artikel yang belum diterbitkan.")

        if not unpublished_posts:
            print("\n🎉 Tidak ada artikel baru. Proses selesai.")
            exit()

        unpublished_posts.sort(key=lambda x: datetime.datetime.fromisoformat(x['date'].replace('Z', '+00:00')), reverse=True)
        post_to_publish = unpublished_posts[0]

        print(f"🌟 Menerbitkan artikel berikutnya: '{post_to_publish.get('processed_title')}' (ID: {post_to_publish.get('ID')})")

        final_processed_content = edit_full_article_with_gemini(
            post_to_publish['ID'],
            post_to_publish['processed_title'],
            post_to_publish['raw_cleaned_content']
        )
        post_to_publish['processed_markdown_content'] = final_processed_content
        generate_jekyll_markdown_post(post_to_publish)
        published_ids.add(str(post_to_publish['ID']))
        save_published_posts_state(published_ids)
        print(f"✅ State file '{STATE_FILE}' diperbarui.")
        print("\n🎉 Proses Selesai!")
        print(f"File Markdown sudah ada di folder: **{POST_DIR}/**")

    except Exception as e:
        print(f"❌ Terjadi kesalahan fatal: {e}")
        import traceback
        traceback.print_exc()
