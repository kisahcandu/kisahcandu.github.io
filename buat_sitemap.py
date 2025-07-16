import os

def generate_post_sitemap_txt(base_url, posts_folder='_posts', output_file='sitemap.txt'):
    """
    Menghasilkan file sitemap.txt hanya untuk postingan dari folder _posts.

    Args:
        base_url (str): URL dasar situs GitHub Pages Anda (misal: "https://username.github.io").
        posts_folder (str): Nama folder tempat artikel Markdown Anda berada.
        output_file (str): Nama file output untuk sitemap.
    """
    sitemap_urls = []

    # --- Tambahkan URL Artikel dari Folder _posts ---
    if os.path.exists(posts_folder) and os.path.isdir(posts_folder):
        for filename in os.listdir(posts_folder):
            if filename.endswith(('.md', '.markdown')):
                # Asumsi format nama file: YYYY-MM-DD-judul-artikel.md
                parts = filename.split('-', 3) # Pisahkan berdasarkan 3 dash pertama
                if len(parts) >= 4: # Pastikan ada cukup bagian untuk tanggal dan judul
                    year = parts[0]
                    month = parts[1]
                    day = parts[2]
                    # Hapus ekstensi .md atau .markdown dan ubah menjadi .html
                    slug = os.path.splitext(parts[3])[0]
                    article_url = f"{base_url}/{slug}/"
                    sitemap_urls.append(article_url)
                else:
                    print(f"Peringatan: Format nama file tidak dikenali untuk {filename}. Dilewati.")
    else:
        print(f"Peringatan: Folder '{posts_folder}' tidak ditemukan. Artikel tidak akan ditambahkan ke sitemap.")
        print("Pastikan Anda menjalankan skrip ini di direktori root repositori GitHub Pages Anda.")


    # --- Tulis Sitemap ke File ---
    if sitemap_urls: # Hanya menulis jika ada URL yang ditemukan
        with open(output_file, 'w') as f:
            for url in sorted(sitemap_urls): # Urutkan URL agar lebih rapi
                f.write(url + '\n')
        print(f"File '{output_file}' berhasil dibuat dengan {len(sitemap_urls)} URL postingan.")
    else:
        print(f"Tidak ada URL postingan yang ditemukan di folder '{posts_folder}'. File '{output_file}' tidak dibuat.")


# --- Cara Menggunakan ---
if __name__ == "__main__":
    # GANTI INI dengan URL dasar situs GitHub Pages Anda
    YOUR_BASE_URL = "https://kisahcandu.github.io" # <-- Ganti USERNAME di sini!

    # Jalankan fungsi
    generate_post_sitemap_txt(YOUR_BASE_URL)
