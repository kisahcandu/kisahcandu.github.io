import requests
import os
import re
import json
import datetime

# --- Konfigurasi ---
BLOG_ID = os.environ.get('WORDPRESS_BLOG_ID', '143986468')
API_BASE_URL = f"https://public-api.wordpress.com/rest/v1.1/sites/{BLOG_ID}/posts"

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
    """
    Menghapus sebagian besar tag HTML, kecuali yang esensial,
    dan mengganti </p> dengan dua newline untuk pemisahan paragraf.
    """
    # 1. Ganti </p> dengan dua newline (\n\n) untuk pemisah paragraf Markdown
    #    Ini harus dilakukan sebelum menghapus tag lain agar pemisah tetap ada
    html_with_newlines = re.sub(r'</p>', r'\n\n', html, flags=re.IGNORECASE)

    # 2. Hapus semua tag <img>
    html_no_images = re.sub(r'<img[^>]*>', '', html_with_newlines)
    
    # 3. Hapus semua tag <div> (pembuka dan penutup)
    html_no_divs = re.sub(r'</?div[^>]*>', '', html_no_images, flags=re.IGNORECASE)

    # 4. Hapus tag HTML lainnya (misalnya <h1>, <h2>, <span>, <strong>, <em>, dll.)
    #    Ini juga akan menghapus tag <p> pembuka <p>
    clean_text = re.sub('<[^<]+?>', '', html_no_divs)
    
    # 5. Hapus multiple newline yang berlebihan menjadi maksimal dua newline
    clean_text = re.sub(r'\n{3,}', r'\n\n', clean_text).strip()

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
    # Mengubah urutan penggantian dari yang lebih panjang ke yang lebih pendek
    sorted_replacements = sorted(REPLACEMENT_MAP.items(), key=lambda item: len(item[0]), reverse=True)
    
    for old_word, new_word in sorted_replacements:
        # Menghilangkan \b (word boundary) untuk penggantian kata yang menyatu
        pattern = re.escape(old_word)
        processed_text = re.sub(pattern, new_word, processed_text, flags=re.IGNORECASE)
    return processed_text

# === Ambil semua postingan dari WordPress.com API ===
def fetch_and_process_posts():
    """Mengambil semua postingan dari WordPress.com API dan memprosesnya."""
    all_posts = []
    offset = 0
    per_request_limit = 100 

    print("📥 Mengambil artikel dari WordPress.com API dan memulai proses pembersihan...")

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

            # --- Urutan Pemrosesan Teks ---
            clean_text = remove_anchor_tags(raw_content)
            # PENTING: Penggantian kata dilakukan setelah pembersihan HTML yang mempertahankan paragraf
            final_processed_text = strip_html_and_divs(clean_text)
            final_processed_text = replace_custom_words(final_processed_text)
            # --- Akhir Urutan Pemrosesan Teks ---

            post['processed_markdown_content'] = final_processed_text

            snippet_text = final_processed_text
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
    print("🚀 Memulai proses generasi postingan Jekyll (.md) dengan paragraf terjaga dan penggantian kata agresif...")
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
