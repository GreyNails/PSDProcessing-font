# PSD Processing & Font Management Toolkit

本项目是一套用于 PSD 文件处理和字体批量下载管理的 Python 工具集。主要用于从 PSD 设计文件中提取字体信息，并从多个在线来源批量下载所需字体。

---

## 项目结构概览

脚本按功能可分为以下几大类：

### 1. PSD 文件处理

| 脚本 | 功能说明 |
|------|----------|
| `processing_psd_0912.py` | **PSD 图层批量提取工具（核心）**。使用 `psd-tools` 解析 PSD 文件，自动识别图层类型（文本、形状、像素、蒙版、背景等），提取图层图像并导出为 PNG，同时生成包含图层元数据（字体、颜色、位置等）的 JSON 文件。支持多进程并行处理整个文件夹的 PSD 文件。 |
| `extra2_psd.py` | **PSD 文本信息深度提取器**。通过二进制解析 PSD 文件，提取文本内容、字体名称、字号、颜色等信息。支持 Unicode 文本块、EngineDict、TySh 块等多种提取方式，适用于 `psd-tools` 无法完整解析的场景。 |
| `get_loss_front_v2.py` | **PSD 字体名称快速提取**。简洁脚本，使用 `psd-tools` 遍历 PSD 文件中的文字图层，输出所有使用的字体名称。 |
| `layer_fillter_v2.py` | **PSD 图层过滤/删除工具**。提供两种方式处理 PSD 最顶层图层：设置为不可见或通过重新合成图像完全移除。支持列出所有图层信息。 |

### 2. 字体批量下载 - 主要工具

| 脚本 | 功能说明 |
|------|----------|
| `download_all_fonts.py` | **综合字体批量下载脚本 v2（主脚本）**。从 Excel 表格 (`font_download_links.xlsx`) 读取字体信息，支持按授权类型（免费商用/个人/全部）过滤，使用 `curl` 绕过 Python SSL 问题，支持 GitHub 代理 (`gh-proxy.com`)，具备断点续传、进度统计、去重下载等功能。通过 CLI 参数控制行为。 |
| `main.py` | **多引擎字体下载管理器**。基于 Playwright 浏览器自动化，支持 5 个下载引擎：webfontfree.com、font.download、dafont.com、freefontdownload.org、Google Fonts API。当一个引擎搜索不到时自动切换到下一个，支持进度保存和断点续传。 |
| `download_unmatched.py` | **未匹配字体多源下载器**。针对未能匹配到的字体，依次尝试多个来源下载：freefontdownload.org（TTF/OTF/ZIP）、Google Fonts API、GitHub 搜索、DaFont 搜索。支持 8 线程并发下载，带重试机制和详细日志。 |
| `download_fonts.py` | **字体下载器（urllib 版）**。使用 `urllib` 实现，支持 Google Fonts CSS 解析、GitHub API/Release 下载、直接 URL 下载。专门处理思源黑体、思源宋体、Noto CJK 等大型字体包。 |

### 3. 字体批量下载 - 特定来源

| 脚本 | 功能说明 |
|------|----------|
| `Google.py` | **Google Fonts 下载器**。从 Google Fonts 批量下载指定字体列表，自动尝试多种名称格式变体，解压 ZIP 提取 TTF 文件。 |
| `dafont.py` | **DaFont 下载器**。通过 BeautifulSoup 爬取 DaFont 网站，搜索并下载指定字体，自动解压 ZIP 提取字体文件。 |
| `freefont.py` | **FreeFontDownload.org 下载器（OTF 版）**。从 freefontdownload.org 批量下载字体 ZIP 包，带重试机制和 SSL 错误处理。 |
| `freefont_v1.py` | **FreeFontDownload.org 下载器（TTF 版）**。与 `freefont.py` 类似，下载 TTF 格式字体，包含约 3300 个字体名称的完整列表。 |
| `freefont_v1-otf.py` | **FreeFontDownload.org 下载器（OTF 版，完整列表）**。与 `freefont_v1.py` 相同的字体列表，但下载 OTF 格式。 |
| `original.py` | **Google Fonts CSS 解析下载器（原始版）**。通过 Google Fonts CSS API 获取字体 URL，下载 gstatic.com 上的 TTF 文件。包含约 50 个常用字体。 |
| `donloadfonts.py` | **FreeFontDownload.org 下载器（早期版本）**。与 `freefont_v1.py` 功能相同，包含完整字体列表，从 freefontdownload.org 下载 TTF 格式。 |

