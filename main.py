#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import time
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright, TimeoutError


class FontDownloadEngine:
    
    def __init__(self, name, page, download_dir):
        self.name = name
        self.page = page
        self.download_dir = download_dir
        Path(download_dir).mkdir(parents=True, exist_ok=True)
    
    def download(self, font_name):
        raise NotImplementedError


class FontDownloadEngine1(FontDownloadEngine):
    
    def __init__(self, page, download_dir):
        super().__init__("font.download", page, download_dir)
    
    def download(self, font_name):
        try:
            self.page.goto("https://font.download/", timeout=30000)
            time.sleep(1)
            
            search_box = self.page.get_by_role("searchbox", name="Search")
            search_box.click()
            search_box.fill(font_name)
            search_box.press("Enter")
            time.sleep(2)
            
            font_link = self.page.get_by_role("link", name=font_name, exact=True).first
            
            if font_link.count() == 0:
                return False, "not_found"
            
            font_link.click()
            time.sleep(2)
            
            with self.page.expect_download(timeout=15000) as download_info:
                self.page.get_by_role("link", name=" Download Font for Free").click()
            
            download = download_info.value
            original_filename = download.suggested_filename
            file_ext = Path(original_filename).suffix
            new_filename = f"{font_name}_{self.name}{file_ext}"
            download_path = os.path.join(self.download_dir, new_filename)
            download.save_as(download_path)
            
            return True, None
            
        except TimeoutError:
            return False, "timeout"
        except Exception as e:
            if "timeout" in str(e).lower() or "not found" in str(e).lower():
                return False, "not_found"
            return False, "error"


class DaFontEngine(FontDownloadEngine):
    
    def __init__(self, page, download_dir):
        super().__init__("dafont.com", page, download_dir)
    
    def download(self, font_name):
        try:
            self.page.goto("https://www.dafont.com/", timeout=30000)
            time.sleep(1)
            
            self.page.get_by_role("textbox").first.click(timeout=10000)
            self.page.get_by_role("textbox").first.press("ControlOrMeta+a")
            self.page.get_by_role("textbox").first.fill(font_name)
            self.page.get_by_role("button", name="Search").first.click(timeout=10000)
            time.sleep(2)
            
            if self.page.locator("text=0 font on DaFont for").count() > 0:
                return False, "not_found"
            
            download_button = self.page.locator('a.dl').first
            
            if download_button.count() == 0:
                return False, "not_found"
            
            with self.page.expect_download(timeout=30000) as download_info:
                download_button.click(timeout=10000)
            
            download = download_info.value
            original_filename = download.suggested_filename
            file_ext = Path(original_filename).suffix
            new_filename = f"{font_name}_{self.name}{file_ext}"
            file_path = os.path.join(self.download_dir, new_filename)
            download.save_as(file_path)
            
            return True, None
            
        except TimeoutError:
            return False, "timeout"
        except Exception as e:
            if "timeout" in str(e).lower():
                return False, "not_found"
            return False, "error"


class WebFontFreeEngine(FontDownloadEngine):
    
    def __init__(self, page, download_dir):
        super().__init__("webfontfree.com", page, download_dir)
    
    def download(self, font_name):
        try:
            self.page.goto("https://www.webfontfree.com/", timeout=30000)
            time.sleep(1)
            
            search_box = self.page.get_by_role("textbox", name="e.g. Web, Glyph , Maps")
            search_box.click()
            search_box.fill(font_name)
            
            with self.page.expect_popup(timeout=10000) as page1_info:
                self.page.get_by_role("button", name="Search").click()
            page1 = page1_info.value
            
            page1.wait_for_load_state('networkidle', timeout=10000)
            
            list_items = page1.get_by_role("listitem").all()
            if not list_items:
                page1.close()
                return False, "not_found"
            
            first_result = list_items[0]
            links = first_result.get_by_role("link").all()
            if len(links) >= 2:
                links[1].click()
            else:
                page1.close()
                return False, "not_found"
            
            page1.wait_for_load_state('networkidle', timeout=10000)
            
            try:
                otf_checkbox = page1.locator("#view label").filter(has_text="otf")
                if otf_checkbox.count() > 0:
                    otf_checkbox.click()
                    time.sleep(0.5)
            except:
                pass
            
            page1.locator("button.download").click()
            time.sleep(0.5)
            
            with page1.expect_download(timeout=15000) as download_info:
                with page1.expect_popup(timeout=10000) as page2_info:
                    page1.get_by_role("link", name="Free Downloads You must").click()
                page2 = page2_info.value
            
            download = download_info.value
            original_filename = download.suggested_filename
            file_ext = Path(original_filename).suffix
            new_filename = f"{font_name}_{self.name}{file_ext}"
            download_path = Path(self.download_dir) / new_filename
            download.save_as(download_path)
            
            page2.close()
            page1.close()
            
            return True, None
            
        except TimeoutError:
            return False, "timeout"
        except Exception:
            return False, "error"


