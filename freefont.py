import requests
import os
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 字体列表
fonts = [
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

def create_session():
    """
    创建带有重试机制的Session
    """
    session = requests.Session()
    
    # 配置重试策略
    retry_strategy = Retry(
        total=5,  # 总共重试5次
        backoff_factor=2,  # 重试间隔：2, 4, 8, 16, 32秒
        status_forcelist=[429, 500, 502, 503, 504],  # 这些状态码会触发重试
        allowed_methods=["GET"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def download_font(font_name, save_dir="fonts", session=None, retry_count=0, max_retries=3):
    """
    下载字体ZIP文件，带有手动重试机制
    """
    # 创建保存目录
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # 如果没有传入session，创建一个新的
    if session is None:
        session = create_session()
    
    # 构建下载URL
    # url = f"https://www.freefontdownload.org/download-font/{font_name}"
    url = f"https://www.freefontdownload.org/download-font-otf/{font_name}"

    
    # 设置更完整的请求头，模拟真实浏览器
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        print(f"正在下载: {font_name} (尝试 {retry_count + 1}/{max_retries + 1})")
        print(f"  URL: {url}")
        
        # 下载文件，增加超时时间
        response = session.get(
            url, 
            headers=headers, 
            timeout=(10, 30),  # (连接超时, 读取超时)
            verify=True  # 验证SSL证书
        )
        response.raise_for_status()
        
        # 检查是否是ZIP文件
        content_type = response.headers.get('content-type', '')
        if 'zip' in content_type or 'application' in content_type or len(response.content) > 1000:
            # 保存为ZIP文件
            file_path = os.path.join(save_dir, f"{font_name}.zip")
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content) / 1024  # KB
            print(f"  ✅ 成功下载: {file_path} ({file_size:.2f} KB)")
            return True
        else:
            print(f"  ❌ 响应不是ZIP文件，Content-Type: {content_type}")
            return False
    
    except requests.exceptions.SSLError as e:
        print(f"  ⚠️ SSL错误: {e}")
        
        # 如果还有重试次数，等待后重试
        if retry_count < max_retries:
            wait_time = (retry_count + 1) * 3  # 递增等待时间：3, 6, 9秒
            print(f"  ⏳ 等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
            return download_font(font_name, save_dir, session, retry_count + 1, max_retries)
        else:
            print(f"  ❌ 达到最大重试次数，跳过")
            return False
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"  ❌ 字体不存在 (404)")
        else:
            print(f"  ❌ HTTP错误: {e}")
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ 请求错误: {e}")
        
        # SSL相关错误也尝试重试
        if retry_count < max_retries:
            wait_time = (retry_count + 1) * 3
            print(f"  ⏳ 等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
            return download_font(font_name, save_dir, session, retry_count + 1, max_retries)
        else:
            return False
            
    except Exception as e:
        print(f"  ❌ 未知错误: {e}")
        return False

def main():
    """
    主函数：批量下载所有字体
    """
    print("=" * 60)
    print("开始批量下载字体")
    print("=" * 60)
    print()
    
    # 创建一个共享的session
    session = create_session()
    
    success_count = 0
    fail_count = 0
    failed_fonts = []
    
    for i, font_name in enumerate(fonts, 1):
        print(f"[{i}/{len(fonts)}] {font_name}")
        
        if download_font(font_name, session=session):
            success_count += 1
        else:
            fail_count += 1
            failed_fonts.append(font_name)
        
        # 添加延迟，避免请求过快
        if i < len(fonts):
            time.sleep(2)  # 每次请求间隔2秒
        
        print()
    
    print("=" * 60)
    print("下载完成！")
    print("=" * 60)
    print(f"✅ 成功: {success_count} 个")
    print(f"❌ 失败: {fail_count} 个")
    
    if failed_fonts:
        print(f"\n失败的字体:")
        for font in failed_fonts:
            print(f"  - {font}")
        print(f"\n💡 提示: 失败的字体可以稍后单独重试")
    
    print("=" * 60)

def download_single_font(font_name):
    """
    单独下载一个字体（用于重试失败的字体）
    """
    print(f"\n单独下载字体: {font_name}")
    session = create_session()
    return download_font(font_name, session=session)

if __name__ == "__main__":
    main()
    
    # 如果有失败的字体，可以使用这个函数单独重试
    # download_single_font("rationale")