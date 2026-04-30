# Append part 4: source-specific downloaders
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SCRIPT_DIR, "download_all_fonts.py")

content = r'''

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


def download_harmonyos(font, progress, download_dir):
    """Download HarmonyOS Sans fonts."""
    vendor_dir = os.path.join(download_dir, "HarmonyOS")
    os.makedirs(vendor_dir, exist_ok=True)

    urls = [
        "https://developer.huawei.com/images/download/general/HarmonyOS-Sans.zip",
        "https://communityfile-drcn.op.dbankcloud.cn/FileServer/getFile/cmtyPub/011/111/111/0000000000011111111.20230517162753.zip",
    ]

    filepath = os.path.join(vendor_dir, "HarmonyOS-Sans.zip")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        print(f"    [SKIP] Already exists: HarmonyOS-Sans.zip")
        return True

    for url in urls:
        print(f"    Trying: {url[:80]}...")
        result = curl_download(url, filepath, timeout=120)
        if result:
            return True

    print(f"    Visit https://developer.harmonyos.com/cn/design/resource to download")
    return False


def download_misans(font, progress, download_dir):
    """Download MiSans fonts."""
    vendor_dir = os.path.join(download_dir, "MiSans")
    os.makedirs(vendor_dir, exist_ok=True)

    urls = [
        "https://hyperos.mi.com/font-download/MiSans.zip",
        "https://cdn.cnbj1.fds.api.mi-img.com/vipmlmodel/font/MiSans/MiSans.zip",
    ]

    filepath = os.path.join(vendor_dir, "MiSans.zip")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        print(f"    [SKIP] Already exists: MiSans.zip")
        return True

    for url in urls:
        print(f"    Trying: {url[:80]}...")
        result = curl_download(url, filepath, timeout=120)
        if result:
            return True

    print(f"    Visit https://hyperos.mi.com/font/ to download MiSans")
    return False
'''

with open(OUT, 'a', encoding='utf-8') as f:
    f.write(content)

print(f"Part 4 written, total: {os.path.getsize(OUT)} bytes")