### 4. 字体数据处理与匹配

| 脚本 | 功能说明 |
|------|----------|
| `parse_fonts.py` | **Excel 字体数据解析器**。从 `font_download_links.xlsx` 的第二个工作表中提取字体信息（名称、分类、来源、授权、下载链接），导出为 JSON 格式。 |
| `analyze_urls.py` | **下载链接分析器**。分析 JSON 数据中的字体下载 URL，按类型分类统计（GitHub Release、直接文件、Google Fonts 等），并测试 Google Fonts CSS 中的 woff2 链接。 |
| `match_and_extract.py` | **字体匹配与提取工具**。将已下载的 ZIP 文件与未匹配字体列表进行智能匹配（支持标准化名称、部分匹配），从 ZIP 中提取对应的字体文件。 |
| `smart_download.py` | **智能字体匹配下载器**。分两阶段工作：Phase 1 扫描已下载的 ZIP 文件，通过读取字体内部 name 表进行精确匹配；Phase 2 处理 GitHub 来源的字体。 |
| `download_step1.py` | **分步下载器（第一步）**。按优先级处理不同来源的字体：Google Fonts CSS -> 直接文件 URL -> GitHub Release，分析并展示各类 URL 的字体分布。 |

### 5. 字体检查与验证

| 脚本 | 功能说明 |
|------|----------|
| `check_fonts.py` | **字体文件检查器**。扫描 `unmatched_fonts/` 目录，列出所有 TTF/OTF 文件的大小、格式（TTF/OTF），标记异常小的文件。 |
| `check_phase1.py` | **Phase 1 下载结果检查器**。读取并展示 `download_phase1.json` 中的下载记录。 |

### 6. 代码生成脚本

以下脚本用于分段生成 `download_all_fonts.py`，通过追加写入的方式组装完整脚本：

| 脚本 | 功能说明 |
|------|----------|
| `_gen_script.py` | 生成 Part 1+2：文件头、imports、授权类型常量列表 |
| `_gen_part3.py` | 生成 Part 3：curl HTTP 工具函数、Excel 读取、字体过滤 |
| `_gen_part4.py` | 生成 Part 4：各来源下载器（GitHub、HarmonyOS、MiSans） |
| `_gen_part5.py` | 生成 Part 5：更多下载器（100font、webfontfree、Naver 等）及调度逻辑 |
| `_gen_part6.py` | 生成 Part 6：去重、统计、CLI 参数解析、main 函数 |

### 7. 测试/调试

| 脚本 | 功能说明 |
|------|----------|
| `_test_scrape.py` | **GitHub 访问测试脚本**。检查 GitHub API 速率限制，测试通过 curl 直接访问 GitHub 仓库页面并查找字体文件链接。 |

---

## 工作流程

```
PSD 文件 --> 提取字体名称 --> 生成字体列表 --> 批量下载字体
                |                                    |
        processing_psd_0912.py              download_all_fonts.py
        get_loss_front_v2.py                main.py (Playwright)
        extra2_psd.py                       download_unmatched.py
                                            (Google/DaFont/FreeFontDownload...)
                                                     |
                                            匹配 & 验证
                                            match_and_extract.py
                                            check_fonts.py
```

## 依赖

- Python 3.8+
- `psd-tools` - PSD 文件解析
- `Pillow` (PIL) - 图像处理
- `openpyxl` / `pandas` - Excel 文件读写
- `requests` - HTTP 请求
- `beautifulsoup4` - HTML 解析
- `playwright` - 浏览器自动化
- `scikit-learn` - KMeans 颜色聚类
- `tqdm` - 进度条
- `numpy` - 数值计算

## 使用示例

```bash
# 提取 PSD 文件中的字体信息
python get_loss_front_v2.py

# 批量处理 PSD 文件，提取图层
python processing_psd_0912.py

# 从 Excel 下载免费商用字体
python download_all_fonts.py --filter free

# 查看下载统计
python download_all_fonts.py --stats

# 使用多引擎下载器
python main.py

# 下载未匹配的字体
python download_unmatched.py

# 检查已下载字体文件
python check_fonts.py
```
