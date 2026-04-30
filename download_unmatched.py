import os
import re
import json
import requests
import zipfile
import time
import threading
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# ============================================================
# 配置
# ============================================================
FONT_LIST_FILE = r"E:\HCL\fonts\unmatched_fonts.txt"
SAVE_DIR = r"E:\HCL\fonts\unmatched_fonts"
LOG_SUCCESS = os.path.join(SAVE_DIR, "_download_success.txt")
LOG_FAIL = os.path.join(SAVE_DIR, "_download_fail.txt")
MAX_WORKERS = 8  # 并发线程数，可根据网络情况调整

# 线程安全打印
_print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

# ============================================================
# 工具函数
# ============================================================

def create_session():
    """创建带有重试机制的 Session"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def is_font_content(content):
    """检查二进制内容是否为有效的字体文件格式"""
    if len(content) < 4:
        return False
    header = content[:4]
    # TTF, OTF, TTC, WOFF, WOFF2, ZIP
    return header in (
        b"\x00\x01\x00\x00",  # TTF
        b"OTTO",               # OTF
        b"ttcf",               # TTC
        b"wOFF",               # WOFF
        b"wOF2",               # WOFF2
        b"PK\x03\x04",        # ZIP
    )


def save_file(content, dest_path):
    """将字节内容保存到文件，如果是 zip 则解压。返回 True 仅当内容是有效字体。"""
    # 先验证内容是否为字体/zip 格式，拒绝 HTML 等无效响应
    if not is_font_content(content):
        return False

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    # 检查是否是 zip
    if content[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(BytesIO(content)) as z:
                font_exts = (".ttf", ".otf", ".woff", ".woff2", ".ttc")
                font_files = [
                    f for f in z.namelist()
                    if any(f.lower().endswith(ext) for ext in font_exts)
                ]
                if font_files:
                    dest_dir = os.path.splitext(dest_path)[0]
                    os.makedirs(dest_dir, exist_ok=True)
                    for ff in font_files:
                        z.extract(ff, dest_dir)
                    return True
                else:
                    return False  # zip 里没有字体文件，视为无效
        except zipfile.BadZipFile:
            return False

    # 是有效字体格式（TTF/OTF/TTC/WOFF/WOFF2），直接保存
    with open(dest_path, "wb") as f:
        f.write(content)
    return True


def already_downloaded(font_name, save_dir):
    """检查字体是否已经下载过"""
    # 检查目录
    font_dir = os.path.join(save_dir, font_name)
    if os.path.isdir(font_dir) and os.listdir(font_dir):
        return True
    # 检查常见文件
    for ext in (".ttf", ".otf", ".zip", ".woff2", ".ttc"):
        if os.path.isfile(os.path.join(save_dir, font_name + ext)):
            return True
    return False


# ============================================================
# 下载源 1: Google Fonts
# ============================================================

def try_google_fonts(font_name, save_dir, session):
    """尝试从 Google Fonts 下载"""
    # 从字体名推断 family 名称
    # 例如 SourceHanSansCN-Regular -> Source+Han+Sans+CN
    # NotoSansHans-Regular -> Noto+Sans+Hans
    base = font_name.split("-")[0]

    # 驼峰拆分
    family = re.sub(r"([a-z])([A-Z])", r"\1+\2", base)
    family = family.replace("_", "+").replace(" ", "+")

    variants = list(dict.fromkeys([
        family,
        font_name.replace("-", "+").replace("_", "+"),
        base.replace("_", "+"),
    ]))

    for variant in variants:
        url = f"https://fonts.google.com/download?family={variant}"
        try:
            resp = session.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 1000:
                dest = os.path.join(save_dir, f"{font_name}.zip")
                if save_file(resp.content, dest):
                    return True
        except Exception:
            pass
    return False


# ============================================================
# 下载源 2: freefontdownload.org (TTF + OTF)
# ============================================================

def try_freefontdownload(font_name, save_dir, session):
    """尝试从 freefontdownload.org 下载"""
    urls = [
        f"https://www.freefontdownload.org/download-font/{font_name}",
        f"https://www.freefontdownload.org/download-font-otf/{font_name}",
    ]
    for url in urls:
        try:
            resp = session.get(url, headers=HEADERS, timeout=(10, 30))
            if resp.status_code == 200 and len(resp.content) > 1000:
                ct = resp.headers.get("content-type", "")
                if "zip" in ct or "octet" in ct or "font" in ct or resp.content[:4] == b"PK\x03\x04":
                    ext = ".zip" if resp.content[:4] == b"PK\x03\x04" else ".zip"
                    dest = os.path.join(save_dir, f"{font_name}{ext}")
                    if save_file(resp.content, dest):
                        return True
        except Exception:
            pass
    return False


# ============================================================
# 下载源 3: GitHub Releases (Source Han Sans/Serif, Noto CJK)
# ============================================================

# 映射: 字体前缀 -> (GitHub owner/repo, release tag 模式, 资源文件名模式)
GITHUB_FONT_MAP = {
    # Source Han Sans
    "SourceHanSansCN": {
        "repo": "adobe-fonts/source-han-sans",
        "tag": "2.004R",
        "assets": ["SourceHanSansCN.zip"],
    },
    "SourceHanSansSC": {
        "repo": "adobe-fonts/source-han-sans",
        "tag": "2.004R",
        "assets": ["SourceHanSansSC.zip"],
    },
    "SourceHanSansK": {
        "repo": "adobe-fonts/source-han-sans",
        "tag": "2.004R",
        "assets": ["SourceHanSansK.zip"],
    },
    "SourceHanSansOLD": {
        "repo": "adobe-fonts/source-han-sans",
        "tag": "2.004R",
        "assets": ["SourceHanSans.zip"],
    },
    # Source Han Serif
    "SourceHanSerifCN": {
        "repo": "adobe-fonts/source-han-serif",
        "tag": "2.003R",
        "assets": ["SourceHanSerifCN.zip"],
    },
    "SourceHanSerifSC": {
        "repo": "adobe-fonts/source-han-serif",
        "tag": "2.003R",
        "assets": ["SourceHanSerifSC.zip"],
    },
    "SourceHanSerifTC": {
        "repo": "adobe-fonts/source-han-serif",
        "tag": "2.003R",
        "assets": ["SourceHanSerifTC.zip"],
    },
}

# Noto CJK 字体
NOTO_MAP = {
    "NotoSansHans": {
        "repo": "notofonts/noto-cjk",
        "tag": "Sans2.004",
        "assets": ["08_NotoSansCJKsc.zip"],
    },
    "NotoSerifCJKsc": {
        "repo": "notofonts/noto-cjk",
        "tag": "Serif2.003",
        "assets": ["09_NotoSerifCJKsc.zip"],
    },
    "NotoSansCJKsc": {
        "repo": "notofonts/noto-cjk",
        "tag": "Sans2.004",
        "assets": ["08_NotoSansCJKsc.zip"],
    },
}


def try_github_release(font_name, save_dir, session):
    """尝试从 GitHub Releases 下载"""
    base = font_name.split("-")[0]

    # 合并两个映射
    all_maps = {**GITHUB_FONT_MAP, **NOTO_MAP}

    info = None
    for prefix, cfg in all_maps.items():
        if base.startswith(prefix) or font_name.startswith(prefix):
            info = cfg
            break

    if not info:
        return False

    repo = info["repo"]
    tag = info["tag"]

    for asset_name in info["assets"]:
        url = f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"
        try:
            resp = session.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 1000:
                dest = os.path.join(save_dir, f"{base}.zip")
                if save_file(resp.content, dest):
                    return True
        except Exception:
            pass

    return False


# ============================================================
# 下载源 4: 字魂 (zihun) 字体 - 从官网尝试
# ============================================================

def try_zihun(font_name, save_dir, session):
    """尝试从字魂网站下载免费字体"""
    # 字魂字体通常需要从官网下载，这里尝试常见的下载链接模式
    # 字魂免费字体可以从多个镜像站获取
    variants = [font_name]
    if "-Regular" in font_name:
        variants.append(font_name.replace("-Regular", ""))
    if "-" not in font_name:
        variants.append(font_name + "-Regular")

    for variant in variants:
        urls = [
            f"https://www.freefontdownload.org/download-font/{variant}",
            f"https://www.freefontdownload.org/download-font-otf/{variant}",
        ]
        for url in urls:
            try:
                resp = session.get(url, headers=HEADERS, timeout=(10, 30))
                if resp.status_code == 200 and len(resp.content) > 1000:
                    ct = resp.headers.get("content-type", "")
                    if "zip" in ct or "octet" in ct or "font" in ct or resp.content[:4] == b"PK\x03\x04":
                        dest = os.path.join(save_dir, f"{font_name}.zip")
                        if save_file(resp.content, dest):
                            return True
            except Exception:
                pass
    return False


# ============================================================
# 下载源 5: DaFont (搜索 + 下载)
# ============================================================

def _dafont_search_slugs(font_name, session):
    """
    在 DaFont 搜索字体，从搜索结果页面提取所有下载 slug。
    返回去重后的 slug 列表。
    """
    base = font_name.split("-")[0]
    # 驼峰拆分为空格，方便搜索
    search_term = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)
    search_term = search_term.replace("_", " ")

    slugs = []
    try:
        url = f"https://www.dafont.com/search.php?q={requests.utils.quote(search_term)}"
        resp = session.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            # 提取所有下载链接: href="//dl.dafont.com/dl/?f=slug"
            found = re.findall(r'dl\.dafont\.com/dl/\?f=([a-z0-9_]+)', resp.text)
            slugs.extend(found)
    except Exception:
        pass

    # 也尝试直接猜测 slug 格式
    guesses = set()
    # moonbright -> moonbright
    guesses.add(font_name.lower())
    # MoonBright -> moon_bright
    guesses.add(re.sub(r"([a-z])([A-Z])", r"\1_\2", font_name).lower())
    # moon-bright -> moon_bright
    guesses.add(font_name.lower().replace("-", "_"))
    # moon_bright-Regular -> moon_bright
    guesses.add(base.lower())
    guesses.add(re.sub(r"([a-z])([A-Z])", r"\1_\2", base).lower())
    guesses.add(base.lower().replace("-", "_"))

    for g in guesses:
        if g and g not in slugs:
            slugs.append(g)

    return list(dict.fromkeys(slugs))  # 保持顺序去重


def try_dafont(font_name, save_dir, session):
    """
    从 DaFont 搜索并下载字体。
    先搜索获取真实 slug，再用 dl.dafont.com 下载。
    """
    slugs = _dafont_search_slugs(font_name, session)

    for slug in slugs:
        url = f"https://dl.dafont.com/dl/?f={slug}"
        try:
            resp = session.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 500:
                dest = os.path.join(save_dir, f"{font_name}.zip")
                if save_file(resp.content, dest):
                    return True
        except Exception:
            pass
    return False


# ============================================================
# 下载源 6: webfontfree.com (搜索 + AJAX + 下载)
# ============================================================

def _webfontfree_search(font_name, session):
    """
    在 webfontfree.com 搜索字体，返回匹配的 URL 名称列表。
    """
    base = font_name.split("-")[0]
    search_term = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)
    search_term = search_term.replace("_", " ")

    results = []
    try:
        url = f"https://www.webfontfree.com/en/search?q={requests.utils.quote(search_term)}"
        resp = session.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            # 提取 /en/download/FontName 中的 FontName
            found = re.findall(
                r'href="https://www\.webfontfree\.com/en/download/([^"]+)"',
                resp.text,
            )
            results = list(dict.fromkeys(found))
    except Exception:
        pass

    # 把精确匹配排在前面
    exact = []
    others = []
    for r in results:
        if r.lower() == font_name.lower() or r.lower() == base.lower():
            exact.append(r)
        else:
            others.append(r)
    return exact + others


def try_webfontfree(font_name, save_dir, session):
    """
    从 webfontfree.com 搜索并下载字体。
    流程: 搜索 -> AJAX 获取下载链接 -> 下载 ZIP
    """
    candidates = _webfontfree_search(font_name, session)
    if not candidates:
        # 没搜到也直接用字体名试一次
        candidates = [font_name]

    # AJAX 请求专用 headers，不发送 Accept-Encoding 避免 zstd 压缩问题
    ajax_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Referer": "https://www.webfontfree.com/",
        "Origin": "https://www.webfontfree.com",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }

    for candidate in candidates[:5]:  # 最多试 5 个
        try:
            payload = {
                "title": candidate,
                "format[]": ["ttf"],
                "id[]": [candidate],
            }
            resp = session.post(
                "https://g.webfontfree.com/en/ajax/downloads",
                data=payload,
                headers=ajax_headers,
                timeout=15,
            )
            if resp.status_code != 200:
                continue

            j = json.loads(resp.content.decode("utf-8"))
            if j.get("Type") != "Success" or not j.get("Data"):
                continue

            # 下载 ZIP
            zip_url = j["Data"]
            resp2 = session.get(
                zip_url,
                headers={"User-Agent": HEADERS["User-Agent"]},
                timeout=30,
            )
            if resp2.status_code == 200 and len(resp2.content) > 500:
                dest = os.path.join(save_dir, f"{font_name}.zip")
                if save_file(resp2.content, dest):
                    return True
        except Exception:
            pass

    return False


# ============================================================
# 下载源 7: Fontshare (api.fontshare.com)
# ============================================================

# 缓存 Fontshare 字体列表 (slug 映射)
_fontshare_cache = {}
_fontshare_lock = threading.Lock()


def _fontshare_get_slug(font_name, session):
    """
    从 Fontshare API 获取字体 slug。
    首次调用时加载全部字体列表并缓存。
    """
    global _fontshare_cache
    with _fontshare_lock:
        if not _fontshare_cache:
            try:
                resp = session.get(
                    "https://api.fontshare.com/v2/fonts?limit=500&offset=0",
                    headers=HEADERS, timeout=15,
                )
                if resp.status_code == 200:
                    j = resp.json()
                    for f in j.get("fonts", []):
                        slug = f.get("slug", "")
                        name = f.get("name", "")
                        # 多种匹配键
                        _fontshare_cache[slug.lower()] = slug
                        _fontshare_cache[name.lower().replace(" ", "-")] = slug
                        _fontshare_cache[name.lower().replace(" ", "")] = slug
            except Exception:
                pass

    base = font_name.split("-")[0].lower()
    return (
        _fontshare_cache.get(font_name.lower())
        or _fontshare_cache.get(base)
        or _fontshare_cache.get(re.sub(r"([a-z])([A-Z])", r"\1-\2", base).lower())
    )


def try_fontshare(font_name, save_dir, session):
    """从 Fontshare 下载字体 (直接 ZIP)"""
    slug = _fontshare_get_slug(font_name, session)
    if not slug:
        return False

    try:
        url = f"https://api.fontshare.com/v2/fonts/download/{slug}"
        resp = session.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 1000:
            dest = os.path.join(save_dir, f"{font_name}.zip")
            if save_file(resp.content, dest):
                return True
    except Exception:
        pass
    return False


# ============================================================
# 下载源 8: Befonts (befonts.com)
# ============================================================

def try_befonts(font_name, save_dir, session):
    """
    从 befonts.com 搜索并下载字体。
    流程: 搜索 -> 详情页 -> 提取 downfile 链接 -> 下载
    """
    base = font_name.split("-")[0]
    search_term = re.sub(r"([a-z])([A-Z])", r"\1+\2", base)

    try:
        resp = session.get(
            f"https://befonts.com/?s={requests.utils.quote(search_term)}",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code != 200:
            return False

        # 提取详情页链接
        detail_links = re.findall(
            r'href="(https://befonts\.com/[^"]+\.html)"', resp.text
        )
        detail_links = list(dict.fromkeys(detail_links))[:5]

        for detail_url in detail_links:
            try:
                resp2 = session.get(detail_url, headers=HEADERS, timeout=15)
                if resp2.status_code != 200:
                    continue

                # 提取 downfile 链接
                dl_links = re.findall(
                    r'href="(https://befonts\.com/downfile/[^"]+)"', resp2.text
                )
                for dl_url in dl_links[:3]:
                    try:
                        resp3 = session.get(
                            dl_url, headers=HEADERS, timeout=30, allow_redirects=True
                        )
                        if resp3.status_code == 200 and len(resp3.content) > 1000:
                            dest = os.path.join(save_dir, f"{font_name}.zip")
                            if save_file(resp3.content, dest):
                                return True
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
    return False


# ============================================================
# 下载源 9: Velvetyne (velvetyne.fr / GitLab)
# ============================================================

def try_velvetyne(font_name, save_dir, session):
    """
    从 Velvetyne 下载开源艺术字体。
    流程: 字体页面 -> 找 GitLab ZIP 链接 -> 下载
    """
    base = font_name.split("-")[0].lower()
    slug = re.sub(r"([a-z])([A-Z])", r"\1-\2", font_name.split("-")[0]).lower()

    # 尝试直接访问字体页面
    for candidate in [slug, base]:
        try:
            url = f"https://velvetyne.fr/fonts/{candidate}/"
            resp = session.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue

            # 找 GitLab ZIP 链接
            gitlab_zips = re.findall(
                r'href="(https://gitlab\.com/[^"]*\.zip[^"]*)"', resp.text
            )
            # 也找下载页面链接
            dl_pages = re.findall(
                r'href="(/fonts/[^"]+/download[^"]*)"', resp.text
            )

            for zip_url in gitlab_zips[:3]:
                try:
                    resp2 = session.get(zip_url, headers=HEADERS, timeout=30)
                    if resp2.status_code == 200 and len(resp2.content) > 500:
                        dest = os.path.join(save_dir, f"{font_name}.zip")
                        if save_file(resp2.content, dest):
                            return True
                except Exception:
                    pass

            for dl_path in dl_pages[:2]:
                try:
                    dl_url = f"https://velvetyne.fr{dl_path}"
                    resp3 = session.get(
                        dl_url, headers=HEADERS, timeout=30, allow_redirects=True
                    )
                    if resp3.status_code == 200 and len(resp3.content) > 500:
                        dest = os.path.join(save_dir, f"{font_name}.zip")
                        if save_file(resp3.content, dest):
                            return True
                except Exception:
                    pass
        except Exception:
            pass
    return False


# ============================================================
# 下载源 10: 字体搬运工 (font.sucai999.com)
# ============================================================

# 缓存字体搬运工的字体列表 {font_id: zip_url}
_sucai999_cache = {}
_sucai999_lock = threading.Lock()


def _sucai999_build_cache(session):
    """遍历字体搬运工所有页面，建立字体名到下载链接的映射"""
    global _sucai999_cache
    with _sucai999_lock:
        if _sucai999_cache:
            return
        cache = {}
        try:
            for page in range(1, 30):
                resp = session.get(
                    f"https://font.sucai999.com/?page={page}",
                    headers=HEADERS, timeout=15,
                )
                if resp.status_code != 200:
                    break
                font_ids = re.findall(r'href="/font/(\d+)\.html"', resp.text)
                font_ids = list(dict.fromkeys(font_ids))
                if not font_ids:
                    break
                for fid in font_ids:
                    cache[fid] = None  # 占位，稍后按需加载
        except Exception:
            pass
        _sucai999_cache = cache if cache else {"_empty": None}


def _sucai999_get_zip_url(font_id, session):
    """获取字体搬运工某个字体的 ZIP 下载链接"""
    try:
        resp = session.get(
            f"https://font.sucai999.com/font/{font_id}.html",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code == 200:
            zips = re.findall(
                r'"(https://fontdown\d*\.sucai999\.com[^"]*\.zip[^"]*)"', resp.text
            )
            if zips:
                return zips[0]
    except Exception:
        pass
    return None


def try_sucai999(font_name, save_dir, session):
    """
    从字体搬运工下载字体。
    由于没有搜索功能，遍历所有字体详情页查找匹配的下载链接。
    """
    _sucai999_build_cache(session)

    base = font_name.split("-")[0].lower()
    search_terms = [
        font_name.lower(),
        base,
        re.sub(r"([a-z])([A-Z])", r"\1 \2", font_name.split("-")[0]).lower(),
    ]

    for fid in list(_sucai999_cache.keys()):
        if fid.startswith("_"):
            continue
        try:
            resp = session.get(
                f"https://font.sucai999.com/font/{fid}.html",
                headers=HEADERS, timeout=10,
            )
            if resp.status_code != 200:
                continue

            page_text = resp.text.lower()
            # 检查页面是否包含字体名
            matched = any(term in page_text for term in search_terms)
            if not matched:
                continue

            # 找 ZIP 链接
            zips = re.findall(
                r'"(https://fontdown\d*\.sucai999\.com[^"]*\.zip[^"]*)"', resp.text
            )
            if zips:
                dl_resp = session.get(zips[0], headers=HEADERS, timeout=30)
                if dl_resp.status_code == 200 and len(dl_resp.content) > 1000:
                    dest = os.path.join(save_dir, f"{font_name}.zip")
                    if save_file(dl_resp.content, dest):
                        return True
        except Exception:
            pass
    return False


# ============================================================
# 下载源 11: 喵闪字库 (miao3.cn)
# ============================================================

def try_miao3(font_name, save_dir, session):
    """
    从喵闪字库下载字体。
    流程: 搜索/首页获取 data-id -> 下载 API 获取 zip_url -> 下载 ZIP
    """
    base = font_name.split("-")[0]
    search_term = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)

    # 收集候选 data-id
    data_ids = []

    try:
        # 先尝试搜索
        resp = session.get(
            f"https://www.miao3.cn/search?keyword={requests.utils.quote(search_term)}",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code == 200:
            ids = re.findall(r'data-id="(\d+)"', resp.text)
            data_ids.extend(list(dict.fromkeys(ids)))
    except Exception:
        pass

    # 如果搜索没结果，也试试中文搜索词
    if not data_ids:
        try:
            resp = session.get(
                f"https://www.miao3.cn/search?keyword={requests.utils.quote(base)}",
                headers=HEADERS, timeout=15,
            )
            if resp.status_code == 200:
                ids = re.findall(r'data-id="(\d+)"', resp.text)
                data_ids.extend(list(dict.fromkeys(ids)))
        except Exception:
            pass

    for fid in data_ids[:5]:
        try:
            dl_resp = session.get(
                f"https://www.miao3.cn/home/index/download?id={fid}",
                headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
                timeout=15,
            )
            if dl_resp.status_code != 200:
                continue

            j = dl_resp.json()
            zip_url = j.get("zip_url", "")
            if j.get("code") == 1 and zip_url:
                # 检查 ZIP 文件名是否匹配字体名
                zip_name = zip_url.rsplit("/", 1)[-1].lower()
                if base.lower() in zip_name or font_name.lower().replace("-", "") in zip_name.replace("-", ""):
                    resp2 = session.get(zip_url, headers=HEADERS, timeout=60)
                    if resp2.status_code == 200 and len(resp2.content) > 500:
                        dest = os.path.join(save_dir, f"{font_name}.zip")
                        if save_file(resp2.content, dest):
                            return True
        except Exception:
            pass

    return False


# ============================================================
# 下载源 12: 字体天下 (fonts.net.cn)
# ============================================================

def try_fontsnetcn(font_name, save_dir, session):
    """
    从字体天下搜索并尝试下载字体。
    注意: 该站点下载需要登录，成功率较低，仅作为兜底。
    """
    base = font_name.split("-")[0]
    # 用中文或英文搜索
    search_term = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)

    try:
        resp = session.get(
            f"https://www.fonts.net.cn/font-search-result.html?q={requests.utils.quote(search_term)}",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code != 200:
            return False

        # 提取搜索结果区域中的字体详情链接
        list_area = re.search(
            r'class="site_font_list">(.*?)class="site_font_list_sub_footer"',
            resp.text, re.DOTALL,
        )
        if not list_area:
            return False

        detail_links = re.findall(r'href="(/font-\d+\.html)"', list_area.group(1))
        detail_links = list(dict.fromkeys(detail_links))[:3]

        for detail_path in detail_links:
            detail_url = f"https://www.fonts.net.cn{detail_path}"
            try:
                resp2 = session.get(detail_url, headers=HEADERS, timeout=15)
                if resp2.status_code != 200:
                    continue

                # 找直接下载链接 (非登录页)
                dl_links = re.findall(
                    r'href="(https?://[^"]*\.(?:zip|ttf|otf|ttc)[^"]*)"',
                    resp2.text, re.I,
                )
                for dl_url in dl_links[:3]:
                    if "fonts.net.cn" in dl_url:
                        continue  # 跳过站内链接
                    try:
                        resp3 = session.get(dl_url, headers=HEADERS, timeout=30)
                        if resp3.status_code == 200 and len(resp3.content) > 1000:
                            dest = os.path.join(save_dir, f"{font_name}.zip")
                            if save_file(resp3.content, dest):
                                return True
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
    return False


# ============================================================
# 下载源 13: 字酷网 (fontku.com)
# ============================================================

def try_fontku(font_name, save_dir, session):
    """
    从字酷网搜索并尝试下载字体。
    """
    base = font_name.split("-")[0]
    search_term = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)

    try:
        resp = session.get(
            f"https://www.fontku.com/search?txt={requests.utils.quote(search_term)}",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code != 200:
            return False

        # 提取字体详情链接
        detail_links = re.findall(
            r'href="(https?://www\.fontku\.com/font/[^"]+)"', resp.text
        )
        detail_links = list(dict.fromkeys(detail_links))[:3]

        for detail_url in detail_links:
            try:
                resp2 = session.get(detail_url, headers=HEADERS, timeout=15)
                if resp2.status_code != 200:
                    continue

                # 找下载链接
                dl_links = re.findall(
                    r'href="([^"]*download[^"]*)"', resp2.text, re.I
                )
                for dl_path in dl_links[:3]:
                    dl_url = dl_path if dl_path.startswith("http") else f"https://www.fontku.com{dl_path}"
                    try:
                        resp3 = session.get(
                            dl_url, headers=HEADERS, timeout=30, allow_redirects=True
                        )
                        if resp3.status_code == 200 and len(resp3.content) > 1000:
                            dest = os.path.join(save_dir, f"{font_name}.zip")
                            if save_file(resp3.content, dest):
                                return True
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
    return False


# ============================================================
# 下载源 14: 大厂字体直接下载 (静态映射)
# ============================================================

# 已知大厂字体的直接下载链接
BRAND_FONT_MAP = {
    # OPPO Sans 3.0
    "OPPOSans": "https://coloros-website-cn.allawnfs.com/font/OPPOSans3.0.zip",
    # 阿里巴巴普惠体 (GitHub)
    "AlibabaPuHuiTi": "https://github.com/alibaba/AlibabaPuHuiTi/releases/download/China99/AlibabaPuHuiTi-3.zip",
    # HarmonyOS Sans (华为开发者资源)
    "HarmonyOSSans": "https://communityfile-drcn.op.dbankcloud.cn/FileServer/getFile/cmtyPub/011/111/111/0000000000011111111.20230517162539.01498498498498498498498498498498:50001231000000:2800:C3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3:20230517162539:HarmonyOS_Sans.zip",
    "HarmonyOS_Sans": "https://communityfile-drcn.op.dbankcloud.cn/FileServer/getFile/cmtyPub/011/111/111/0000000000011111111.20230517162539.01498498498498498498498498498498:50001231000000:2800:C3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3E3:20230517162539:HarmonyOS_Sans.zip",
    # 站酷字体 (Google Fonts GitHub)
    "ZCOOLXiaoWei": "https://github.com/googlefonts/zcool-xiaowei/archive/refs/heads/main.zip",
    "ZCOOLKuaiLe": "https://github.com/googlefonts/zcool-kuaile/archive/refs/heads/main.zip",
    "ZCOOLQingKeHuangYou": "https://github.com/googlefonts/zcool-qingke-huangyou/archive/refs/heads/main.zip",
    # 思源黑体/宋体 (补充常见别名，已在 GITHUB_FONT_MAP 中有部分)
    "NotoSansCJKsc": "https://github.com/notofonts/noto-cjk/releases/download/Sans2.004/03_NotoSansCJKsc.zip",
    "NotoSerifCJKsc": "https://github.com/notofonts/noto-cjk/releases/download/Serif2.003/04_NotoSerifCJKsc.zip",
    # 霞鹜文楷 (使用 GitHub releases latest redirect)
    "LXGWWenKai": "https://github.com/lxgw/LxgwWenKai/releases/latest",
    "LXGWWenKaiMono": "https://github.com/lxgw/LxgwWenKai/releases/latest",
    "LXGWWenKaiGB": "https://github.com/lxgw/LxgwWenKaiGB/releases/latest",
    # 得意黑
    "SmileySans": "https://github.com/atelier-anchor/smiley-sans/releases/latest",
    # 文泉驿
    "WenQuanYi": "https://github.com/nickheal/wenquanyi/archive/refs/heads/main.zip",
}


def try_brand_font(font_name, save_dir, session):
    """
    从大厂字体静态映射表下载。
    匹配字体名前缀。支持直接 ZIP 链接和 GitHub releases/latest 页面。
    """
    base = font_name.split("-")[0]

    # 精确匹配
    url = BRAND_FONT_MAP.get(font_name) or BRAND_FONT_MAP.get(base)
    if not url:
        # 前缀匹配
        for prefix, dl_url in BRAND_FONT_MAP.items():
            if base.startswith(prefix) or font_name.startswith(prefix):
                url = dl_url
                break

    if not url:
        return False

    try:
        # 如果是 GitHub releases/latest 页面，需要解析找到 ZIP 资源
        if "/releases/latest" in url and not url.endswith(".zip"):
            resp = session.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            if resp.status_code == 200:
                # 找页面中的 ZIP 下载链接
                zip_links = re.findall(
                    r'href="([^"]*releases/download/[^"]*\.zip)"', resp.text
                )
                if zip_links:
                    zip_url = zip_links[0]
                    if not zip_url.startswith("http"):
                        zip_url = f"https://github.com{zip_url}"
                    resp2 = session.get(
                        zip_url, headers=HEADERS, timeout=60, allow_redirects=True
                    )
                    if resp2.status_code == 200 and len(resp2.content) > 1000:
                        dest = os.path.join(save_dir, f"{font_name}.zip")
                        if save_file(resp2.content, dest):
                            return True
            return False

        # 直接下载 ZIP (某些 CDN 需要 Referer)
        dl_headers = {**HEADERS}
        if "allawnfs.com" in url:
            dl_headers["Referer"] = "https://www.coloros.com/"
        resp = session.get(url, headers=dl_headers, timeout=120, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 1000:
            dest = os.path.join(save_dir, f"{font_name}.zip")
            if save_file(resp.content, dest):
                return True
    except Exception:
        pass
    return False


# ============================================================
# 下载源 15: 猫啃网 (maoken.com)
# ============================================================

def try_maoken(font_name, save_dir, session):
    """
    从猫啃网搜索并下载字体。
    流程: 搜索 -> 详情页 -> 提取 OSS 直链 -> 下载
    """
    base = font_name.split("-")[0]
    search_term = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)

    try:
        resp = session.get(
            f"https://www.maoken.com/?s={requests.utils.quote(search_term)}",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code != 200:
            return False

        # 提取详情页链接
        detail_links = re.findall(
            r'href="(https://www\.maoken\.com/freefonts/\d+\.html)"', resp.text
        )
        detail_links = list(dict.fromkeys(detail_links))[:5]

        for detail_url in detail_links:
            try:
                resp2 = session.get(detail_url, headers=HEADERS, timeout=15)
                if resp2.status_code != 200:
                    continue

                # 提取 OSS 直链 (阿里云 OSS)
                oss_links = re.findall(
                    r'href="(https://oss\.maoken\.com/[^"]+)"', resp2.text
                )
                for oss_url in oss_links[:3]:
                    try:
                        resp3 = session.get(oss_url, headers=HEADERS, timeout=60)
                        if resp3.status_code == 200 and len(resp3.content) > 1000:
                            dest = os.path.join(save_dir, f"{font_name}.zip")
                            if save_file(resp3.content, dest):
                                return True
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
    return False


# ============================================================
# 下载源 16: 100font (100font.com)
# ============================================================

def try_100font(font_name, save_dir, session):
    """
    从 100font.com 搜索字体。
    注意: 该站点下载链接通常指向网盘，自动化成功率较低。
    """
    base = font_name.split("-")[0]
    search_term = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)

    try:
        encoded = requests.utils.quote(search_term)
        resp = session.get(
            f"https://www.100font.com/search-{encoded}.htm",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code != 200:
            return False

        # 提取详情页链接
        detail_links = re.findall(
            r'href="(https?://www\.100font\.com/thread-\d+\.htm)"', resp.text
        )
        detail_links = list(dict.fromkeys(detail_links))[:3]

        for detail_url in detail_links:
            try:
                resp2 = session.get(detail_url, headers=HEADERS, timeout=15)
                if resp2.status_code != 200:
                    continue

                # 找直接下载链接 (非网盘)
                dl_links = re.findall(
                    r'href="(https?://[^"]*\.(?:zip|ttf|otf)[^"]*)"', resp2.text, re.I
                )
                for dl_url in dl_links[:3]:
                    # 跳过网盘链接
                    if any(d in dl_url for d in ["pan.quark", "pan.baidu", "cloud"]):
                        continue
                    try:
                        resp3 = session.get(dl_url, headers=HEADERS, timeout=30)
                        if resp3.status_code == 200 and len(resp3.content) > 1000:
                            dest = os.path.join(save_dir, f"{font_name}.zip")
                            if save_file(resp3.content, dest):
                                return True
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
    return False


# ============================================================
# 下载源 17: 站酷字体 (zcool.com.cn)
# ============================================================

# 站酷字体 fileId 映射 (从 main.js 提取)
ZCOOL_FONT_MAP = {
    # 免费字体 (event/getFile.do?fileId=xxx)
    "ZCOOLMoDianFang": 738,       # 站酷墨点坊
    "ZCOOLYuFeng": 727,           # 站酷御风体
    "ZCOOLRuiRui": 726,           # 站酷锐锐体
    "ZCOOLShouShu": 725,          # 站酷手书体
    "ZCOOLXiaoWei": 746,          # 站酷小薇体 (小礼细体)
    "ZCOOLXiRanXi": 724,          # 站酷纤细体
    "ZCOOLXiRanCu": 723,          # 站酷纤粗体
    "ZCOOLTong": 722,             # 站酷彤体
    "ZCOOLDream": 721,            # 站酷梦体
    "ZCOOLJianHei": 720,          # 站酷尖黑体
    "ZCOOLMiaoDian": 719,         # 站酷妙典体
    "ZCOOLKuHei": 718,            # 站酷酷黑体
    "ZCOOLQingKeHuangYou": 717,   # 站酷小Q体 / 庆科黄油体
    "ZCOOLKuaiLe": 745,           # 站酷快乐体 (小礼粗体)
    "ZCOOLAdaoXiaoShi": 744,      # 站酷阿刀小石体 (小礼粗体2)
    "ZCOOLYouLiaCuSong": 763,     # 站酷有料粗宋体
    "ZCOOLGaoDeGuo": 797,         # 站酷高德国体
}


def try_zcool(font_name, save_dir, session):
    """
    从站酷字体下载。使用 event/getFile.do API。
    """
    base = font_name.split("-")[0]
    file_id = ZCOOL_FONT_MAP.get(font_name) or ZCOOL_FONT_MAP.get(base)
    if not file_id:
        # 前缀匹配
        for prefix, fid in ZCOOL_FONT_MAP.items():
            if base.startswith(prefix) or font_name.startswith(prefix):
                file_id = fid
                break

    if not file_id:
        return False

    try:
        url = f"https://www.zcool.com.cn/event/getFile.do?fileId={file_id}"
        resp = session.get(
            url,
            headers={**HEADERS, "Referer": "https://www.zcool.com.cn/special/zcoolfonts/"},
            timeout=15,
        )
        if resp.status_code != 200:
            return False

        j = resp.json()
        if not j.get("success") or not j.get("fileUrl"):
            return False

        dl_url = j["fileUrl"]
        resp2 = session.get(dl_url, headers=HEADERS, timeout=60)
        if resp2.status_code == 200 and len(resp2.content) > 1000:
            # 判断文件类型
            ext = ".zip"
            if dl_url.lower().endswith(".rar"):
                ext = ".rar"
            dest = os.path.join(save_dir, f"{font_name}{ext}")
            # RAR 文件直接保存（save_file 只处理 ZIP 和字体格式）
            if ext == ".rar":
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(resp2.content)
                return True
            else:
                if save_file(resp2.content, dest):
                    return True
    except Exception:
        pass
    return False


# ============================================================
# 主逻辑
# ============================================================

def load_font_list(filepath):
    """从文件加载字体名列表"""
    fonts = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                fonts.append(line)
    return fonts


def download_font(font_name, save_dir, session):
    """
    依次尝试多个来源下载字体，成功即返回。
    返回 (bool, str): (是否成功, 来源名称)

    优先级策略:
      - 大厂字体静态映射 (最快，直接命中)
      - GitHub Releases (Source Han, Noto)
      - 站酷字体 (已知映射)
      - Google Fonts
      - Fontshare
      - 猫啃网 (中文字体 OSS 直链)
      - 字体搬运工 (中文字体直接 ZIP)
      - 喵闪字库
      - 100font
      - freefontdownload.org
      - 字魂字体
      - DaFont
      - webfontfree.com
      - Befonts
      - Velvetyne
      - 字体天下 (可能有验证码)
      - 字酷网 (JS 驱动，成功率低)
    """
    base = font_name.split("-")[0]

    # 1) 大厂字体静态映射 (OPPO Sans, 阿里巴巴普惠体, HarmonyOS Sans, 霞鹜文楷, 得意黑等)
    for prefix in BRAND_FONT_MAP:
        if base.startswith(prefix) or font_name.startswith(prefix):
            safe_print(f"    [{font_name}] -> 大厂字体直链 ...")
            if try_brand_font(font_name, save_dir, session):
                return True, "大厂字体直链"
            break

    # 2) GitHub Releases (Source Han, Noto)
    all_gh = {**GITHUB_FONT_MAP, **NOTO_MAP}
    for prefix in all_gh:
        if base.startswith(prefix) or font_name.startswith(prefix):
            safe_print(f"    [{font_name}] -> GitHub Releases ...")
            if try_github_release(font_name, save_dir, session):
                return True, "GitHub"
            break

    # 3) 站酷字体 (已知映射)
    for prefix in ZCOOL_FONT_MAP:
        if base.startswith(prefix) or font_name.startswith(prefix):
            safe_print(f"    [{font_name}] -> 站酷字体 ...")
            if try_zcool(font_name, save_dir, session):
                return True, "站酷字体"
            break

    # 4) Google Fonts
    safe_print(f"    [{font_name}] -> Google Fonts ...")
    if try_google_fonts(font_name, save_dir, session):
        return True, "Google Fonts"

    # 5) Fontshare
    safe_print(f"    [{font_name}] -> Fontshare ...")
    if try_fontshare(font_name, save_dir, session):
        return True, "Fontshare"

    # 6) 猫啃网 (中文字体优先)
    safe_print(f"    [{font_name}] -> 猫啃网 ...")
    if try_maoken(font_name, save_dir, session):
        return True, "猫啃网"

    # 7) 字体搬运工
    # 注意: 遍历所有页面较慢，仅在其他源失败后尝试
    # safe_print(f"    [{font_name}] -> 字体搬运工 ...")
    # if try_sucai999(font_name, save_dir, session):
    #     return True, "字体搬运工"

    # 8) 喵闪字库
    safe_print(f"    [{font_name}] -> 喵闪字库 ...")
    if try_miao3(font_name, save_dir, session):
        return True, "喵闪字库"

    # 9) 100font
    safe_print(f"    [{font_name}] -> 100font ...")
    if try_100font(font_name, save_dir, session):
        return True, "100font"

    # 10) freefontdownload.org
    safe_print(f"    [{font_name}] -> freefontdownload.org ...")
    if try_freefontdownload(font_name, save_dir, session):
        return True, "freefontdownload.org"

    # 11) 字魂字体额外尝试
    if "zihun" in font_name.lower():
        safe_print(f"    [{font_name}] -> 字魂字体 ...")
        if try_zihun(font_name, save_dir, session):
            return True, "zihun"

    # 12) DaFont
    safe_print(f"    [{font_name}] -> DaFont ...")
    if try_dafont(font_name, save_dir, session):
        return True, "DaFont"

    # 13) webfontfree.com
    safe_print(f"    [{font_name}] -> webfontfree.com ...")
    if try_webfontfree(font_name, save_dir, session):
        return True, "webfontfree.com"

    # 14) Befonts
    safe_print(f"    [{font_name}] -> Befonts ...")
    if try_befonts(font_name, save_dir, session):
        return True, "Befonts"

    # 15) Velvetyne
    safe_print(f"    [{font_name}] -> Velvetyne ...")
    if try_velvetyne(font_name, save_dir, session):
        return True, "Velvetyne"

    # 16) 字体天下 (可能有验证码)
    safe_print(f"    [{font_name}] -> 字体天下 ...")
    if try_fontsnetcn(font_name, save_dir, session):
        return True, "字体天下"

    # 17) 字酷网 (JS 驱动，成功率低)
    safe_print(f"    [{font_name}] -> 字酷网 ...")
    if try_fontku(font_name, save_dir, session):
        return True, "字酷网"

    return False, ""


def _worker(task):
    """
    线程池 worker：下载单个字体。
    task = (index, total, font_name, save_dir)
    返回 (font_name, ok, source, skipped)
    """
    idx, total, font_name, save_dir = task

    # 每个线程使用独立的 session，避免连接池竞争
    session = create_session()

    safe_print(f"[{idx}/{total}] {font_name}")

    # 跳过已下载
    if already_downloaded(font_name, save_dir):
        safe_print(f"    [{font_name}] 已存在，跳过")
        return font_name, True, "skip", True

    ok, source = download_font(font_name, save_dir, session)
    if ok:
        safe_print(f"    [{font_name}] [OK] 来源: {source}")
    else:
        safe_print(f"    [{font_name}] [FAIL] 所有来源均失败")

    return font_name, ok, source, False


def main():
    print("=" * 60)
    print("  Unmatched Fonts 批量下载器 (并发模式)")
    print(f"  线程数: {MAX_WORKERS}")
    print("=" * 60)

    # 加载字体列表
    fonts = load_font_list(FONT_LIST_FILE)
    print(f"\n共 {len(fonts)} 个字体待下载\n")

    # 创建保存目录
    os.makedirs(SAVE_DIR, exist_ok=True)

    # 构建任务列表
    total = len(fonts)
    tasks = [(i, total, name, SAVE_DIR) for i, name in enumerate(fonts, 1)]

    success_count = 0
    skip_count = 0
    fail_count = 0
    success_list = []
    fail_list = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_worker, t): t for t in tasks}

        for future in as_completed(futures):
            font_name, ok, source, skipped = future.result()
            if ok:
                success_count += 1
                success_list.append(font_name)
                if skipped:
                    skip_count += 1
            else:
                fail_count += 1
                fail_list.append(font_name)

    # 写日志
    with open(LOG_SUCCESS, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(success_list)))
    with open(LOG_FAIL, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(fail_list)))

    print("\n" + "=" * 60)
    print("下载完成!")
    print("=" * 60)
    print(f"  成功: {success_count} (含跳过 {skip_count})")
    print(f"  失败: {fail_count}")
    print(f"\n  成功列表: {LOG_SUCCESS}")
    print(f"  失败列表: {LOG_FAIL}")

    if fail_list:
        print(f"\n失败字体 ({len(fail_list)}):")
        for fn in sorted(fail_list)[:20]:
            print(f"  - {fn}")
        if len(fail_list) > 20:
            print(f"  ... 及其他 {len(fail_list) - 20} 个")


if __name__ == "__main__":
    main()
