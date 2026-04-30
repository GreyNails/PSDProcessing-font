# Append part 5: remaining downloaders + dispatcher + main
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SCRIPT_DIR, "download_all_fonts.py")

content = r'''

def download_harmonyos(font, progress, download_dir):
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
'''

with open(OUT, 'a', encoding='utf-8') as f:
    f.write(content)

print(f"Part 5 written, total: {os.path.getsize(OUT)} bytes")
