# Append part 3: curl helpers + downloaders + main
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SCRIPT_DIR, "download_all_fonts.py")

content = r'''
# ============================================================
# curl-based HTTP helpers (bypass Python 3.14 SSL issues)
# ============================================================
def curl_get(url, timeout=30, headers=None):
    """HTTP GET via curl. Returns (text_body, status_code)."""
    cmd = ['curl', '-sk', '-L', '--max-time', str(timeout),
           '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
           '-w', '\n%{http_code}']
    if headers:
        for k, v in headers.items():
            cmd.extend(['-H', f'{k}: {v}'])
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
        if r.returncode != 0:
            return None, 0
        text = r.stdout.decode('utf-8', errors='replace')
        lines = text.rsplit('\n', 1)
        body = lines[0] if len(lines) > 1 else text
        try:
            status = int(lines[-1].strip()) if len(lines) > 1 else 0
        except ValueError:
            status = 0
        return body, status
    except Exception as e:
        print(f"    curl error: {e}")
        return None, 0


def curl_download(url, filepath, timeout=300, max_retries=2):
    """Download a file via curl with retry. Returns file size or None."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"    Retry {attempt}/{max_retries}...")
            time.sleep(2)
        cmd = ['curl', '-sk', '-L', '--max-time', str(timeout),
               '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
               '-o', filepath, '-w', '%{http_code}', url]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
            status = r.stdout.strip()
            if r.returncode == 0 and os.path.exists(filepath):
                size = os.path.getsize(filepath)
                if size > 0 and status.startswith('2'):
                    print(f"    Downloaded: {os.path.basename(filepath)} ({size:,} bytes)")
                    return size
                elif size == 0:
                    os.remove(filepath)
                    print(f"    Empty file (HTTP {status})")
                elif size < 1000:
                    with open(filepath, 'rb') as f:
                        head = f.read(200)
                    if b'<html' in head.lower() or b'error' in head.lower() or b'404' in head:
                        os.remove(filepath)
                        print(f"    Got error page (HTTP {status})")
                        continue
                    return size
                else:
                    return size
            else:
                print(f"    curl failed (exit={r.returncode}, HTTP {status})")
        except subprocess.TimeoutExpired:
            print(f"    Timeout after {timeout}s")
        except Exception as e:
            print(f"    Download error: {e}")
    return None


def curl_get_json(url, timeout=15):
    """GET JSON via curl. Returns parsed dict/list or None."""
    data, status = curl_get(url, timeout=timeout,
                            headers={'Accept': 'application/vnd.github.v3+json'})
    if data and status == 200:
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None
    return None


def safe_filename(name):
    """Sanitize a string for use as filename."""
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# ============================================================
# Excel reader
# ============================================================
def load_fonts_from_excel():
    """Read font data from the Excel file."""
    print(f"Reading Excel: {EXCEL_FILE}")
    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb.worksheets[1]  # Sheet 2 = font details
    fonts = []
    for row in ws.iter_rows(min_row=5, values_only=True):
        font_name, cn_name, vendor, license_type, link, note = row
        if font_name is None or link is None:
            continue
        fonts.append({
            "font_name": str(font_name).strip(),
            "cn_name": str(cn_name or "").strip(),
            "vendor": str(vendor or "Unknown").strip(),
            "license": str(license_type or "Unknown").strip(),
            "link": str(link).strip(),
            "note": str(note or "").strip(),
        })
    print(f"Loaded {len(fonts)} font records")
    return fonts


def filter_fonts(fonts, license_filter="free", vendor_keyword=None):
    if license_filter == "free":
        result = [f for f in fonts if f["license"] in FREE_COMMERCIAL]
        label = "free commercial"
    elif license_filter == "personal":
        result = [f for f in fonts if f["license"] in FREE_PERSONAL]
        label = "free personal"
    elif license_filter == "all":
        result = [f for f in fonts if f["license"] not in SKIP_LICENSES]
        label = "all downloadable (excl. paid/system)"
    elif license_filter == "none":
        result = list(fonts)
        label = "no filter"
    else:
        result = list(fonts)
        label = "no filter"
    if vendor_keyword:
        result = [f for f in result if vendor_keyword.lower() in f["vendor"].lower()]
        label += f" + vendor contains '{vendor_keyword}'"
    print(f"Filter [{label}]: {len(result)} fonts")
    return result
'''

with open(OUT, 'a', encoding='utf-8') as f:
    f.write(content)

print(f"Part 3 written, total: {os.path.getsize(OUT)} bytes")
