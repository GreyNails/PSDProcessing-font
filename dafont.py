import os
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import time
import zipfile
from io import BytesIO

# 字体列表
font_names = [
    "aAnotherTag",
    "aAttackGraffiti",
    "aAutoSignature",
    "adelia",
    "against-Regular",
    "alagambe",
    "aliensandcows",
    "brillant",
    "brushely",
    "callovescript",
    "golden0pony",
    "modernlinePersonalUse",
    "moon_get-Heavy",
    "moonbright",
    "rationale",
    "sdprostreet-Regular",
    "spinweradBold",
    "taller",
    "theartisan"
]

# 创建保存目录
fonts_dir = Path("dafont_fonts")
fonts_dir.mkdir(exist_ok=True)

# 请求头（模拟浏览器）
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.dafont.com/',
}

def clean_font_name(font_name):
    """清理字体名称，移除可能的后缀"""
    # 移除 -Regular, -Bold 等后缀
    cleaned = font_name.replace('-Regular', '').replace('-Bold', '').replace('_', ' ')
    return cleaned.strip()

def search_dafont(font_name):
    """
    在DaFont上搜索字体并返回下载链接
    """
    try:
        # 清理字体名称
        search_name = clean_font_name(font_name)
        
        # DaFont搜索URL
        search_url = f"https://www.dafont.com/search.php?q={search_name}"
        
        print(f"  搜索: {search_url}")
        
        response = requests.get(search_url, headers=HEADERS, timeout=15)
        
        if response.status_code != 200:
            print(f"  ✗ 搜索失败，状态码: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找下载按钮 - DaFont的下载链接通常在 class="dl" 的div中
        download_div = soup.find('div', class_='dl')
        
        if download_div:
            download_link = download_div.find('a')
            if download_link and 'href' in download_link.attrs:
                download_url = download_link['href']
                
                # 如果是相对路径，补全为完整URL
                if not download_url.startswith('http'):
                    download_url = f"https://www.dafont.com/{download_url.lstrip('/')}"
                
                return download_url
        
        # 备选方案：查找所有包含 "Download" 文本的链接
        download_links = soup.find_all('a', string=lambda text: text and 'Download' in text)
        if download_links:
            download_url = download_links[0].get('href')
            if download_url and not download_url.startswith('http'):
                download_url = f"https://www.dafont.com/{download_url.lstrip('/')}"
            return download_url
        
        print(f"  ✗ 未找到下载链接")
        return None
        
    except Exception as e:
        print(f"  ✗ 搜索错误: {str(e)}")
        return None

def download_font(font_name, download_url):
    """
    下载并解压字体文件
    """
    try:
        print(f"  下载中...")
        
        response = requests.get(download_url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            print(f"  ✗ 下载失败，状态码: {response.status_code}")
            return False
        
        # 创建字体专用文件夹
        font_folder = fonts_dir / font_name
        font_folder.mkdir(exist_ok=True)
        
        # 保存原始zip文件
        zip_path = font_folder / f"{font_name}.zip"
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        # 尝试解压zip文件
        try:
            with zipfile.ZipFile(BytesIO(response.content)) as z:
                # 获取所有文件
                all_files = z.namelist()
                
                # 提取ttf和otf文件
                font_files = [f for f in all_files if f.lower().endswith(('.ttf', '.otf'))]
                
                if font_files:
                    for font_file in font_files:
                        z.extract(font_file, font_folder)
                    
                    print(f"  ✓ 成功下载并解压 {len(font_files)} 个字体文件")
                    return True
                else:
                    # 如果没有字体文件，就提取所有文件
                    z.extractall(font_folder)
                    print(f"  ✓ 成功下载 (zip已保存)")
                    return True
                    
        except zipfile.BadZipFile:
            print(f"  ⚠ 文件不是zip格式，已保存原始文件")
            return True
        
    except Exception as e:
        print(f"  ✗ 下载错误: {str(e)}")
        return False

def main():
    print("=" * 70)
    print(" " * 20 + "DaFont 字体下载器")
    print("=" * 70)
    print()
    
    success_count = 0
    fail_count = 0
    failed_fonts = []
    
    for i, font_name in enumerate(font_names, 1):
        print(f"\n[{i}/{len(font_names)}] 处理字体: {font_name}")
        print("-" * 70)
        
        # 搜索字体
        download_url = search_dafont(font_name)
        
        if download_url:
            print(f"  找到下载链接: {download_url}")
            
            # 下载字体
            if download_font(font_name, download_url):
                success_count += 1
            else:
                fail_count += 1
                failed_fonts.append(font_name)
        else:
            print(f"  ✗ 未找到字体")
            fail_count += 1
            failed_fonts.append(font_name)
        
        # 避免请求过快，防止被封IP
        time.sleep(2)
    
    # 总结
    print("\n" + "=" * 70)
    print(" " * 25 + "下载完成!")
    print("=" * 70)
    print(f"\n📊 统计信息:")
    print(f"   ✓ 成功: {success_count} 个")
    print(f"   ✗ 失败: {fail_count} 个")
    print(f"   📁 保存位置: {fonts_dir.absolute()}")
    
    if failed_fonts:
        print(f"\n❌ 失败的字体列表:")
        for font in failed_fonts:
            print(f"   - {font}")
        
        print("\n💡 提示:")
        print("   1. 这些字体可能在DaFont上使用了不同的名称")
        print("   2. 可以手动访问 https://www.dafont.com/ 搜索")
        print("   3. 有些字体可能已被移除或更名")

if __name__ == "__main__":
    # 检查依赖
    try:
        import bs4
    except ImportError:
        print("错误: 需要安装 beautifulsoup4")
        print("请运行: pip install beautifulsoup4")
        exit(1)
    
    main()