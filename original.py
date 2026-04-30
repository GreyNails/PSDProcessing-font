import json
import requests
import re
import os

# 字体名称列表
fonts = [
    "Mohave",
    "Days One",
    "Playlist",
    "Akaya Kanadaka",
    "BioRhyme",
    "Oxanium",
    "Archivo Black",
    "Devonshire",
    "Blogger Sans",
    "Chicle",
    "Rum Raisin",
    "Croissant One",
    "Selima",
    "Brusher Regular",
    "Dynalight",
    "Manrope",
    "Barriecito",
    "Spartan",
    "Krona One",
    "Adamina",
    "Alata",
    "Poller One",
    "Black Han Sans",
    "FoglihtenNo06",
    "Kumbh Sans",
    "Jacques Francois",
    "Alex Brush",
    "Aguafina Script",
    "Gotu",
    "Courier Prime",
    "Cinzel Decorative",
    "Oswald Light",
    "Red Rose",
    "Dosis Light",
    "Meie Script",
    "Raleway Bold",
    "ABeeZee",
    "Kreon Bold",
    "Chela One",
    "Niramit",
    "Raleway Italic",
    "Sonsie One",
    "Charm",
    "Blogger Sans Bold"
]

def download_ttf(font_name):
    formatted_name = font_name.replace(' ', '+')
    url = f"https://fonts.googleapis.com/css?family={formatted_name}"

    response = requests.get(url)

    if response.status_code == 200:
        # 使用正则表达式提取TTF文件的URL
        ttf_urls = re.findall(r'url\((.*?)\)', response.text)
        for ttf_url in ttf_urls:
            ttf_url = ttf_url.strip('\'"')
            if 'gstatic.com' in ttf_url:  # 只下载gstatic.com的字体
                ttf_response = requests.get(ttf_url)
                if ttf_response.status_code == 200:
                    # 保存TTF文件
                    font_file_name = os.path.join("fonts", f"{font_name}.ttf")
                    os.makedirs("fonts", exist_ok=True)  # 创建fonts文件夹
                    with open(font_file_name, 'wb') as f:
                        f.write(ttf_response.content)
                    print(f"Downloaded: {font_file_name}")
                else:
                    print(f"Failed to download TTF: {ttf_url} (Status code: {ttf_response.status_code})")
    else:
        print(f"Failed to download CSS: {font_name} (Status code: {response.status_code})")

# 遍历字体列表，下载每种字体的TTF文件
for font in fonts:
    download_ttf(font)
