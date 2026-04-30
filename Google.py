import os
import requests
import zipfile
from pathlib import Path
import time
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
fonts_dir = Path("google_fonts")
fonts_dir.mkdir(exist_ok=True)

def download_google_font(font_name):
    """
    从Google Fonts下载字体
    """
    try:
        # Google Fonts下载URL
        # 尝试多种格式的字体名称
        font_variants = [
            font_name,
            font_name.replace("-", "+"),
            font_name.replace("_", "+"),
            font_name.title().replace("-", "+").replace("_", "+")
        ]
        
        for variant in font_variants:
            url = f"https://fonts.google.com/download?family={variant}"
            
            print(f"尝试下载: {font_name} (URL: {variant})...")
            
            response = requests.get(url, timeout=30, allow_redirects=True)
            
            if response.status_code == 200 and len(response.content) > 1000:
                # 检查是否是zip文件
                if response.content[:4] == b'PK\x03\x04':
                    # 解压zip文件
                    with zipfile.ZipFile(BytesIO(response.content)) as z:
                        # 提取所有ttf文件
                        ttf_files = [f for f in z.namelist() if f.endswith('.ttf')]
                        
                        if ttf_files:
                            font_folder = fonts_dir / font_name
                            font_folder.mkdir(exist_ok=True)
                            
                            for ttf_file in ttf_files:
                                z.extract(ttf_file, font_folder)
                            
                            print(f"✓ 成功: {font_name} (提取了 {len(ttf_files)} 个文件)")
                            return True
                else:
                    print(f"✗ 响应不是zip文件: {font_name}")
            
        print(f"✗ 失败: {font_name} (可能不在Google Fonts上)")
        return False
        
    except Exception as e:
        print(f"✗ 错误: {font_name} - {str(e)}")
        return False

def search_google_fonts_api(font_name):
    """
    使用Google Fonts API搜索字体
    """
    try:
        # 注意：需要Google Fonts API Key
        # 申请地址：https://developers.google.com/fonts/docs/developer_api
        api_key = "YOUR_API_KEY"  # 替换为你的API Key
        
        url = f"https://www.googleapis.com/webfonts/v1/webfonts?key={api_key}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            fonts = response.json().get('items', [])
            # 搜索匹配的字体
            for font in fonts:
                if font_name.lower() in font['family'].lower():
                    return font['family']
        
        return None
        
    except Exception as e:
        print(f"API搜索错误: {e}")
        return None

def main():
    print("=" * 60)
    print("Google Fonts 字体下载器")
    print("=" * 60)
    print()
    
    success_count = 0
    fail_count = 0
    failed_fonts = []
    
    for i, font_name in enumerate(font_names, 1):
        print(f"\n[{i}/{len(font_names)}] 处理: {font_name}")
        
        if download_google_font(font_name):
            success_count += 1
        else:
            fail_count += 1
            failed_fonts.append(font_name)
        
        # 避免请求过快
        time.sleep(1)
    
    print("\n" + "=" * 60)
    print("下载完成!")
    print("=" * 60)
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    
    if failed_fonts:
        print(f"\n失败的字体列表:")
        for font in failed_fonts:
            print(f"  - {font}")
        
        print("\n💡 提示：这些字体可能不在Google Fonts上。")
        print("   你可以在以下网站查找：")
        print("   - https://fonts.google.com/ (Google Fonts)")
        print("   - https://www.dafont.com/ (DaFont)")
        print("   - https://www.fontsquirrel.com/ (Font Squirrel)")

if __name__ == "__main__":
    main()