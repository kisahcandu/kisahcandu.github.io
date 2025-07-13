import os
import re
import datetime

# Direktori postingan
POSTS_DIR = '_posts'

# Nama file output
SITEMAP_XSL_FILE = 'wp-sitemap.xsl'  # File XSL
BASE_URL = 'https://kisahcandu.github.io/'  # URL dasar

# Output path
ROOT_SITEMAP = 'sitemap.xml'
PUBLIC_FOLDER = 'public'
PUBLIC_SITEMAP = os.path.join(PUBLIC_FOLDER, 'sitemap.xml')


def extract_front_matter(markdown_content):
    """Mengekstrak front matter YAML dari konten Markdown."""
    match = re.match(r'---\s*\n(.*?)\n---\s*\n', markdown_content, re.DOTALL)
    if match:
        front_matter_str = match.group(1)

        title_match = re.search(r'title:\s*(.*)', front_matter_str)
        # Menggunakan regex yang lebih fleksibel untuk tanggal, menerima YYYY-MM-DD atau YYYY-MM-DD HH:MM:SS
        date_match = re.search(r'date:\s*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?)', front_matter_str)

        title = title_match.group(1).strip().strip('"\'') if title_match else 'No Title'
        date_str = date_match.group(1).strip() if date_match else None

        lastmod = None
        if date_str:
            try:
                # Menyesuaikan format parsing tanggal
                if ' ' in date_str: # Jika ada waktu
                    dt_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                else: # Jika hanya tanggal
                    dt_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                lastmod = dt_obj.isoformat(timespec='seconds') + '+00:00'
            except ValueError:
                print(f"⚠️ Peringatan: Format tanggal tidak valid untuk '{date_str}'")
                pass

        return {'title': title, 'date': date_str, 'lastmod': lastmod}
    return None


def generate_sitemap_content():
    """Menghasilkan isi sitemap.xml sebagai list baris XML."""
    xml_content = []
    xml_content.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_content.append(f'<?xml-stylesheet type="text/xsl" href="{BASE_URL}{SITEMAP_XSL_FILE}" ?>')
    xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    # Pastikan direktori _posts ada sebelum memprosesnya
    if not os.path.exists(POSTS_DIR):
        print(f"❌ Error: Direktori '{POSTS_DIR}' tidak ditemukan. Harap pastikan direktori ini ada dan berisi file Markdown Anda.")
        return None # Mengembalikan None jika direktori tidak ada

    for filename in os.listdir(POSTS_DIR):
        if filename.endswith('.md'):
            filepath = os.path.join(POSTS_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"❌ Error membaca file '{filepath}': {e}")
                continue # Lanjutkan ke file berikutnya

            front_matter = extract_front_matter(content)

            if front_matter:
                # Asumsi format nama file: YYYY-MM-DD-nama-postingan.md
                # Menggunakan regex untuk mengekstrak slug dengan lebih robust
                match_filename = re.match(r'^\d{4}-\d{2}-\d{2}-(.*)\.md$', filename)
                if match_filename:
                    slug = match_filename.group(1)
                    post_url = f"{BASE_URL}{slug}/"

                    xml_content.append('    <url>')
                    xml_content.append(f'        <loc>{post_url}</loc>')
                    if front_matter['lastmod']:
                        xml_content.append(f'        <lastmod>{front_matter["lastmod"]}</lastmod>')
                    xml_content.append('    </url>')
                else:
                    print(f"⚠️ Peringatan: Melewatkan nama file yang tidak sesuai format YYYY-MM-DD-slug.md: {filename}")
            else:
                print(f"⚠️ Peringatan: Melewatkan file '{filename}' karena tidak ada front matter atau formatnya salah.")

    xml_content.append('</urlset>')
    return '\n'.join(xml_content)


def write_sitemap_file(path, content):
    """Menulis isi sitemap ke file yang ditentukan."""
    dirpath = os.path.dirname(path)
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)
        print(f"📁 Direktori '{dirpath}' berhasil dibuat.")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Sitemap berhasil dibuat: {path}")
    except Exception as e:
        print(f"❌ Error menulis file '{path}': {e}")


def generate_sitemaps():
    """Menginisiasi pembuatan kedua sitemap."""
    content = generate_sitemap_content()
    if content: # Hanya menulis sitemap jika konten berhasil digenerate
        write_sitemap_file(ROOT_SITEMAP, content)
        write_sitemap_file(PUBLIC_SITEMAP, content)
    else:
        print("🛑 Pembuatan sitemap dibatalkan karena tidak ada konten yang digenerate.")


if __name__ == "__main__":
    generate_sitemaps()
