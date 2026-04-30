#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Font Batch Download Script v2
Uses curl for HTTP (bypasses Python SSL issues in China).
Reads font_download_links.xlsx and downloads fonts from various sources.

Usage:
    python download_all_fonts.py --list                     # List all downloadable fonts
    python download_all_fonts.py --filter free              # Download free commercial fonts
    python download_all_fonts.py --filter all               # Download all non-paid fonts
    python download_all_fonts.py --filter free --max 5      # Test with 5 fonts
    python download_all_fonts.py --vendor "Adobe"           # Filter by vendor keyword
    python download_all_fonts.py --resume                   # Resume interrupted downloads
    python download_all_fonts.py --stats                    # Show download statistics
"""

import openpyxl
import os
import sys
import time
import re
import json
import argparse
import subprocess
from pathlib import Path
from urllib.parse import urlparse, quote, unquote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(SCRIPT_DIR, "font_download_links.xlsx")
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloads")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "download_progress_v2.json")
FAILED_FILE = os.path.join(SCRIPT_DIR, "download_failed_v2.txt")

# GitHub proxy (gh-proxy.com works in China when direct GitHub fails)
GH_PROXY = "https://gh-proxy.com/"

FREE_COMMERCIAL = [
    "免费商用 (SIL OFL)", "免费商用", "免费商用 (IPA OFL类)",
    "免费商用(注册即可)", "免费商用(个人版)", "免费商用 (作者已宣布)",
]
FREE_PERSONAL = [
    "免费个人", "免费非商用", "免费非商用 / 商业需购买",
    "免费非商用 (NC = Non-Commercial)", "免费个人(确认授权)",
    "免费个人 / 商业需联系作者", "需购买商用授权 (个人非商用可下载)",
]
SKIP_LICENSES = [
    "需购买商用授权", "商业付费", "商业", "商业 / 字由客户端",
    "商业 / 已不流通", "商业 / 需确认", "商业 (字库已不活跃)",
    "商业 (字厂已不活跃)", "商业 (Bitstream)", "商业 (Fontfabric)",
    "商业 (Hoefler)", "Windows 系统授权 / 不可单独下载",
    "Windows系统授权 / 商业", "Windows 系统授权",
    "macOS/iOS 系统授权 / 不可单独再分发", "Adobe Creative Cloud 订阅",
    "Trial/Demo (商业)", "Trial / 商业", "需购买授权", "需授权",
]

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


# ============================================================
# Source-specific downloaders
# ============================================================
def download_github_font(font, progress, download_dir):
    """Download font from GitHub releases or repo files, using gh-proxy."""
    link = font["link"]
    font_name = font["font_name"]

    match = re.search(r"github\.com/([^/]+)/([^/]+)", link)
    if not match:
        return False

    owner, repo = match.groups()
    repo = repo.split("/")[0].split("?")[0].rstrip("/")

    vendor_dir = os.path.join(download_dir, safe_filename(font["vendor"]))
    os.makedirs(vendor_dir, exist_ok=True)

    # Strategy 1: GitHub API for releases (via gh-proxy)
    api_url = f"{GH_PROXY}https://api.github.com/repos/{owner}/{repo}/releases"
    releases = curl_get_json(api_url, timeout=20)

    if releases and isinstance(releases, list) and len(releases) > 0:
        latest = releases[0]
        tag = latest.get("tag_name", "unknown")
        assets = latest.get("assets", [])
        print(f"    Release: {tag} ({len(assets)} assets)")

        if assets:
            best = None
            for a in assets:
                name = a["name"].lower()
                if any(kw in name for kw in ["sc", "cn", "simplifiedchinese"]):
                    best = a
                    break
            if not best:
                for a in assets:
                    if a["name"].lower().endswith((".zip", ".ttf", ".otf", ".ttc", ".7z")):
                        best = a
                        break
            if not best and assets:
                best = assets[0]

            if best:
                filename = best["name"]
                filepath = os.path.join(vendor_dir, filename)
                if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                    print(f"    [SKIP] Already exists: {filename}")
                    return True
                dl_url = f"{GH_PROXY}{best['browser_download_url']}"
                print(f"    Downloading: {filename} ({best['size']:,} bytes)")
                result = curl_download(dl_url, filepath, timeout=600)
                if result:
                    return True
                # Fallback: direct
                result = curl_download(best['browser_download_url'], filepath, timeout=600)
                if result:
                    return True

    # Strategy 2: Scrape repo page for font files
    print(f"    No release assets, scanning repo for font files...")
    page_url = f"https://github.com/{owner}/{repo}"
    html, status = curl_get(page_url, timeout=20)
    if html and status == 200:
        font_links = re.findall(
            r'href="(/[^"]+\.(?:ttf|otf|ttc|zip|woff2?))"', html, re.IGNORECASE
        )
        if font_links:
            for fl in font_links[:3]:
                raw_url = f"https://github.com{fl}".replace("/blob/", "/raw/")
                filename = fl.split("/")[-1]
                filepath = os.path.join(vendor_dir, filename)
                if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                    print(f"    [SKIP] Already exists: {filename}")
                    return True
                dl_url = f"{GH_PROXY}{raw_url}"
                print(f"    Downloading repo file: {filename}")
                result = curl_download(dl_url, filepath, timeout=300)
                if result:
                    return True

        # Check subdirectories
        dir_links = re.findall(r'href="(/[^"]+/tree/[^"]+)"', html)
        for dl in dir_links:
            dirname = dl.split("/")[-1].lower()
            if any(kw in dirname for kw in ["font", "release", "build", "dist", "output", "otf", "ttf"]):
                subhtml, _ = curl_get(f"https://github.com{dl}", timeout=15)
                if subhtml:
                    sub_fonts = re.findall(
                        r'href="(/[^"]+\.(?:ttf|otf|ttc|zip))"', subhtml, re.IGNORECASE
                    )
                    for sf in sub_fonts[:3]:
                        raw_url = f"https://github.com{sf}".replace("/blob/", "/raw/")
                        filename = sf.split("/")[-1]
                        filepath = os.path.join(vendor_dir, filename)
                        if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                            print(f"    [SKIP] Already exists: {filename}")
                            return True
                        dl_url = f"{GH_PROXY}{raw_url}"
                        print(f"    Downloading: {filename}")
                        result = curl_download(dl_url, filepath, timeout=300)
                        if result:
                            return True

    print(f"    Could not find downloadable font files in {owner}/{repo}")
    return False


def download_google_fonts(font, progress, download_dir):
    """Download from Google Fonts (may fail in China)."""
    link = font["link"]
    font_name = font["font_name"]
    vendor_dir = os.path.join(download_dir, "Google_Fonts")
    os.makedirs(vendor_dir, exist_ok=True)

    family = None
    if "/specimen/" in link:
        family = link.split("/specimen/")[-1].split("?")[0].replace("+", " ")
    elif "query=" in link:
        family = link.split("query=")[-1].split("&")[0].replace("+", " ")
    if not family:
        family = re.sub(r"[-_](Regular|Bold|Light|Medium|Thin|Black|ExtraBold|SemiBold|ExtraLight|Italic).*", "", font_name)
        family = family.replace("-", " ").replace("_", " ")

    filepath = os.path.join(vendor_dir, f"{safe_filename(family)}.zip")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        print(f"    [SKIP] Already exists: {os.path.basename(filepath)}")
        return True

    url = f"https://fonts.google.com/download?family={quote(family)}"
    print(f"    Downloading from Google Fonts: {family}")
    result = curl_download(url, filepath, timeout=60, max_retries=1)
    if result and result > 1000:
        return True

    print(f"    Google Fonts blocked. Try: {url}")
    return False


def download_alibabafonts(font, progress, download_dir):
    """Download Alibaba/Alimama fonts."""
    font_name = font["font_name"]
    vendor_dir = os.path.join(download_dir, safe_filename(font["vendor"]))
    os.makedirs(vendor_dir, exist_ok=True)

    # Scrape the alibabafonts page for download links
    html, status = curl_get("https://www.alibabafonts.com/", timeout=15)
    if html:
        # Look for CDN/OSS download URLs
        urls = re.findall(r'https?://[^\s"\'<>]+\.zip', html)
        for url in urls:
            if font_name.lower().replace("-", "").replace("_", "") in url.lower().replace("-", "").replace("_", ""):
                filename = url.split("/")[-1]
                filepath = os.path.join(vendor_dir, filename)
                if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
                    print(f"    [SKIP] Already exists: {filename}")
                    return True
                print(f"    Downloading: {filename}")
                result = curl_download(url, filepath, timeout=300)
                if result:
                    return True

    # alibabafonts.com is a SPA, download links are loaded via JS
    # Record for manual download
    print(f"    Visit https://www.alibabafonts.com/ to download {font_name}")
    print(f"    (Alibaba fonts site requires JavaScript, manual download needed)")
    return False





    """Download HarmonyOS Sans fonts."""
    vendor_dir = os.path.join(download_dir, "HarmonyOS")
    os.makedirs(vendor_dir, exist_ok=True)
    filepath = os.path.join(vendor_dir, "HarmonyOS-Sans.zip")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        print(f"    [SKIP] Already exists: HarmonyOS-Sans.zip")
        return True
    urls = [
        "https://developer.huawei.com/images/download/general/HarmonyOS-Sans.zip",
        "https://communityfile-drcn.op.dbankcloud.cn/FileServer/getFile/cmtyPub/011/111/111/0000000000011111111.20230517162753.zip",
    ]
    for url in urls:
        print(f"    Trying: {url[:60]}...")
        result = curl_download(url, filepath, timeout=120)
        if result:
            return True
    print(f"    Visit https://developer.harmonyos.com/cn/design/resource to download")
    return False


def download_misans(font, progress, download_dir):
    """Download MiSans fonts."""
    vendor_dir = os.path.join(download_dir, "MiSans")
    os.makedirs(vendor_dir, exist_ok=True)
    filepath = os.path.join(vendor_dir, "MiSans.zip")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        print(f"    [SKIP] Already exists: MiSans.zip")
        return True
    urls = [
        "https://hyperos.mi.com/font-download/MiSans.zip",
        "https://cdn.cnbj1.fds.api.mi-img.com/vipmlmodel/font/MiSans/MiSans.zip",
    ]
    for url in urls:
        print(f"    Trying: {url[:60]}...")
        result = curl_download(url, filepath, timeout=120)
        if result:
            return True
    print(f"    Visit https://hyperos.mi.com/font/ to download MiSans")
    return False


def download_100font(font, progress, download_dir):
    """Download from 100font.com."""
    vendor_dir = os.path.join(download_dir, "100font")
    os.makedirs(vendor_dir, exist_ok=True)
    font_name = font["font_name"]

    # Scrape 100font.com for the font page
    html, status = curl_get("https://www.100font.com/", timeout=15)
    if html and status == 200:
        # Find thread links that match font name
        threads = re.findall(r'href="(thread-\d+\.htm)"[^>]*>([^<]+)', html)
        for thread_url, thread_title in threads:
            if font_name.lower() in thread_title.lower() or font["cn_name"] in thread_title:
                full_url = f"https://www.100font.com/{thread_url}"
                print(f"    Found page: {thread_title}")
                page_html, _ = curl_get(full_url, timeout=15)
                if page_html:
                    # Look for download links (lanzou, baidu, direct)
                    dl_links = re.findall(r'href="(https?://[^"]*(?:lanzou[a-z]*\.com|pan\.baidu\.com|\.zip|\.ttf)[^"]*)"', page_html, re.IGNORECASE)
                    if dl_links:
                        for dl in dl_links:
                            if dl.lower().endswith(('.zip', '.ttf', '.otf')):
                                filename = dl.split("/")[-1].split("?")[0]
                                filepath = os.path.join(vendor_dir, filename)
                                result = curl_download(dl, filepath, timeout=120)
                                if result:
                                    return True
                        print(f"    Cloud link found: {dl_links[0]}")
                        print(f"    Open in browser to download")
                        return False

    print(f"    Visit https://www.100font.com/ and search for {font['cn_name'] or font_name}")
    return False


def download_zcool(font, progress, download_dir):
    """Download from zcool.com.cn (ZCOOL fonts)."""
    vendor_dir = os.path.join(download_dir, safe_filename(font["vendor"]))
    os.makedirs(vendor_dir, exist_ok=True)
    link = font["link"]

    html, status = curl_get(link, timeout=15)
    if html and status == 200:
        dl_links = re.findall(r'href="([^"]*\.(?:zip|ttf|otf)[^"]*)"', html, re.IGNORECASE)
        for dl in dl_links:
            if not dl.startswith("http"):
                dl = "https://www.zcool.com.cn" + dl
            filename = dl.split("/")[-1].split("?")[0]
            filepath = os.path.join(vendor_dir, filename)
            if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                print(f"    [SKIP] Already exists: {filename}")
                return True
            print(f"    Downloading: {filename}")
            result = curl_download(dl, filepath, timeout=120)
            if result:
                return True

    # ZCOOL fonts are also on GitHub
    zcool_github = {
        "ZCOOLKuaiLe": "AaronBBrown831/TaipeiSansTCBeta",  # placeholder
        "ZCOOLXiaoWei": "AaronBBrown831/TaipeiSansTCBeta",
    }
    print(f"    Visit {link} to download {font['font_name']}")
    return False


def download_58pic(font, progress, download_dir):
    """Download from 58pic.com (Qiantu fonts)."""
    vendor_dir = os.path.join(download_dir, safe_filename(font["vendor"]))
    os.makedirs(vendor_dir, exist_ok=True)
    link = font["link"]

    html, status = curl_get(link, timeout=15)
    if html and status == 200:
        dl_links = re.findall(r'href="([^"]*(?:download|\.zip|\.ttf)[^"]*)"', html, re.IGNORECASE)
        for dl in dl_links:
            if not dl.startswith("http"):
                dl = "https://www.58pic.com" + dl
            if dl.lower().endswith(('.zip', '.ttf', '.otf')):
                filename = dl.split("/")[-1].split("?")[0]
                filepath = os.path.join(vendor_dir, filename)
                result = curl_download(dl, filepath, timeout=120)
                if result:
                    return True

    print(f"    Visit {link} to download (requires login)")
    return False


def download_bytedance(font, progress, download_dir):
    """Download Douyin Sans (ByteDance)."""
    vendor_dir = os.path.join(download_dir, "ByteDance")
    os.makedirs(vendor_dir, exist_ok=True)
    filepath = os.path.join(vendor_dir, "DouyinSansSC.zip")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        print(f"    [SKIP] Already exists")
        return True
    urls = [
        "https://sf3-cdn-tos.douyinstatic.com/obj/eden-cn/lswwheh7nupwnups/DouyinSans/DouyinSansSC.zip",
        "https://sf1-cdn-tos.douyinstatic.com/obj/eden-cn/lswwheh7nupwnups/DouyinSans/DouyinSansSC.zip",
    ]
    for url in urls:
        print(f"    Trying: {url[:60]}...")
        result = curl_download(url, filepath, timeout=120)
        if result:
            return True
    print(f"    Visit {font['link']} to download")
    return False


def download_islide(font, progress, download_dir):
    """Download iSlide fonts."""
    vendor_dir = os.path.join(download_dir, "iSlide")
    os.makedirs(vendor_dir, exist_ok=True)
    link = font["link"]
    html, status = curl_get(link, timeout=15)
    if html and status == 200:
        dl_links = re.findall(r'href="([^"]*\.(?:zip|ttf|otf)[^"]*)"', html, re.IGNORECASE)
        for dl in dl_links:
            if not dl.startswith("http"):
                dl = "https://sponsor.ws" + dl
            filename = dl.split("/")[-1].split("?")[0]
            filepath = os.path.join(vendor_dir, filename)
            if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                print(f"    [SKIP] Already exists: {filename}")
                return True
            result = curl_download(dl, filepath, timeout=120)
            if result:
                return True
    print(f"    Visit {link} to download {font['font_name']}")
    return False


def download_uisdc(font, progress, download_dir):
    """Download from uisdc.com."""
    vendor_dir = os.path.join(download_dir, safe_filename(font["vendor"]))
    os.makedirs(vendor_dir, exist_ok=True)
    link = font["link"]
    html, status = curl_get(link, timeout=15)
    if html and status == 200:
        dl_links = re.findall(r'href="(https?://[^"]*(?:lanzou[a-z]*\.com|pan\.baidu\.com|\.zip|\.ttf)[^"]*)"', html, re.IGNORECASE)
        if dl_links:
            for dl in dl_links:
                if dl.lower().endswith(('.zip', '.ttf', '.otf')):
                    filename = dl.split("/")[-1].split("?")[0]
                    filepath = os.path.join(vendor_dir, filename)
                    result = curl_download(dl, filepath, timeout=120)
                    if result:
                        return True
            print(f"    Cloud link: {dl_links[0]}")
            return False
    print(f"    Visit {link} to download {font['font_name']}")
    return False


def download_naver(font, progress, download_dir):
    """Download Naver/Nanum fonts."""
    vendor_dir = os.path.join(download_dir, "Naver")
    os.makedirs(vendor_dir, exist_ok=True)
    font_name = font["font_name"]
    family = re.sub(r"(ExtraBold|Bold|Light|Regular)$", "", font_name).strip()
    filepath = os.path.join(vendor_dir, f"{safe_filename(family)}.zip")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        print(f"    [SKIP] Already exists")
        return True
    # Try Google Fonts
    url = f"https://fonts.google.com/download?family={quote(family)}"
    result = curl_download(url, filepath, timeout=30, max_retries=0)
    if result and result > 1000:
        return True
    print(f"    Visit https://hangeul.naver.com/font/nanum to download")
    return False


# ============================================================
# Main download dispatcher
# ============================================================
def download_font(font, progress, download_dir):
    """Route a font to the appropriate downloader based on its link domain."""
    font_name = font["font_name"]
    link = font["link"]
    domain = urlparse(link).netloc.lower()

    if progress.get(font_name) == "done":
        return True

    print(f"\n  Font: {font_name} ({font['cn_name']})")
    print(f"  Vendor: {font['vendor']} | License: {font['license']}")
    print(f"  Link: {link}")

    success = False
    try:
        if "github.com" in domain:
            success = download_github_font(font, progress, download_dir)
        elif "fonts.google.com" in domain:
            success = download_google_fonts(font, progress, download_dir)
        elif "alibabafonts.com" in domain:
            success = download_alibabafonts(font, progress, download_dir)
        elif "developer.harmonyos.com" in domain or "developer.huawei.com" in domain:
            success = download_harmonyos(font, progress, download_dir)
        elif "hyperos.mi.com" in domain:
            success = download_misans(font, progress, download_dir)
        elif "100font.com" in domain:
            success = download_100font(font, progress, download_dir)
        elif "zcool.com.cn" in domain:
            success = download_zcool(font, progress, download_dir)
        elif "58pic.com" in domain:
            success = download_58pic(font, progress, download_dir)
        elif "bytednsdoc.com" in domain or "douyin" in link.lower():
            success = download_bytedance(font, progress, download_dir)
        elif "sponsor.ws" in domain:
            success = download_islide(font, progress, download_dir)
        elif "uisdc.com" in domain:
            success = download_uisdc(font, progress, download_dir)
        elif "hangeul.naver.com" in domain:
            success = download_naver(font, progress, download_dir)
        elif link.lower().endswith((".ttf", ".otf", ".ttc", ".zip", ".woff2", ".woff")):
            vendor_dir = os.path.join(download_dir, safe_filename(font["vendor"]))
            ext = os.path.splitext(link)[1]
            filepath = os.path.join(vendor_dir, f"{safe_filename(font_name)}{ext}")
            if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                print(f"    [SKIP] Already exists")
                success = True
            else:
                print(f"    Direct download: {link}")
                result = curl_download(link, filepath, timeout=120)
                success = result is not None
        else:
            vendor_dir = os.path.join(download_dir, safe_filename(font["vendor"]))
            os.makedirs(vendor_dir, exist_ok=True)
            manual_file = os.path.join(vendor_dir, "_MANUAL_DOWNLOAD.txt")
            with open(manual_file, "a", encoding="utf-8") as f:
                f.write(f"{font_name}\t{font['cn_name']}\t{link}\n")
            print(f"    [MANUAL] Recorded for manual download: {link}")
            success = False
    except Exception as e:
        print(f"    [ERROR] {e}")
        success = False

    if success:
        progress[font_name] = "done"
        print(f"    [OK] {font_name}")
    else:
        progress[font_name] = "failed"
        print(f"    [FAIL] {font_name}")

    return success


# ============================================================
# Deduplication
# ============================================================
def deduplicate_downloads(fonts):
    """Group fonts sharing the same download URL."""
    groups = {}
    for font in fonts:
        link = font["link"]
        if link not in groups:
            groups[link] = []
        groups[link].append(font)
    result = [(group[0], group) for group in groups.values()]
    print(f"Deduplicated: {len(fonts)} fonts -> {len(result)} unique download sources")
    return result


# ============================================================
# CLI and main
# ============================================================
def print_stats(progress, fonts):
    done = sum(1 for v in progress.values() if v == "done")
    failed = sum(1 for v in progress.values() if v == "failed")
    manual = sum(1 for v in progress.values() if v == "manual")
    total = len(fonts)
    remaining = total - done - failed - manual

    print(f"\n{'='*60}")
    print(f"Download Statistics")
    print(f"{'='*60}")
    print(f"Total fonts in Excel:  {total}")
    print(f"Downloaded (done):     {done}")
    print(f"Failed:                {failed}")
    print(f"Manual needed:         {manual}")
    print(f"Remaining:             {remaining}")
    print(f"{'='*60}")

    if failed > 0:
        print(f"\nFailed fonts:")
        for font in fonts:
            if progress.get(font["font_name"]) == "failed":
                print(f"  - {font['font_name']} ({font['vendor']}) -> {font['link']}")


def main():
    parser = argparse.ArgumentParser(description="Font Batch Download Script v2 (curl-based)")
    parser.add_argument("--filter", choices=["free", "personal", "all", "none"],
                        default="free",
                        help="License filter (default: free)")
    parser.add_argument("--vendor", type=str, default=None,
                        help="Filter by vendor keyword")
    parser.add_argument("--max", type=int, default=None,
                        help="Max number of fonts to download")
    parser.add_argument("--list", action="store_true",
                        help="List fonts only, do not download")
    parser.add_argument("--stats", action="store_true",
                        help="Show download statistics")
    parser.add_argument("--resume", action="store_true",
                        help="Resume: skip already downloaded fonts")
    parser.add_argument("--reset", action="store_true",
                        help="Reset progress and start fresh")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory (default: ./downloads)")
    parser.add_argument("--no-proxy", action="store_true",
                        help="Disable gh-proxy.com for GitHub")
    args = parser.parse_args()

    # Check curl is available
    try:
        subprocess.run(['curl', '--version'], capture_output=True, timeout=5)
    except Exception:
        print("ERROR: curl is required but not found. Install curl and try again.")
        sys.exit(1)

    # Load data
    fonts = load_fonts_from_excel()
    progress = load_progress()

    if args.reset:
        progress = {}
        save_progress(progress)
        print("Progress reset.")

    if args.no_proxy:
        global GH_PROXY
        GH_PROXY = ""

    download_dir = args.output or DOWNLOAD_DIR
    os.makedirs(download_dir, exist_ok=True)

    # Filter
    filtered = filter_fonts(fonts, args.filter, args.vendor)

    if args.max:
        filtered = filtered[:args.max]

    if args.stats:
        print_stats(progress, filtered)
        return

    if args.list:
        print(f"\n{'='*80}")
        print(f"Font List ({len(filtered)} fonts)")
        print(f"{'='*80}")
        for i, font in enumerate(filtered, 1):
            status = progress.get(font["font_name"], "pending")
            marker = "[OK]" if status == "done" else "[FAIL]" if status == "failed" else "[ ]"
            print(f"  {i:3d}. {marker} {font['font_name']}")
            print(f"       {font['cn_name']} | {font['vendor']} | {font['license']}")
            print(f"       {font['link']}")
        return

    # Deduplicate and download
    groups = deduplicate_downloads(filtered)

    print(f"\n{'='*60}")
    print(f"Starting download: {len(groups)} sources for {len(filtered)} fonts")
    print(f"Output: {download_dir}")
    print(f"{'='*60}")

    done_count = 0
    fail_count = 0
    skip_count = 0

    for i, (rep_font, group_fonts) in enumerate(groups, 1):
        font_name = rep_font["font_name"]

        # Skip if already done (resume mode)
        if args.resume and progress.get(font_name) == "done":
            skip_count += 1
            continue

        print(f"\n[{i}/{len(groups)}]")
        success = download_font(rep_font, progress, download_dir)

        # Mark all fonts in the group
        for gf in group_fonts:
            if success:
                progress[gf["font_name"]] = "done"
            elif progress.get(gf["font_name"]) != "done":
                progress[gf["font_name"]] = "failed"

        if success:
            done_count += 1
        else:
            fail_count += 1

        save_progress(progress)
        time.sleep(0.5)

    # Summary
    print(f"\n{'='*60}")
    print(f"Download Complete")
    print(f"{'='*60}")
    print(f"  Downloaded: {done_count}")
    print(f"  Failed:     {fail_count}")
    print(f"  Skipped:    {skip_count}")
    print(f"  Total:      {len(groups)}")

    # Write manual download list
    manual_fonts = [f for f in filtered if progress.get(f["font_name"]) in ("failed", "manual")]
    if manual_fonts:
        manual_file = os.path.join(download_dir, "_MANUAL_DOWNLOADS.txt")
        with open(manual_file, "w", encoding="utf-8") as f:
            f.write("# Fonts that need manual download\n")
            f.write("# font_name\tcn_name\tvendor\tlicense\tlink\n")
            for font in manual_fonts:
                f.write(f"{font['font_name']}\t{font['cn_name']}\t{font['vendor']}\t{font['license']}\t{font['link']}\n")
        print(f"\nManual download list: {manual_file}")


if __name__ == "__main__":
    main()
