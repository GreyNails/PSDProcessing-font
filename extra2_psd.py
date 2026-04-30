import re
import os
import sys
import struct
import codecs

class PSDTextExtractor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.text_elements = []
        self.fonts_map = {}
        
    def extract_all_text_info(self):
        """提取所有文本信息"""
        with open(self.file_path, 'rb') as f:
            self.data = f.read()
        
        print(f"文件大小: {len(self.data)} bytes")
        
        # 1. 提取字体映射表
        self._extract_font_mapping()
        
        # 2. 查找并提取文本块
        self._extract_text_blocks()
        
        # 3. 查找TySh块中的文本
        self._extract_tysh_text()
        
        return self.text_elements
    
    def _extract_font_mapping(self):
        """提取字体映射关系"""
        # 查找 /FontSet 标记
        font_patterns = [
            rb'/FontSet\s*\[\s*\n(.*?)\]',  # 多行格式
            rb'/FontSet\s*\[(.*?)\]',        # 单行格式
        ]
        
        for pattern in font_patterns:
            matches = re.finditer(pattern, self.data, re.DOTALL)
            for match in matches:
                font_data = match.group(1)
                # 提取字体名称
                name_pattern = rb'/Name\s*\(([^)]+)\)'
                names = re.findall(name_pattern, font_data)
                for i, name in enumerate(names):
                    font_name = self._safe_decode(name)
                    if font_name and font_name != 'AdobeInvisFont':
                        self.fonts_map[i] = font_name
                        print(f"找到字体 [{i}]: {font_name}")
    
    def _extract_text_blocks(self):
        """使用改进的方法提取文本块"""
        
        # 方法1: 查找TXT标记后的文本
        self._extract_txt_blocks()
        
        # 方法2: 查找Unicode文本块
        self._extract_unicode_blocks()
        
        # 方法3: 查找EngineDict中的文本
        self._extract_engine_dict_text()
    
    def _extract_txt_blocks(self):
        """提取/Txt标记的文本"""
        # 改进的文本模式
        txt_patterns = [
            rb'/Txt\s*\(([^)]*?)\)',
            rb'<<\s*/Text\s*\(([^)]*?)\)',
        ]
        
        for pattern in txt_patterns:
            matches = re.finditer(pattern, self.data)
            for match in matches:
                raw_text = match.group(1)
                text = self._decode_psd_text(raw_text)
                if text and self._is_valid_text(text):
                    # 查找附近的样式信息
                    context_start = max(0, match.start() - 1000)
                    context_end = min(len(self.data), match.end() + 1000)
                    context = self.data[context_start:context_end]
                    
                    font_info = self._extract_style_from_context(context)
                    
                    self.text_elements.append({
                        'text': text,
                        'method': 'Txt pattern',
                        **font_info
                    })
                    print(f"通过Txt模式找到文本: {text[:50]}...")
    
    def _extract_unicode_blocks(self):
        """提取Unicode文本块（UTF-16）"""
        # UTF-16 BE 标记
        utf16_be_bom = b'\xfe\xff'
        # UTF-16 LE 标记
        utf16_le_bom = b'\xff\xfe'
        
        # 查找所有可能的UTF-16文本
        pos = 0
        while pos < len(self.data) - 4:
            # 检查UTF-16 BE
            if self.data[pos:pos+2] == utf16_be_bom:
                text = self._extract_utf16_text(pos + 2, 'utf-16-be')
                if text and self._is_valid_text(text):
                    self._add_text_with_context(text, pos, 'UTF-16 BE')
                pos += 2
                
            # 检查UTF-16 LE
            elif self.data[pos:pos+2] == utf16_le_bom:
                text = self._extract_utf16_text(pos + 2, 'utf-16-le')
                if text and self._is_valid_text(text):
                    self._add_text_with_context(text, pos, 'UTF-16 LE')
                pos += 2
                
            # 检查没有BOM的UTF-16文本（通过特征判断）
            elif pos < len(self.data) - 10:
                # 检查是否可能是UTF-16文本
                if self._looks_like_utf16(pos):
                    for encoding in ['utf-16-be', 'utf-16-le']:
                        text = self._extract_utf16_text(pos, encoding, max_length=500)
                        if text and len(text) > 3 and self._is_valid_text(text):
                            self._add_text_with_context(text, pos, f'UTF-16 {encoding}')
                            break
                pos += 2
            else:
                pos += 1
    
    def _extract_utf16_text(self, start_pos, encoding, max_length=2000):
        """从指定位置提取UTF-16文本"""
        end_pos = min(start_pos + max_length, len(self.data))
        
        # 查找文本结束位置（连续的null字节）
        null_pattern = b'\x00\x00\x00\x00'
        null_pos = self.data.find(null_pattern, start_pos, end_pos)
        if null_pos > 0:
            end_pos = null_pos
        
        try:
            text_bytes = self.data[start_pos:end_pos]
            # 确保字节数是偶数（UTF-16需要）
            if len(text_bytes) % 2 != 0:
                text_bytes = text_bytes[:-1]
            
            text = text_bytes.decode(encoding, errors='ignore')
            # 清理文本
            text = text.strip('\x00\r\n\t ')
            return text if text else None
        except:
            return None
    
    def _looks_like_utf16(self, pos):
        """检查是否像UTF-16文本"""
        if pos + 20 > len(self.data):
            return False
        
        # 检查交替的null字节模式（UTF-16的特征）
        sample = self.data[pos:pos+20]
        
        # UTF-16 BE: 高字节通常是0x00
        be_nulls = sum(1 for i in range(0, min(20, len(sample)), 2) if sample[i] == 0)
        # UTF-16 LE: 低字节通常是0x00
        le_nulls = sum(1 for i in range(1, min(20, len(sample)), 2) if sample[i] == 0)
        
        # 如果有足够多的null字节在固定位置，可能是UTF-16
        return be_nulls > 5 or le_nulls > 5
    
    def _extract_engine_dict_text(self):
        """从EngineDict中提取文本"""
        # 查找EngineDict块
        engine_pattern = rb'<<[\s\n]*/EngineDict[\s\n]*<<(.*?)>>[\s\n]*>>'
        matches = re.finditer(engine_pattern, self.data, re.DOTALL)
        
        for match in matches:
            engine_data = match.group(1)
            
            # 提取文本
            text_patterns = [
                rb'/Text[\s\n]*\(([^)]*?)\)',
            ]
            
            for pattern in text_patterns:
                text_matches = re.finditer(pattern, engine_data)
                for text_match in text_matches:
                    raw_text = text_match.group(1)
                    text = self._decode_psd_text(raw_text)
                    if text and self._is_valid_text(text):
                        # 提取样式信息
                        style_info = self._parse_engine_dict_styles(engine_data)
                        self.text_elements.append({
                            'text': text,
                            'method': 'EngineDict',
                            **style_info
                        })
                        print(f"通过EngineDict找到文本: {text[:50]}...")
    
    def _extract_tysh_text(self):
        """从TySh块中提取文本"""
        # 查找所有TySh标记
        tysh_pattern = b'TySh'
        pos = 0
        
        while pos < len(self.data):
            pos = self.data.find(tysh_pattern, pos)
            if pos == -1:
                break
            
            # TySh后面通常跟着版本和文本数据
            if pos + 50 < len(self.data):
                # 跳过TySh和版本号
                data_start = pos + 6
                
                # 在接下来的几KB中查找文本
                search_area = self.data[data_start:min(data_start + 5000, len(self.data))]
                
                # 尝试提取文本
                text = self._extract_text_from_tysh(search_area)
                if text:
                    # 提取样式信息
                    style_info = self._extract_style_from_context(search_area)
                    self.text_elements.append({
                        'text': text,
                        'method': 'TySh block',
                        **style_info
                    })
                    print(f"通过TySh块找到文本: {text[:50]}...")
            
            pos += 4
    
    def _extract_text_from_tysh(self, data):
        """从TySh数据中提取文本"""
        # 查找文本的各种模式
        
        # 1. 查找有效的ASCII/UTF-8文本
        ascii_pattern = rb'([\x20-\x7E]{10,})'
        matches = re.findall(ascii_pattern, data)
        for match in matches:
            text = self._safe_decode(match)
            if text and self._is_valid_text(text):
                return text
        
        # 2. 查找UTF-16文本
        for i in range(0, len(data) - 20):
            if self._looks_like_utf16(i):
                for encoding in ['utf-16-be', 'utf-16-le']:
                    text = self._extract_utf16_text(i, encoding, max_length=500)
                    if text and self._is_valid_text(text):
                        return text
        
        return None
    
    def _parse_engine_dict_styles(self, engine_data):
        """解析EngineDict中的样式信息"""
        style_info = {}
        
        # 提取StyleRun
        stylerun_pattern = rb'/StyleRun[\s\n]*<<(.*?)>>'
        stylerun_match = re.search(stylerun_pattern, engine_data, re.DOTALL)
        
        if stylerun_match:
            style_data = stylerun_match.group(1)
            
            # 提取字体索引
            font_pattern = rb'/Font[\s\n]+(\d+)'
            font_match = re.search(font_pattern, style_data)
            if font_match:
                idx = int(font_match.group(1))
                if idx in self.fonts_map:
                    style_info['font'] = self.fonts_map[idx]
            
            # 提取字号
            size_pattern = rb'/FontSize[\s\n]+([\d.]+)'
            size_match = re.search(size_pattern, style_data)
            if size_match:
                style_info['font_size'] = float(size_match.group(1))
        
        # 提取FontSet（如果有）
        fontset_pattern = rb'/FontSet[\s\n]*\[(.*?)\]'
        fontset_match = re.search(fontset_pattern, engine_data, re.DOTALL)
        if fontset_match:
            font_data = fontset_match.group(1)
            name_pattern = rb'/Name[\s\n]*\(([^)]+)\)'
            names = re.findall(name_pattern, font_data)
            if names:
                style_info['fonts'] = [self._safe_decode(name) for name in names]
                if 'font' not in style_info and style_info['fonts']:
                    style_info['font'] = style_info['fonts'][0]
        
        return style_info
    
    def _extract_style_from_context(self, context):
        """从上下文中提取样式信息"""
        style_info = {}
        
        # 提取字号
        size_patterns = [
            rb'/FontSize[\s\n]+([\d.]+)',
            rb'/Size[\s\n]+([\d.]+)',
            rb'FontSize["\s]*:[\s]*([\d.]+)'
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, context)
            if match:
                try:
                    style_info['font_size'] = float(match.group(1))
                    break
                except:
                    pass
        
        # 提取字体
        font_patterns = [
            rb'/Font[\s\n]*/Name[\s\n]*\(([^)]+)\)',
            rb'/Name[\s\n]*\(([^)]+)\).*?/Font',
        ]
        
        for pattern in font_patterns:
            match = re.search(pattern, context)
            if match:
                font_name = self._safe_decode(match.group(1))
                if font_name:
                    style_info['font'] = font_name
                    break
        
        # 提取颜色
        color_pattern = rb'/FillColor.*?/Values[\s\n]*\[[\s\n]*([\d.]+)[\s\n]+([\d.]+)[\s\n]+([\d.]+)'
        color_match = re.search(color_pattern, context)
        if color_match:
            try:
                style_info['color'] = {
                    'r': int(float(color_match.group(1)) * 255),
                    'g': int(float(color_match.group(2)) * 255),
                    'b': int(float(color_match.group(3)) * 255)
                }
            except:
                pass
        
        return style_info
    
    def _add_text_with_context(self, text, position, method):
        """添加文本并提取上下文样式信息"""
        # 获取上下文
        context_start = max(0, position - 1000)
        context_end = min(len(self.data), position + 1000)
        context = self.data[context_start:context_end]
        
        style_info = self._extract_style_from_context(context)
        
        self.text_elements.append({
            'text': text,
            'method': method,
            **style_info
        })
        print(f"通过{method}找到文本: {text[:50]}...")
    
    def _decode_psd_text(self, text_bytes):
        """解码PSD文本（处理转义和编码）"""
        if not text_bytes:
            return None
        
        # 处理转义序列
        text_bytes = text_bytes.replace(b'\\r', b'\r')
        text_bytes = text_bytes.replace(b'\\n', b'\n')
        text_bytes = text_bytes.replace(b'\\t', b'\t')
        text_bytes = text_bytes.replace(b'\\(', b'(')
        text_bytes = text_bytes.replace(b'\\)', b')')
        text_bytes = text_bytes.replace(b'\\"', b'"')
        text_bytes = text_bytes.replace(b'\\\\', b'\\')
        
        # 尝试解码
        return self._safe_decode(text_bytes)
    
    def _safe_decode(self, data):
        """安全解码字节数据"""
        if not data:
            return None
        
        # 移除null字节
        data = data.replace(b'\x00', b'')
        
        # 尝试不同的编码
        encodings = ['utf-8', 'utf-16-be', 'utf-16-le', 'latin-1', 'cp1252', 'gbk']
        
        for encoding in encodings:
            try:
                decoded = data.decode(encoding)
                # 检查解码结果是否合理
                if decoded and not all(c in '\x00\xff\xfe' for c in decoded):
                    return decoded.strip()
            except:
                continue
        
        # 最后尝试忽略错误
        try:
            return data.decode('utf-8', errors='ignore').strip()
        except:
            return None
    
    def _is_valid_text(self, text):
        """判断文本是否有效"""
        if not text or len(text.strip()) < 2:
            return False
        
        # 清理后再检查
        text = text.strip()
        
        # 过滤太短的文本
        if len(text) < 2:
            return False
        
        # 检查是否包含太多特殊字符
        special_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
        if special_chars > len(text) * 0.3:
            return False
        
        # 检查是否包含有效的可打印字符
        printable = sum(1 for c in text if 32 <= ord(c) <= 126 or ord(c) > 127)
        if printable < len(text) * 0.5:
            return False
        
        return True