class FreeFontDownloadEngine(FontDownloadEngine):
    
    def __init__(self, page, download_dir):
        super().__init__("freefontdownload.org", page, download_dir)
    
    def download(self, font_name):
        try:
            self.page.goto("https://www.freefontdownload.org/en", timeout=30000)
            time.sleep(1)
            
            search_box = self.page.get_by_role("textbox", name="Enter font name")
            search_box.click()
            search_box.fill(font_name)
            time.sleep(0.5)
            
            self.page.get_by_role("button", name="").click()
            time.sleep(2)
            
            try:
                self.page.get_by_role("heading", name=f"{font_name} Font", exact=True).click(timeout=5000)
            except:
                try:
                    self.page.get_by_role("heading", name=f"{font_name}").first.click(timeout=5000)
                except:
                    return False, "not_found"
            
            time.sleep(1)
            
            try:
                self.page.get_by_role("link", name="Download", exact=True).nth(1).click(timeout=5000)
            except:
                try:
                    self.page.get_by_role("link", name="Download").first.click(timeout=5000)
                except:
                    return False, "not_found"
            
            time.sleep(1)
            
            with self.page.expect_download(timeout=30000) as download_info:
                self.page.get_by_role("button", name="Download TTF").click()
            download = download_info.value
            
            original_filename = download.suggested_filename
            file_ext = Path(original_filename).suffix
            new_filename = f"{font_name}_{self.name}{file_ext}"
            save_path = os.path.join(self.download_dir, new_filename)
            download.save_as(save_path)
            
            return True, None
            
        except TimeoutError:
            return False, "timeout"
        except Exception:
            return False, "error"


class GoogleFontEngine(FontDownloadEngine):
    
    def __init__(self, page, download_dir):
        super().__init__("Google Fonts", page, download_dir)
    
    def download(self, font_name):
        import re
        
        try:
            formatted_name = font_name.replace(" ", "+")
            url = f"https://fonts.googleapis.com/css?family={formatted_name}"
            
            css_text = self.page.evaluate(f"""
                async () => {{
                    const response = await fetch('{url}');
                    return await response.text();
                }}
            """)
            
            ttf_urls = re.findall(r"url\((.*?)\)", css_text)
            if not ttf_urls:
                return False, "not_found"
            
            for ttf_url in ttf_urls:
                ttf_url = ttf_url.strip("'\"")
                if "gstatic.com" in ttf_url:
                    font_data = self.page.evaluate(f"""
                        async () => {{
                            const response = await fetch('{ttf_url}');
                            const buffer = await response.arrayBuffer();
                            return Array.from(new Uint8Array(buffer));
                        }}
                    """)
                    
                    if '.woff2' in ttf_url:
                        file_ext = '.woff2'
                    elif '.woff' in ttf_url:
                        file_ext = '.woff'
                    elif '.ttf' in ttf_url:
                        file_ext = '.ttf'
                    else:
                        file_ext = '.ttf'
                    
                    new_filename = f"{font_name}_{self.name}{file_ext}"
                    font_file_path = os.path.join(self.download_dir, new_filename)
                    with open(font_file_path, "wb") as f:
                        f.write(bytes(font_data))
                    
                    return True, None
            
            return False, "not_found"
            
        except Exception:
            return False, "error"


