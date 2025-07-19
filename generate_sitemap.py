import os
import glob
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom # Untuk memformat XML agar lebih rapi

# Konfigurasi
WEBSITE_HOST = "kisahcandu.github.io"  # Ganti dengan domain website kamu
POSTS_DIR = "_posts"                   # Lokasi folder postingan kamu
SITEMAP_FILE = "sitemap.xml"           # Nama file sitemap yang akan dibuat
ROBOTS_TXT_FILE = "robots.txt"         # Nama file robots.txt yang akan diperbarui

def get_post_urls_and_lastmod():
    """
    Memindai direktori _posts, mengekstrak URL postingan dan tanggal modifikasi terakhirnya.
    Asumsi: Struktur nama file postingan Jekyll: YYYY-MM-DD-judul-postingan.md
    """
    post_data = []
    # Dapatkan semua file markdown (.md atau .markdown) di dalam direktori _posts
    # dan subdirektorinya secara rekursif
    markdown_files = glob.glob(os.path.join(POSTS_DIR, "**", "*.md"), recursive=True)
    markdown_files.extend(glob.glob(os.path.join(POSTS_DIR, "**", "*.markdown"), recursive=True))

    for filepath in markdown_files:
        filename = os.path.basename(filepath)
        # Ekstrak tanggal dan judul dari nama file
        # Contoh: 2023-10-26-my-awesome-post.md
        parts = filename.split('-', 3) # Pisahkan berdasarkan 3 tanda hubung pertama

        if len(parts) >= 4:
            year = parts[0]
            month = parts[1]
            day = parts[2]
            # Hapus ekstensi .md atau .markdown dan ubah tanda hubung menjadi garis miring untuk path URL
            post_slug = os.path.splitext(parts[3])[0]
            # Pastikan post_slug tidak memiliki garis miring di awal atau akhir
            post_slug = post_slug.strip('/')

            # Buat URL postingan
            # Untuk Jekyll, postingan biasanya berada di /YYYY/MM/DD/title.html
            post_url = f"https://{WEBSITE_HOST}/{year}/{month}/{day}/{post_slug}.html"

            # Dapatkan waktu modifikasi terakhir file
            last_mod_timestamp = os.path.getmtime(filepath)
            # Format tanggal ke ISO 8601 dengan zona waktu UTC (Z)
            last_mod_date = datetime.datetime.fromtimestamp(last_mod_timestamp).isoformat(timespec='seconds') + 'Z'

            post_data.append({"url": post_url, "lastmod": last_mod_date})
        else:
            print(f"Peringatan: Melewati nama file postingan yang tidak valid: {filename}")

    print(f"Ditemukan {len(post_data)} postingan di {POSTS_DIR}.")
    return post_data

def generate_sitemap_xml(post_data, sitemap_file):
    """
    Menghasilkan file sitemap.xml dari daftar data postingan.
    """
    # Buat elemen root 'urlset' dengan namespace sitemap
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    # Tambahkan homepage ke sitemap
    home_url = ET.SubElement(urlset, "url")
    ET.SubElement(home_url, "loc").text = f"https://{WEBSITE_HOST}/"
    # Gunakan waktu saat ini sebagai lastmod untuk homepage
    ET.SubElement(home_url, "lastmod").text = datetime.datetime.now().isoformat(timespec='seconds') + 'Z'

    # Tambahkan setiap postingan ke sitemap
    for post in post_data:
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = post["url"]
        ET.SubElement(url, "lastmod").text = post["lastmod"]

    # Format XML agar lebih rapi (pretty print)
    rough_string = ET.tostring(urlset, 'utf-8')
    reparsed_xml = minidom.parseString(rough_string)
    pretty_xml_as_string = reparsed_xml.toprettyxml(indent="  ", encoding="utf-8").decode('utf-8')

    try:
        with open(sitemap_file, "w", encoding="utf-8") as f:
            f.write(pretty_xml_as_string)
        print(f"Berhasil membuat {sitemap_file}.")
    except Exception as e:
        print(f"Gagal menulis {sitemap_file}: {e}")

def generate_robots_txt(sitemap_url, robots_txt_path):
    """
    Menghasilkan atau memperbarui file robots.txt dengan URL sitemap.
    """
    robots_txt_content = f"""# robots.txt untuk {WEBSITE_HOST}
User-agent: *
Allow: /

Sitemap: {sitemap_url}
"""
    try:
        with open(robots_txt_path, "w") as robots_file:
            robots_file.write(robots_txt_content)
        print(f"Berhasil membuat/memperbarui {robots_txt_path}.")
    except Exception as e:
        print(f"Gagal membuat/memperbarui {robots_txt_path}: {e}")

if __name__ == "__main__":
    # Pastikan direktori _posts ada. Ini penting untuk pengujian lokal.
    if not os.path.exists(POSTS_DIR):
        print(f"Error: Direktori '{POSTS_DIR}' tidak ditemukan. Mohon buat atau sesuaikan POSTS_DIR.")
        # Untuk demonstrasi, mari kita buat direktori _posts dan file dummy
        os.makedirs(POSTS_DIR, exist_ok=True)
        with open(os.path.join(POSTS_DIR, "2023-01-01-hello-world.md"), "w") as f:
            f.write("---\ntitle: Hello World\n---\nIni adalah postingan pertamaku.")
        with open(os.path.join(POSTS_DIR, "2023-01-05-another-post.md"), "w") as f:
            f.write("---\ntitle: Another Post\n---\nIni adalah postingan lainnya.")
        print(f"Membuat direktori '{POSTS_DIR}' dan file dummy untuk pengujian.")

    # Langkah 1: Dapatkan data postingan
    posts = get_post_urls_and_lastmod()

    # Langkah 2: Buat sitemap.xml
    generate_sitemap_xml(posts, SITEMAP_FILE)

    # Langkah 3: Buat/perbarui robots.txt
    sitemap_full_url = f"https://{WEBSITE_HOST}/{SITEMAP_FILE}"
    generate_robots_txt(sitemap_full_url, ROBOTS_TXT_FILE)
