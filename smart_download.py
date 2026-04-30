import json, os, zipfile, re, struct

UNMATCHED_FILE = r'E:\HCL\fonts\unmatched_fonts.txt'
SAVE_DIR = r'E:\HCL\fonts\unmatched_fonts'
os.makedirs(SAVE_DIR, exist_ok=True)

with open(UNMATCHED_FILE, encoding='utf-8', errors='replace') as f:
    unmatched = [l.strip() for l in f if l.strip()]
unmatched_set = set(unmatched)
unmatched_lower = {u.lower(): u for u in unmatched}
print(f'Unmatched fonts: {len(unmatched)}')

# Load links data
with open(r'E:\HCL\fonts\font_download_links_data.json', encoding='utf-8') as f:
    links_data = {d['font_name']: d for d in json.load(f)}

def read_font_name(data):
    '''Read font name from TTF/OTF name table - try all platforms'''
    try:
        if data[:4] == b'OTTO':
            off = 4
        elif data[:4] == b'\x00\x01\x00\x00':
            off = 4
        else:
            return None
        num_tables = struct.unpack('>H', data[off+4:off+6])[0]
        
        name_off, name_len = None, None
        for i in range(num_tables):
            rec = off + 12 + i * 16
            if data[rec:rec+4] == b'name':
                name_off = struct.unpack('>I', data[rec+8:rec+12])[0]
                name_len = struct.unpack('>I', data[rec+12:rec+16])[0]
                break
        if name_off is None:
            return None
        
        count = struct.unpack('>H', data[name_off:name_off+2])[0]
        str_base = struct.unpack('>H', data[name_off+2:name_off+4])[0]
        
        results = {}
        pos = name_off + 4
        for i in range(count):
            platform = struct.unpack('>H', data[pos:pos+2])[0]
            encoding = struct.unpack('>H', data[pos+2:pos+4])[0]
            language = struct.unpack('>H', data[pos+4:pos+6])[0]
            name_id = struct.unpack('>H', data[pos+6:pos+8])[0]
            byte_len = struct.unpack('>H', data[pos+8:pos+10])[0]
            str_offset = struct.unpack('>H', data[pos+10:pos+12])[0]
            pos += 12
            
            if byte_len == 0 or name_id not in (1, 4, 6):
                continue
            
            # Try different encodings
            str_start = name_off + str_base + str_offset
            str_data = data[str_start:str_start+byte_len]
            
            name = None
            if platform == 3 and encoding == 1:  # Windows Unicode BMP
                name = str_data.decode('utf-16-be', errors='replace').strip('\x00')
            elif platform == 1 and encoding == 0:  # Mac Roman
                name = str_data.decode('mac-roman', errors='replace').strip('\x00')
            elif platform == 0:  # Unicode
                name = str_data.decode('utf-16-be', errors='replace').strip('\x00')
            
            if name and len(name) > 1:
                if name_id not in results:
                    results[name_id] = set()
                results[name_id].add(name)
        
        # Return nameID 6 > 4 > 1
        for nid in (6, 4, 1):
            if nid in results:
                return list(results[nid])[0]
        return None
    except:
        return None

def normalize_name(name):
    n = re.sub(r'[-_]', '', name.strip())
    return n.lower()

def font_matches(font_name, unmatched_list):
    '''Check if font name matches any unmatched font'''
    fn = font_name.strip()
    if fn in unmatched_set:
        return fn
    fn_norm = normalize_name(fn)
    for u in unmatched_list:
        un = normalize_name(u)
        if un == fn_norm or un in fn_norm or fn_norm in un:
            if abs(len(un) - len(fn_norm)) < 6:
                return u
    return None

# ─── Phase 1: Scan downloads folder (zip files from webfontfree.com) ───
DOWNLOADS_DIR = r'E:\HCL\fonts\downloads'
zips = sorted([f for f in os.listdir(DOWNLOADS_DIR) if f.endswith('.zip')])
print(f'Phase 1: Scanning {len(zips)} zip files from downloads/...')

downloaded = []
skipped = 0
errors = 0

for i, zip_name in enumerate(zips):
    if i % 500 == 0:
        print(f'  Progress: {i}/{len(zips)}, downloaded={len(downloaded)}')
    
    zip_path = os.path.join(DOWNLOADS_DIR, zip_name)
    
    # Get expected font name from zip filename
    base = zip_name.replace('.zip', '').rsplit('_', 1)[0]
    base_match = font_matches(base, unmatched)
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            font_files = [n for n in zf.namelist() 
                          if n.lower().endswith(('.ttf', '.otf')) and not n.endswith('/')]
            
            if not font_files:
                skipped += 1
                continue
            
            # Read all font names from inside
            found_name = None
            found_data = None
            
            # First: try font name from inside zip
            for fname in font_files:
                fd = zf.read(fname)
                extracted_name = read_font_name(fd)
                if extracted_name:
                    match = font_matches(extracted_name, unmatched)
                    if match:
                        found_name = match
                        found_data = fd
                        break
            
            # Fallback: use zip filename match
            if not found_name and base_match:
                for fname in font_files:
                    fd = zf.read(fname)
                    if fname.lower().endswith('.otf'):
                        found_name = base_match
                        found_data = fd
                        break
                if not found_data:
                    found_name = base_match
                    found_data = zf.read(font_files[0])
            
            if found_name and found_data:
                ext = 'otf' if font_files[0].lower().endswith('.otf') else 'ttf'
                safe = re.sub(r'[<>:"/\\|?*]', '_', found_name)
                out_path = os.path.join(SAVE_DIR, f'{safe}.{ext}')
                
                # Don't overwrite existing (unless we have a reason to update)
                if not os.path.exists(out_path):
                    with open(out_path, 'wb') as f:
                        f.write(found_data)
                    downloaded.append((found_name, zip_name, out_path))
                else:
                    skipped += 1
            else:
                skipped += 1
    except Exception as e:
        errors += 1

print(f'Phase 1 done: downloaded={len(downloaded)}, skipped={skipped}, errors={errors}')

# Save progress
progress = {}
for fn, zn, path in downloaded:
    progress[fn] = path

with open(r'E:\HCL\fonts\download_phase1.json', 'w', encoding='utf-8') as f:
    json.dump({'downloaded': [{'font': fn, 'zip': zn, 'path': p} for fn, zn, p in downloaded],
              'skipped': skipped, 'errors': errors}, f, ensure_ascii=False, indent=2)

print(f'\nPhase 1 results:')
for fn, zn, p in downloaded[:20]:
    print(f'  {fn}')
if len(downloaded) > 20:
    print(f'  ... +{len(downloaded)-20} more')

# ─── Phase 2: GitHub sources ───
print('\nPhase 2: GitHub sources (Source Han, Noto CJK)...')