class FontDownloadManager:
    
    def __init__(self, json_file="fonts_list.json", download_dir="downloads", progress_file="download_progress.json"):
        self.json_file = json_file
        self.download_dir = download_dir
        self.progress_file = progress_file
        self.engines = []
        
        self.fonts_list = self._load_fonts_list()
        self.progress = self._load_progress()
    
    def _load_fonts_list(self):
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'fonts' in data:
                    return data['fonts']
                elif isinstance(data, list):
                    return data
                return []
        except:
            return []
    
    def _load_progress(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            'downloaded': [],
            'failed': [],
            'not_found': [],
            'engine_used': {}
        }
    
    def _save_progress(self):
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, indent=2, ensure_ascii=False)
    
    def _init_engines(self, page):
        self.engines = [
            WebFontFreeEngine(page, self.download_dir),
            FontDownloadEngine1(page, self.download_dir),
            DaFontEngine(page, self.download_dir),
            FreeFontDownloadEngine(page, self.download_dir),
            GoogleFontEngine(page, self.download_dir),
        ]
    
    def download_font(self, font_name):
        for engine in self.engines:
            print(f"   尝试引擎: {engine.name}")
            
            try:
                success, error_type = engine.download(font_name)
                
                if success:
                    print(f"   成功 (引擎: {engine.name})")
                    return True, engine.name
                else:
                    print(f"   失败: {error_type}")
                    
                    if error_type == "not_found":
                        continue
                    else:
                        continue
            except Exception as e:
                print(f"   引擎异常: {str(e)}")
                continue
        
        return False, None
    
    def run(self, playwright: Playwright):
        if not self.fonts_list:
            print("没有找到需要下载的字体")
            return
        
        print(f"共找到 {len(self.fonts_list)} 个字体")
        
        downloaded = set(self.progress.get('downloaded', []))
        not_found = set(self.progress.get('not_found', []))
        failed = set(self.progress.get('failed', []))
        
        success_count = len(downloaded)
        not_found_count = len(not_found)
        failed_count = len(failed)
        skipped_count = 0
        
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)
        
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        
        self._init_engines(page)
        
        try:
            print("\n" + "="*60)
            print("开始批量下载字体")
            print("="*60)
            
            for idx, font_name in enumerate(self.fonts_list, 1):
                if font_name in downloaded:
                    skipped_count += 1
                    print(f"\n[{idx}/{len(self.fonts_list)}] 跳过已下载: {font_name}")
                    continue
                
                if font_name in not_found:
                    skipped_count += 1
                    print(f"\n[{idx}/{len(self.fonts_list)}] 跳过未找到: {font_name}")
                    continue
                
                print(f"\n[{idx}/{len(self.fonts_list)}] 正在下载: {font_name}")
                
                success, engine_name = self.download_font(font_name)
                
                if success:
                    downloaded.add(font_name)
                    success_count += 1
                    failed.discard(font_name)
                    not_found.discard(font_name)
                    
                    if 'engine_used' not in self.progress:
                        self.progress['engine_used'] = {}
                    self.progress['engine_used'][font_name] = engine_name
                else:
                    not_found.add(font_name)
                    not_found_count += 1
                    failed.discard(font_name)
                
                self.progress['downloaded'] = list(downloaded)
                self.progress['failed'] = list(failed)
                self.progress['not_found'] = list(not_found)
                self._save_progress()
                
                time.sleep(1)
            
            print("\n" + "="*60)
            print("下载统计:")
            print(f"   成功: {success_count}")
            print(f"   未找到: {not_found_count}")
            print(f"   失败: {failed_count}")
            print(f"   跳过: {skipped_count}")
            print(f"   下载目录: {self.download_dir}")
            print("="*60)
            
            if 'engine_used' in self.progress and self.progress['engine_used']:
                print("\n引擎使用统计:")
                engine_stats = {}
                for engine in self.progress['engine_used'].values():
                    engine_stats[engine] = engine_stats.get(engine, 0) + 1
                
                for engine, count in sorted(engine_stats.items(), key=lambda x: x[1], reverse=True):
                    print(f"   {engine}: {count} 个")
            
            if not_found:
                print(f"\n未找到的字体 ({len(not_found)} 个):")
                for font in sorted(not_found):
                    print(f"   - {font}")
        
        finally:
            context.close()
            browser.close()


def main():
    json_file = "fonts_list.json"
    download_dir = "downloads"
    progress_file = "download_progress.json"
    
    print("="*60)
    print("多引擎字体批量下载工具")
    print("="*60)
    print(f"字体列表: {json_file}")
    print(f"下载目录: {download_dir}")
    print(f"进度文件: {progress_file}")
    print("="*60)
    print("\n支持的下载引擎:")
    print("  1. webfontfree.com (优先)")
    print("  2. font.download")
    print("  3. dafont.com")
    print("  4. freefontdownload.org")
    print("  5. Google Fonts API")
    print("\n当一个引擎搜索不到时，自动切换到下一个引擎")
    print("="*60 + "\n")
    
    manager = FontDownloadManager(json_file, download_dir, progress_file)
    
    with sync_playwright() as playwright:
        manager.run(playwright)
    
    print("\n程序执行完成！")


if __name__ == "__main__":
    main()
