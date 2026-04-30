#!/usr/bin/env python3
"""Font Downloader - Batch download fonts from various sources"""
import os
import json
import time
import urllib.request
import urllib.error
import ssl
import re
import gzip
import struct
import hashlib

# Configuration
SAVE_DIR = r'E:\HCL\fonts\unmatched_fonts'
DATA_FILE = r'E:\HCL\fonts\font_download_links_data.json'
PROGRESS_FILE = r'E:\HCL\fonts\download_progress.json'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

def load_data():
    with open(DATA_FILE, encoding='utf-8') as f:
        return json.load(f)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_progress(progress):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def http_get(url, headers=None, timeout=30):
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read(), resp.geturl()
    except Exception as e:
        print(f'    HTTP Error: {e}')
        return None, None

def get_github_api(url):
    """Get GitHub API response (unauthenticated, rate limited)"""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'FontDownloader/1.0',
        'Accept': 'application/vnd.github.v3+json'
    })
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f'    GitHub API Error: {e}')
        return None

def download_file(url, filepath, headers=None):
    """Download a file with resume support"""
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            data = resp.read()
            with open(filepath, 'wb') as f:
                f.write(data)
            return len(data)
    except Exception as e:
        print(f'    Download failed: {e}')
        return None

def get_font_format_from_url(url):
    """Determine font format from URL or guess from font name"""
    if '.ttf' in url.lower():
        return 'ttf'
    elif '.otf' in url.lower():
        return 'otf'
    elif '.woff2' in url.lower():
        return 'woff2'
    elif '.woff' in url.lower():
        return 'woff'
    return 'ttf'

def save_font(font_name, data, subdir=''):
    """Save font data to file, detecting format from content"""
    # Detect format from magic bytes
    if data[:4] == b'OTTO':
        ext = 'otf'
    elif data[:4] == b'\x00\x01\x00\x00':
        ext = 'ttf'
    elif data[:4] == b'wOF':
        ext = 'woff'
    elif data[:4] == b'wOF2':
        ext = 'woff2'
    elif data[:4] == b'\xd0\xcf\x11\xe0':  # Old Office format
        ext = 'ttf'
    else:
        ext = 'ttf'
    
    # Sanitize filename
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', font_name)
    save_dir = os.path.join(SAVE_DIR, subdir) if subdir else SAVE_DIR
    os.makedirs(save_dir, exist_ok=True)
    
    filepath = os.path.join(save_dir, f'{safe_name}.{ext}')
    
    # Avoid overwriting existing files unless content differs
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            existing = f.read()
        if existing == data:
            print(f'    [SKIP - identical] {os.path.basename(filepath)}')
            return filepath, 'skipped'
    
    with open(filepath, 'wb') as f:
        f.write(data)
    print(f'    [OK] {os.path.basename(filepath)} ({len(data):,} bytes)')
    return filepath, 'saved'

# ─── Source-specific downloaders ────────────────────────────────────────────

