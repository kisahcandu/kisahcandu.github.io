import requests
import os
import re
import json
import datetime
import google.generativeai as genai
from google.generativeai import GenerativeModel
import nltk
from nltk.tokenize import sent_tokenize

# --- Download NLTK punkt tokenizer (hanya perlu sekali) ---
# Jalankan ini secara lokal pertama kali atau pastikan di GitHub Actions
try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    print("Downloading NLTK punkt tokenizer...")
    nltk.download('punkt')
    print("NLTK punkt tokenizer downloaded.")

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
        # Contoh: "memeknya" akan menjadi "serambi lempitnya"
        pattern = re.compile(re.escape(old_word), re.IGNORECASE)
        processed_text = pattern.sub(new_word, processed_text)
    return processed_text

# --- Gemini AI Integration ---
def paraphrase_text_with_gemini(text_content, max_retries=3, chunk_size=3000):
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
        # Menggunakan prompt Anda yang sudah terbukti jalan
        prompt = (
            "Paraphrase teks berikut agar menjadi unik, segar, dan tidak terdeteksi sebagai duplikat. "
            "Pertahankan semua informasi, fakta, dan alur cerita asli. "
            "Gunakan gaya penulisan yang dinamis dan bervariasi, seolah-olah ditulis oleh seorang narator yang menarik. "
            "Pastikan struktur paragraf dan sub-judul (jika ada) tetap terjaga. "
            "Teks asli:\n\n"
            f"'{chunk}'" # Menggunakan chunk di sini
        )
        
        retries = 0
        while retries < max_retries:
            try:
                print(f"Memproses parafrase bagian {i+1}/{len(chunks)}...")
                response = GEMINI_MODEL.generate_content(prompt)
                
                if response and response.text:
                    paraphrased_chunks.append(response.text.strip())
                    break # Berhasil, keluar dari loop retry
                else:
                    print(f"⚠️ Respon kosong dari Gemini untuk bagian {i+1}. Mencoba lagi ({retries+1}/{max_retries})...")
                    retries += 1
            except Exception as e:
                print(f"❌ Error saat memparafrase bagian {i+1}: {e}. Mencoba lagi ({retries+1}/{max_retries})...")
                retries += 1
        
        if retries == max_retries:
            print(f"🚫 Gagal memparafrase bagian {i+1} setelah {max_retries} percobaan. Menggunakan teks asli.")
            paraphrased_chunks.append(chunk) # Gunakan teks asli jika gagal

    return "\n\n".join(paraphrased_chunks)


def limit_sentences_per_paragraph(text, max_sentences=2):
    """
    Membatasi setiap paragraf agar hanya memiliki maksimal 'max_sentences' kalimat.
    Mempertahankan pemisah paragraf asli dan menambahkan pemisah paragraf baru jika diperlukan.
    """
    if not text.strip():
        return ""

    processed_paragraphs = []
    original_paragraphs = text.split('\n\n')

    for para in original_paragraphs:
        if not para.strip():
            processed_paragraphs.append("")
            continue

        sentences = sent_tokenize(para.strip(), language='indonesian')

        current_paragraph_sentences = []
        for i, sentence in enumerate(sentences):
            current_paragraph_sentences.append(sentence.strip())

            if len(current_paragraph_sentences) == max_sentences or i == len(sentences) - 1:
                processed_paragraphs.append(" ".join(current_paragraph_sentences))
                current_paragraph_sentences = []

    return "\n\n".join(processed_paragraphs).strip()


def load_published_posts_state():
    """Memuat daftar ID postingan yang sudah diterbitkan dari state file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
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
        clean_text_before_paraphrase = strip_html_and_divs(clean_text_before_paraphrase)
        
        # Parafrase konten dengan Gemini AI (menggunakan fungsi paraphrase yang diadaptasi)
        print(f"Memulai parafrase konten untuk '{processed_title}'...")
        paraphrased_content = paraphrase_text_with_gemini(clean_text_before_paraphrase)
        
        # --- Batasi kalimat per paragraf setelah parafrase ---
        print(f"Membatasi kalimat per paragraf untuk '{processed_title}'...")
        formatted_content_with_sentence_limit = limit_sentences_per_paragraph(paraphrased_content, max_sentences=2)

        # Lalu terapkan penggantian kata khusus pada konten yang sudah diparafrase dan diformat
        final_processed_text = replace_custom_words(formatted_content_with_sentence_limit) 
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
    print("🚀 Memulai proses generasi postingan Jekyll (.md) terjadwal dari TERBARU ke TERLAMA...")
    print("🗓️ Tanggal postingan akan diatur ke tanggal saat ini (saat artikel diproses).")
    print("✨ Penggantian kata khusus diterapkan pada judul dan konten.")
    print("💡 Konten akan diparafrase menggunakan Gemini AI untuk keunikan.")
    print("✍️ Setiap paragraf konten akan dibatasi hingga maksimal 2 kalimat.")
    try:
        # 1. Muat daftar postingan yang sudah diterbitkan
        published_ids = load_published_posts_state()
        print(f"Ditemukan {len(published_ids)} postingan yang sudah diterbitkan sebelumnya.")

        # 2. Ambil semua postingan dari API
        all_posts = fetch_all_and_process_posts()
        print(f"Total {len(all_posts)} artikel ditemukan dari WordPress API.")

        # 3. Filter postingan yang belum diterbitkan
        unpublished_posts = [post for post in all_posts if str(post['ID']) not in published_ids]
        print(f"Ditemukan {len(unpublished_posts)} artikel yang belum diterbitkan.")
        
        if not unpublished_posts:
            print("\n🎉 Tidak ada artikel baru yang tersedia untuk diterbitkan hari ini. Proses selesai.")
            print("GitHub Actions akan melakukan commit jika ada perubahan pada state file.")
            exit()

        # 4. Urutkan postingan yang belum diterbitkan dari yang TERBARU ke TERLAMA
        unpublished_posts.sort(key=lambda x: datetime.datetime.fromisoformat(x['date'].replace('Z', '+00:00')), reverse=True)

        # 5. Pilih satu postingan untuk diterbitkan hari ini (yang paling baru dari yang belum diterbitkan)
        post_to_publish = unpublished_posts[0]
        
        print(f"🌟 Menerbitkan artikel berikutnya: '{post_to_publish.get('title')}' (ID: {post_to_publish.get('ID')})")
        
        # 6. Hasilkan file Markdown
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
