import json, urllib.request, ssl, re, os
from collections import defaultdict

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'identity'}

with open(r'E:\HCL\fonts\font_download_links_data.json', encoding='utf-8') as f:
    data = json.load(f)

by_url = defaultdict(list)
for d in data:
    by_url[d['download_url']].append(d)

github_urls = {u: by_url[u] for u in by_url if 'github.com' in u and 'releases' in u}
direct_file_urls = {u: by_url[u] for u in by_url if any(u.lower().endswith(ext) for ext in ['.ttf', '.otf', '.zip', '.woff2', '.woff'])}
google_urls = {u: by_url[u] for u in by_url if 'fonts.google.com' in u}

print('URL Types:')
print(f'  GitHub releases: {len(github_urls)}')
print(f'  Direct file URLs: {len(direct_file_urls)}')
print(f'  Google Fonts: {len(google_urls)}')
print(f'  Other: {len(by_url) - len(github_urls) - len(direct_file_urls) - len(google_urls)}')
print()

# Google Fonts CSS samples
print('=== Google Fonts CSS Samples ===')
for url in list(google_urls)[:5]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            woffs = re.findall(r'https://fonts\.[^)\s"]+\.woff2[^)\s"]*', content)
            print(f'URL: {url}')
            print(f'  Fonts: {[f["font_name"] for f in google_urls[url]]}')
            print(f'  Found woff2: {len(woffs)}')
            for w in woffs[:1]:
                print(f'    {w[:120]}')
    except Exception as e:
        print(f'Error: {e}')
    print()

# Direct file samples
print('=== Direct File URL Samples ===')
for url in list(direct_file_urls)[:10]:
    fonts = direct_file_urls[url]
    print(f'URL: {url}')
    print(f'  Fonts: {[f["font_name"] for f in fonts]}')
    print()

# GitHub samples
print('=== GitHub Release URL Samples ===')
for url in list(github_urls)[:5]:
    fonts = github_urls[url]
    print(f'URL: {url}')
    print(f'  Fonts: {[f["font_name"] for f in fonts]}')
    print()