def download_source_han_sans(data, progress, log):
    """Download Source Han Sans from GitHub releases"""
    # These 26 fonts share the same GitHub release URL
    # We need to find the right zip file for each weight
    fonts = [d for d in data if 'github.com/adobe-fonts/source-han-sans' in d['download_url']]
    
    # The GitHub release has multiple ZIPs by weight
    # Regular=1, Medium=2, Bold=3, etc.
    weight_map = {
        'SourceHanSans-Regular': 'SourceHanSans-Regular.zip',
        'SourceHanSans-Bold': 'SourceHanSans-Bold.zip',
        'SourceHanSans-Medium': 'SourceHanSans-Medium.zip',
        'SourceHanSans-Light': 'SourceHanSans-Light.zip',
        'SourceHanSans-ExtraLight': 'SourceHanSans-ExtraLight.zip',
        'SourceHanSans-Heavy': 'SourceHanSans-Heavy.zip',
    }
    
    api_url = 'https://api.github.com/repos/adobe-fonts/source-han-sans/releases/latest'
    release = get_github_api(api_url)
    if not release:
        print('  [ERROR] Could not fetch Source Han Sans release info')
        return
    
    print(f'  Found release: {release.get("tag_name", "unknown")}')
    
    assets = {a['name']: a['browser_download_url'] for a in release.get('assets', [])}
    
    # Map font names to zip files
    font_to_zip = {}
    for font in fonts:
        fn = font['font_name']
        if fn in weight_map:
            zip_name = weight_map[fn]
        else:
            # Try to find by matching the weight name in the font
            for zipn, dl_url in assets.items():
                if fn.replace('SourceHanSans', '')[:4].lower() in zipn.lower():
                    zip_name = zipn
                    break
            else:
                print(f'    [SKIP] No matching zip for {fn}')
                continue
        font_to_zip[fn] = assets.get(zip_name)
    
    # Download each zip
    downloaded_zips = {}
    for fn, dl_url in font_to_zip.items():
        if not dl_url:
            print(f'    [SKIP] No URL for {fn}')
            continue
        print(f'  Downloading {fn}...')
        zip_path = os.path.join(SAVE_DIR, f'_temp_{fn}.zip')
        size = download_file(dl_url, zip_path)
        if size:
            downloaded_zips[fn] = zip_path
        time.sleep(0.5)
    
    # Extract and save individual fonts from zips
    for fn, zip_path in downloaded_zips.items():
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith(('.otf', '.ttf')) and fn.replace('SourceHanSans-', '') in name:
                        # Extract the specific font
                        data = zf.read(name)
                        save_font(fn, data, 'SourceHanSans')
                        break
            os.remove(zip_path)
        except Exception as e:
            print(f'    [ERROR] Extracting {zip_path}: {e}')
    
    for fn in font_to_zip:
        progress[fn] = 'done'

def download_source_han_serif(data, progress, log):
    """Download Source Han Serif from GitHub"""
    fonts = [d for d in data if 'github.com/adobe-fonts/source-han-serif' in d['download_url']]
    api_url = 'https://api.github.com/repos/adobe-fonts/source-han-serif/releases/latest'
    release = get_github_api(api_url)
    if not release:
        print('  [ERROR] Could not fetch Source Han Serif release info')
        return
    
    assets = {a['name']: a['browser_download_url'] for a in release.get('assets', [])}
    print(f'  Found {len(assets)} assets')
    
    for font in fonts:
        fn = font['font_name']
        print(f'  Processing {fn}...')
        
        # Find matching zip
        search_terms = fn.replace('SourceHanSerif', '').replace('CN', '').replace('JP', '').replace('SC', '').replace('TC', '').strip('-')
        matching_zip = None
        for zip_name, dl_url in assets.items():
            if search_terms.lower() in zip_name.lower() or fn.lower() in zip_name.lower():
                matching_zip = (zip_name, dl_url)
                break
        
        if not matching_zip:
            # Try regex patterns
            for zip_name, dl_url in assets.items():
                if zip_name.startswith('SourceHanSerif') and '.zip' in zip_name:
                    print(f'    Trying {zip_name}...')
                    zip_path = os.path.join(SAVE_DIR, f'_temp_{fn}.zip')
                    size = download_file(dl_url, zip_path)
                    if size:
                        try:
                            import zipfile
                            with zipfile.ZipFile(zip_path, 'r') as zf:
                                for zname in zf.namelist():
                                    if zname.endswith('.otf'):
                                        font_data = zf.read(zname)
                                        save_font(fn, font_data, 'SourceHanSerif')
                                        break
                            os.remove(zip_path)
                        except Exception as e:
                            print(f'    [ERROR] {e}')
                    break
            continue
        
        zip_name, dl_url = matching_zip
        zip_path = os.path.join(SAVE_DIR, f'_temp_{fn}.zip')
        size = download_file(dl_url, zip_path)
        if size:
            try:
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for zname in zf.namelist():
                        if zname.endswith('.otf'):
                            font_data = zf.read(zname)
                            save_font(fn, font_data, 'SourceHanSerif')
                            break
                os.remove(zip_path)
            except Exception as e:
                print(f'    [ERROR] {e}')
        
        progress[fn] = 'done'
        time.sleep(0.5)

