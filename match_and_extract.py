import os, zipfile, re, json
from collections import defaultdict

SAVE_DIR = r'E:\HCL\fonts\unmatched_fonts'
UNMATCHED_FILE = r'E:\HCL\fonts\unmatched_fonts.txt'
DOWNLOADS_DIR = r'E:\HCL\fonts\downloads'
os.makedirs(SAVE_DIR, exist_ok=True)

with open(UNMATCHED_FILE, encoding='utf-8', errors='replace') as f:
    unmatched = [l.strip() for l in f if l.strip()]
unmatched_set = set(unmatched)
print(f'Unmatched fonts: {len(unmatched)}')

with open(r'E:\HCL\fonts\font_download_links_data.json', encoding='utf-8') as f:
    links_data = {d['font_name']: d for d in json.load(f)}

zips = [f for f in os.listdir(DOWNLOADS_DIR) if f.endswith('.zip')]
print(f'Zip files: {len(zips)}')

def normalize(name):
    """Remove common suffixes/variants for matching"""
    n = name.strip()
    # Remove common style suffixes
    n = re.sub(r'[-_]?(Regular|Bold|Italic|Light|Medium|Heavy|BoldItalic|ExtraLight|ExtraBold|SemiBold|Thin|Black|Oblique|UltraLight)$', '', n, flags=re.IGNORECASE)
    # Remove file extensions
    n = re.sub(r'\.(ttf|otf|woff2?|TTF|OTF|WOFF2?)$', '', n, flags=re.IGNORECASE)
    # Remove common separators
    n = re.sub(r'[-_]', '', n)
    return n.lower()

# Build a quick lookup: normalized name -> original name
norm_to_orig = {}
for u in unmatched:
    norm = normalize(u)
    if norm not in norm_to_orig:
        norm_to_orig[norm] = u
    # Also store individual words
    for part in re.split(r'[-_\s]+', u):
        if len(part) > 3:
            norm_to_orig[part.lower()] = u

matched = []
not_matched = []
errors = []

for i, zip_name in enumerate(zips):
    if i % 500 == 0:
        print(f'Progress: {i}/{len(zips)}, matched={len(matched)}')
    
    zip_path = os.path.join(DOWNLOADS_DIR, zip_name)
    base = zip_name.replace('.zip', '').rsplit('_', 1)[0] if '_' in zip_name else zip_name.replace('.zip', '')
    base_clean = normalize(base)
    
    found = False
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            font_files = [n for n in zf.namelist() if n.lower().endswith(('.ttf', '.otf', '.woff', '.woff2'))]
            if not font_files:
                not_matched.append((zip_name, 'no font file'))
                continue
            
            # Strategy: only use the zip filename to determine if it matches
            # Match against unmatched by normalized name OR by original name
            matched_font = None
            ext = None
            
            # Check 1: zip base name directly matches an unmatched name
            if base in unmatched_set:
                matched_font = base
                found = True
            
            # Check 2: normalized zip base matches
            elif base_clean in norm_to_orig:
                matched_font = norm_to_orig[base_clean]
                found = True
            
            # Check 3: try to extract font name from inside zip and match
            if not found:
                for fname in font_files:
                    fn = os.path.basename(fname)
                    fn_base = normalize(fn)
                    
                    if fn_base in norm_to_orig:
                        matched_font = norm_to_orig[fn_base]
                        found = True
                        break
                    if fn_base in unmatched_set:
                        matched_font = fn_base
                        found = True
                        break
            
            # Check 4: partial match - zip base contains an unmatched name (longer than 6 chars)
            if not found:
                for um in unmatched:
                    if len(um) > 5:
                        um_norm = normalize(um)
                        # Only match if it's a substantial match (not just 4-5 chars)
                        if um_norm in base_clean or base_clean in um_norm:
                            if abs(len(um_norm) - len(base_clean)) < 5:
                                matched_font = um
                                found = True
                                break
            
            if found and matched_font:
                # Get the font data - prefer OTF/TTF over woff
                font_data = None
                font_source = None
                for fname in font_files:
                    if fname.lower().endswith(('.otf', '.ttf')):
                        font_data = zf.read(fname)
                        font_source = fname
                        break
                if not font_data and font_files:
                    font_data = zf.read(font_files[0])
                    font_source = font_files[0]
                
                if font_data:
                    # Determine extension
                    if font_source.lower().endswith('.otf'):
                        ext = 'otf'
                    elif font_source.lower().endswith('.woff2'):
                        ext = 'woff2'
                    elif font_source.lower().endswith('.woff'):
                        ext = 'woff'
                    else:
                        ext = 'ttf'
                    
                    safe = re.sub(r'[<>:"/\\|?*]', '_', matched_font)
                    out_path = os.path.join(SAVE_DIR, f'{safe}.{ext}')
                    
                    with open(out_path, 'wb') as f:
                        f.write(font_data)
                    
                    matched.append((matched_font, zip_name, out_path))
                    found = True
            else:
                not_matched.append((zip_name, base))
    except Exception as e:
        errors.append((zip_name, str(e)))

print(f'\n=== Results ===')
print(f'Matched: {len(matched)}')
print(f'Not matched: {len(not_matched)}')
print(f'Errors: {len(errors)}')

print('\nMatched:')
for m, z, p in matched[:30]:
    print(f'  {m} <- {z}')
if len(matched) > 30:
    print(f'  ... +{len(matched)-30} more')

with open(r'E:\HCL\fonts\matched_from_downloads.json', 'w', encoding='utf-8') as f:
    json.dump([{'original': m, 'zip': z, 'saved': p} for m, z, p in matched], f, ensure_ascii=False, indent=2)
print('\nSaved matched_from_downloads.json')