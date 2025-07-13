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
        date_match = re.search(r'date:\s*([\d-]+)', front_matter_str)

        title = title_match.group(1).strip().strip('"\'') if title_match else 'No Title'
        date_str = date_match.group(1).strip() if date_match else None

        lastmod = None
        if date_str:
            try:
                dt_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                lastmod = dt_obj.isoformat(timespec='seconds') + '+00:00'
            except ValueError:
                pass

        return {'title': title, 'date': date_str, 'lastmod': lastmod}
    return None


def generate_sitemap_content():
    """Menghasilkan isi sitemap.xml sebagai list baris XML."""
    xml_content = []
    xml_content.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_content.append(f'<?xml-stylesheet type="text/xsl" href="{BASE_URL}{SITEMAP_XSL_FILE}" ?>')
    xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for filename in os.listdir(POSTS_DIR):
        if filename.endswith('.md'):
            filepath = os.path.join(POSTS_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            front_matter = extract_front_matter(content)

            if front_matter:
                parts = filename.split('-', 3)
                if len(parts) >= 4:
                    slug = parts[3].replace('.md', '')
                    post_url = f"{BASE_URL}{slug}/"

                    xml_content.append('    <url>')
                    xml_content.append(f'        <loc>{post_url}</loc>')
                    if front_matter['lastmod']:
                        xml_content.append(f'        <lastmod>{front_matter["lastmod"]}</lastmod>')
                    xml_content.append('    </url>')
                else:
                    print(f"Skipping malformed filename: {filename}")

    xml_content.append('</urlset>')
    return '\n'.join(xml_content)


def write_sitemap_file(path, content):
    dirpath = os.path.dirname(path)
    if dirpath:  # hanya buat folder jika ada direktori
        os.makedirs(dirpath, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Sitemap berhasil dibuat: {path}")


def generate_sitemaps():
    content = generate_sitemap_content()
    write_sitemap_file(ROOT_SITEMAP, content)
    write_sitemap_file(PUBLIC_SITEMAP, content)


if __name__ == "__main__":
    generate_sitemaps()