def download_noto_cjk(data, progress, log):
    """Download Noto CJK from GitHub"""
    fonts = [d for d in data if 'github.com/notofonts/noto-cjk' in d['download_url']]
    
    # noto-cjk repo has fonts by script/region
    # SC (Simplified Chinese) fonts are in separate zips
    api_url = 'https://api.github.com/repos/notofonts/noto-cjk/releases/latest'
    release = get_github_api(api_url)
    if not release:
        print('  [ERROR] Could not fetch Noto CJK release info')
        return
    
    assets = {a['name']: a['browser_download_url'] for a in release.get('assets', [])}
    print(f'  Found {len(assets)} assets')
    
    for font in fonts:
        fn = font['font_name']
        print(f'  Processing {fn}...')
        
        # Find matching zip
        # e.g., NotoSansCJKsc-Bold.zip, NotoSerifCJKsc-Bold.zip
        is_serif = 'Serif' in fn
        region = 'SC' if 'SC' in fn or 'Hans' in fn else ('TC' if 'TC' in fn or 'Hant' in fn else 'SC')
        weight = fn.split('-')[-1] if '-' in fn else 'Regular'
        
        if is_serif:
            base_name = f'NotoSerifCJK{region}-{weight}.zip'
        else:
            base_name = f'NotoSansCJK{region}-{weight}.zip'
        
        dl_url = assets.get(base_name)
        if not dl_url:
            # Try alternative naming
            for an, au in assets.items():
                if fn.replace('NotoSansCJK', '').replace('NotoSerifCJK', '').lower() in an.lower():
                    dl_url = au
                    break
        
        if not dl_url:
            print(f'    [SKIP] No matching asset for {fn}')
            continue
        
        zip_path = os.path.join(SAVE_DIR, f'_temp_{fn}.zip')
        size = download_file(dl_url, zip_path)
        if size:
            try:
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for zname in zf.namelist():
                        if zname.endswith('.otf'):
                            font_data = zf.read(zname)
                            save_font(fn, font_data, 'NotoCJK')
                            break
                os.remove(zip_path)
            except Exception as e:
                print(f'    [ERROR] {e}')
        
        progress[fn] = 'done'
        time.sleep(0.5)

def download_github_generic(data, progress, log):
    """Generic GitHub downloader for other repos"""
    github_data = [d for d in data if 'github.com' in d['download_url'] 
                   and 'adobe-fonts/source-han-sans' not in d['download_url']
                   and 'adobe-fonts/source-han-serif' not in d['download_url']
                   and 'notofonts/noto-cjk' not in d['download_url']]
    
    # Group by repo
    from collections import defaultdict
    by_repo = defaultdict(list)
    for font in github_data:
        url = font['download_url']
        # Extract owner/repo from github URL
        m = re.search(r'github\.com/([^/]+/[^/]+)/releases?', url)
        if m:
            by_repo[m.group(1)].append(font)
    
    for repo, fonts in by_repo.items():
        print(f'\n  Processing repo: {repo} ({len(fonts)} fonts)')
        api_url = f'https://api.github.com/repos/{repo}/releases/latest'
        release = get_github_api(api_url)
        if not release:
            # Try tags
            api_url = f'https://api.github.com/repos/{repo}/tags'
            tags = get_github_api(api_url)
            if tags and len(tags) > 0:
                # Try first tag
                tag_name = tags[0]['name']
                api_url = f'https://api.github.com/repos/{repo}/releases/tags/{tag_name}'
                release = get_github_api(api_url)
        
        if not release:
            print(f'    [ERROR] Could not fetch release for {repo}')
            for font in fonts:
                progress[font['font_name']] = 'error'
            continue
        
        assets = {a['name']: a['browser_download_url'] for a in release.get('assets', [])}
        print(f'    Found release with {len(assets)} assets')
        
        for font in fonts:
            fn = font['font_name']
            print(f'    Processing {fn}...')
            
            # Find matching asset
            dl_url = None
            # Try exact match in assets
            for an in assets:
                if fn in an or an.replace('-', '').replace('_', '') in fn.replace('-', '').replace('_', ''):
                    dl_url = assets[an]
                    break
            
            if not dl_url:
                # Try partial match
                for an, au in assets.items():
                    if fn.split('-')[0].lower() in an.lower():
                        dl_url = au
                        break
            
            if not dl_url:
                print(f'      [SKIP] No matching asset for {fn}')
                progress[fn] = 'skipped'
                continue
            
            zip_path = os.path.join(SAVE_DIR, f'_temp_{fn}.zip')
            size = download_file(dl_url, zip_path)
            if size:
                try:
                    import zipfile
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        for zname in zf.namelist():
                            if zname.endswith(('.otf', '.ttf', '.woff', '.woff2')):
                                fd = zf.read(zname)
                                save_font(fn, fd, repo.replace('/', '_'))
                                break
                        else:
                            print(f'      [WARN] No font file found in zip')
                    os.remove(zip_path)
                except Exception as e:
                    print(f'      [ERROR] {e}')
            else:
                progress[fn] = 'error'
            
            progress[fn] = 'done'
            time.sleep(0.3)

