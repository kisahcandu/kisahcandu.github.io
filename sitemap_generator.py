import os
import re
import datetime

# Direktori postingan
POSTS_DIR = '_posts'
# Nama file output
SITEMAP_XML_FILE = 'sitemap.xml'
SITEMAP_XSL_FILE = 'wp-sitemap.xsl' # Ini akan menjadi file XSL manual yang kamu buat
# URL dasar situs kamu (ganti dengan URL GitHub Pages kamu)
BASE_URL = 'https://kisahcandu.github.io' # Contoh: 'https://your-username.github.io/your-repo/'

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

def generate_sitemap_xml():
    """Menghasilkan sitemap.xml."""
    xml_content = []
    xml_content.append('<?xml version="1.0" encoding="UTF-8"?>')
    # Baris ini memanggil file XSL yang sudah ada secara statis
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
                    year = parts[0]
                    month = parts[1]
                    day = parts[2]
                    slug = parts[3].replace('.md', '')
                    
                    post_url = f"{BASE_URL}/{slug}/"
                    
                    xml_content.append('    <url>')
                    xml_content.append(f'        <loc>{post_url}</loc>')
                    if front_matter['lastmod']:
                        xml_content.append(f'        <lastmod>{front_matter["lastmod"]}</lastmod>')
                    # Kita tidak menambahkan changefreq atau priority karena biasanya tidak ada di front matter postingan sederhana
                    xml_content.append('    </url>')
                else:
                    print(f"Skipping malformed filename: {filename}")
    
    xml_content.append('</urlset>')
    
    with open(SITEMAP_XML_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(xml_content))
    print(f"Sitemap XML berhasil dibuat: {SITEMAP_XML_FILE}")

if __name__ == "__main__":
    generate_sitemap_xml()