def display_results(text_elements):
    """显示提取结果"""
    if not text_elements:
        print("\n未找到文本元素")
        return
    
    # 去重
    unique_elements = []
    seen_texts = set()
    
    for elem in text_elements:
        text = elem.get('text', '').strip()
        if text and text not in seen_texts:
            seen_texts.add(text)
            unique_elements.append(elem)
    
    print(f"\n{'='*80}")
    print(f"找到 {len(unique_elements)} 个唯一文本元素:")
    print(f"{'='*80}")
    
    for i, elem in enumerate(unique_elements, 1):
        print(f"\n【文本元素 {i}】")
        print(f"提取方法: {elem.get('method', '未知')}")
        print(f"文本内容: {elem.get('text', 'N/A')}")
        print(f"字体名称: {elem.get('font', '未知')}")
        print(f"字体大小: {elem.get('font_size', '未知')}{'pt' if elem.get('font_size') else ''}")
        
        if 'color' in elem:
            color = elem['color']
            print(f"文本颜色: RGB({color['r']}, {color['g']}, {color['b']})")
        
        print("-" * 80)

def main():
    psd_file = r'D:\HCL\PSDProcessing\input\0702_freepik_v5_2816561de0.psd'
    
    print(f"开始分析PSD文件: {psd_file}")
    print("="*80)
    
    extractor = PSDTextExtractor(psd_file)
    text_elements = extractor.extract_all_text_info()
    
    display_results(text_elements)
    
    # 保存结果到文件
    output_file = psd_file.rsplit('.', 1)[0] + '_extracted_text.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"PSD文本提取结果\n")
        f.write(f"文件: {psd_file}\n")
        f.write("="*80 + "\n\n")
        
        for i, elem in enumerate(text_elements, 1):
            f.write(f"【文本元素 {i}】\n")
            f.write(f"文本: {elem.get('text', 'N/A')}\n")
            f.write(f"字体: {elem.get('font', '未知')}\n")
            f.write(f"字号: {elem.get('font_size', '未知')}\n")
            f.write("-"*40 + "\n\n")
    
    print(f"\n结果已保存到: {output_file}")

if __name__ == '__main__':
    main()