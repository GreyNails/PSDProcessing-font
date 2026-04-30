import json, urllib.request, ssl, re, zipfile, io, os, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Accept-Encoding': 'identity'}

with open(r'E:\HCL\fonts\font_download_links_data.json', encoding='utf-8') as f:
    data = json.load(f)

SAVE_DIR = r'E:\HCL\fonts\unmatched_fonts'
os.makedirs(SAVE_DIR, exist_ok=True)

def http_get(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read(), resp.geturl()
    except Exception as e:
        return None, None

def save_font(fn, data, subdir=''):
    if data[:4] == b'OTTO': ext = 'otf'
    elif data[:4] == b'\x00\x01\x00\x00': ext = 'ttf'
    elif data[:4] == b'wOF': ext = 'woff'
    elif data[:4] == b'wOF2': ext = 'woff2'
    else: ext = 'otf'

    safe = re.sub(r'[<>:"/\\|?*]', '_', fn)
    d = os.path.join(SAVE_DIR, subdir) if subdir else SAVE_DIR
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f'{safe}.{ext}')
    if os.path.exists(path):
        with open(path, 'rb') as f: existing = f.read()
        if existing == data: return 'skipped'
    with open(path, 'wb') as f: f.write(data)
    return 'saved'

# Group by download URL pattern
from collections import defaultdict
by_url = defaultdict(list)
for d in data:
    by_url[d['download_url']].append(d)

print(f'Total fonts: {len(data)}, Unique URLs: {len(by_url)}')
print()

downloaded = []
failed = []
skipped_urls = set()

# Priority 1: Google Fonts (small, direct)
gf_urls = {u for u in by_url if 'fonts.google.com' in u}
print(f'=== Google Fonts URLs: {len(gf_urls)} ===')
for url in gf_urls:
    fonts = by_url[url]
    print(f'  URL: {url}')
    print(f'  Fonts: {[f["font_name"] for f in fonts]}')
    # Google Fonts CSS page - we need to find the actual font file URL
    content, final_url = http_get(url)
    if content:
        # Extract .woff2 URLs from CSS
        woff_urls = re.findall(r'https://fonts\.[^)\s"]+\.woff2[^)\s"]*', content.decode('utf-8', errors='replace'))
        print(f'  Found woff2: {len(woff_urls)}')
        for woff_url in woff_urls:
            fn = fonts[0]['font_name']  # Simplified
            result = save_font(fn, b'', 'GoogleFonts')
    print()

print()
print(f'=== Direct-file URLs ===')
# Priority 2: Direct file URLs (ending in .ttf/.otf/.zip)
direct = {u: by_url[u] for u in by_url if any(u.lower().endswith(ext) for ext in ['.ttf', '.otf', '.zip', '.woff2', '.woff'])}
for url, fonts in direct.items():
    print(f'URL: {url}')
    print(f'Fonts: {[f["font_name"] for f in fonts]}')
    print()

print()
print(f'=== GitHub releases ===')
github = {u: by_url[u] for u in by_url if 'github.com' in u and 'releases' in u}
for url, fonts in github.items():
    print(f'URL: {url}')
    print(f'Fonts: {[f["font_name"] for f in fonts]}')