def main():
    data = load_data()
    progress = load_progress()
    log = []
    
    print(f'Loaded {len(data)} fonts')
    print(f'Already done: {sum(1 for v in progress.values() if v == "done")}')
    
    # Identify sources
    github_shan = [d for d in data if 'github.com/adobe-fonts/source-han-sans' in d['download_url']]
    github_serif = [d for d in data if 'github.com/adobe-fonts/source-han-serif' in d['download_url']]
    github_noto = [d for d in data if 'github.com/notofonts/noto-cjk' in d['download_url']]
    github_other = [d for d in data if 'github.com' in d['download_url'] 
                    and d not in github_shan and d not in github_serif and d not in github_noto]
    
    # System fonts (Windows/Mac) - skip download, mark as system
    system_data = [d for d in data if d['source'] in ['微软 Windows / Office', 'Apple macOS / iOS 系统']]
    
    print(f'\nSource breakdown:')
    print(f'  Source Han Sans (GitHub): {len(github_shan)}')
    print(f'  Source Han Serif (GitHub): {len(github_serif)}')
    print(f'  Noto CJK (GitHub): {len(github_noto)}')
    print(f'  Other GitHub: {len(github_other)}')
    print(f'  System fonts (skip): {len(system_data)}')
    
    # Mark system fonts as done
    for d in system_data:
        progress[d['font_name']] = 'system'
    
    # Download GitHub fonts
    print('\n=== Downloading Source Han Sans ===')
    download_source_han_sans(data, progress, log)
    save_progress(progress)
    
    print('\n=== Downloading Source Han Serif ===')
    download_source_han_serif(data, progress, log)
    save_progress(progress)
    
    print('\n=== Downloading Noto CJK ===')
    download_noto_cjk(data, progress, log)
    save_progress(progress)
    
    print('\n=== Downloading Other GitHub Fonts ===')
    download_github_generic(data, progress, log)
    save_progress(progress)
    
    save_progress(progress)
    
    # Summary
    done = sum(1 for v in progress.values() if v == 'done')
    skipped = sum(1 for v in progress.values() if v == 'skipped')
    system = sum(1 for v in progress.values() if v == 'system')
    error = sum(1 for v in progress.values() if v == 'error')
    total = len(data)
    
    print(f'\n=== Summary ===')
    print(f'Total fonts: {total}')
    print(f'  Downloaded: {done}')
    print(f'  System (skip): {system}')
    print(f'  Skipped: {skipped}')
    print(f'  Error: {error}')
    print(f'  Remaining: {total - done - skipped - system - error}')

if __name__ == '__main__':
    main()
