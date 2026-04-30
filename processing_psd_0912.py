import os
import json
from PIL import Image
import numpy as np
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer, ShapeLayer, TypeLayer, AdjustmentLayer
try:
    from psd_tools.api.layers import Group
except ImportError:
    from psd_tools.api.layers import GroupLayer as Group
import io
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing
from functools import lru_cache
import warnings
import base64
from sklearn.cluster import KMeans
warnings.filterwarnings('ignore')

class OptimizedPSDLayerExtractor:
    def __init__(self, psd_path, output_folder):
        self.psd_path = psd_path
        self.output_folder = output_folder
        self.psd = PSDImage.open(psd_path)
        self.file_id = os.path.splitext(os.path.basename(psd_path))[0]
        self.layers_info = []
        
        # 创建输出文件夹
        file_output_folder = os.path.join(output_folder, self.file_id)
        os.makedirs(file_output_folder, exist_ok=True)
        self.file_output_folder = file_output_folder
        
        # 缓存composite结果
        self._composite_cache = {}
        
    def determine_layer_type_fast(self, layer):
        """快速判断图层类型（优化版）"""
        # 跳过不可见图层
        if not layer.is_visible():
            return None
            
        # 文本图层
        if isinstance(layer, TypeLayer):
            return "textElement"
        
        # 基于名称的快速判断
        layer_name_lower = layer.name.lower()
        if layer_name_lower in ['background', '背景', 'bg']:
            return "coloredBackground"
            
        # 形状图层
        if isinstance(layer, ShapeLayer):
            # 简化的背景检查
            if hasattr(layer, 'bbox') and layer.bbox:
                bounds = layer.bbox
                layer_area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
                if layer_area > (self.psd.width * self.psd.height * 0.8):
                    return "coloredBackground"
            return "svgElement"
            
        # 调整图层
        if isinstance(layer, AdjustmentLayer):
            return "maskElement"
            
        # 像素图层
        if isinstance(layer, PixelLayer):
            # 快速蒙版检查
            if layer.mask or 'mask' in layer_name_lower or '蒙版' in layer_name_lower:
                return "maskElement"
            
            # 大图层快速背景检查
            if hasattr(layer, 'bbox') and layer.bbox:
                bounds = layer.bbox
                layer_area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
                canvas_area = self.psd.width * self.psd.height
                
                if layer_area > canvas_area * 0.7:
                    return "coloredBackground"
            
            return "imageElement"
                
        # 组图层不处理
        if isinstance(layer, Group):
            return None
            
        return "imageElement"
    
    def _get_layer_composite(self, layer):
        """获取图层composite（带缓存）"""
        layer_id = id(layer)
        if layer_id not in self._composite_cache:
            self._composite_cache[layer_id] = layer.composite()
        return self._composite_cache[layer_id]
    
    def extract_dominant_color(self, img):
        """提取图像的主要颜色"""
        try:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 缩小图像以加快处理速度
            img_small = img.resize((50, 50), Image.Resampling.LANCZOS)
            
            # 转换为numpy数组
            img_array = np.array(img_small)
            
            # 只考虑不透明的像素
            if img_array.shape[-1] == 4:  # RGBA
                mask = img_array[:, :, 3] > 128  # 透明度大于128的像素
                pixels = img_array[mask][:, :3]  # 只取RGB值
            else:
                pixels = img_array.reshape(-1, 3)
            
            if len(pixels) == 0:
                return [255, 255, 255]  # 默认白色
            
            # 使用KMeans找到主要颜色
            if len(pixels) > 3:
                kmeans = KMeans(n_clusters=1, random_state=0, n_init=10)
                kmeans.fit(pixels)
                dominant_color = kmeans.cluster_centers_[0]
            else:
                dominant_color = np.mean(pixels, axis=0)
            
            return [int(c) for c in dominant_color]
        except:
            return [255, 255, 255]
    
    def get_text_properties(self, layer):
        """提取文本图层的属性"""
        text = ""
        font = ""
        font_size = 0.0
        text_align = "left"
        
        if isinstance(layer, TypeLayer):
            try:
                # 获取文本内容
                text = layer.text
                
                # 获取字体信息
                if hasattr(layer, 'engine_data'):
                    engine_data = layer.engine_data
                    
                    # 获取字体名称
                    if 'StyleRun' in engine_data and 'RunArray' in engine_data['StyleRun']:
                        style_runs = engine_data['StyleRun']['RunArray']
                        if style_runs and len(style_runs) > 0:
                            style_sheet = style_runs[0].get('StyleSheet', {})
                            style_data = style_sheet.get('StyleSheetData', {})
                            font = style_data.get('Font', '')
                            
                            # 获取字体大小（像素）
                            if 'FontSize' in style_data:
                                font_size = float(style_data['FontSize'])
                    
                    # 获取文本对齐方式
                    if 'ParagraphRun' in engine_data and 'RunArray' in engine_data['ParagraphRun']:
                        para_runs = engine_data['ParagraphRun']['RunArray']
                        if para_runs and len(para_runs) > 0:
                            para_sheet = para_runs[0].get('ParagraphSheet', {})
                            para_data = para_sheet.get('Properties', {})
                            justification = para_data.get('Justification', 0)
                            
                            # 转换对齐方式
                            align_map = {0: 'left', 1: 'right', 2: 'center', 3: 'justify'}
                            text_align = align_map.get(justification, 'left')
            except:
                pass
        
        return text, font, font_size, text_align
    
    def get_layer_opacity(self, layer):
        """获取图层不透明度"""
        try:
            if hasattr(layer, 'opacity'):
                return layer.opacity / 255.0
        except:
            pass
        return 1.0
    
    def get_layer_angle(self, layer):
        """获取图层旋转角度（弧度）"""
        try:
            # 检查transform属性
            if hasattr(layer, 'transform'):
                # 提取旋转角度
                transform = layer.transform
                if transform and 'xx' in transform and 'xy' in transform:
                    # 从变换矩阵计算旋转角度
                    angle = np.arctan2(transform['xy'], transform['xx'])
                    return float(angle)
        except:
            pass
        return 0.0
    
    def image_to_png_bytes(self, img):
        """将PIL图像转换为PNG字节"""
        try:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 调整大小到256x256
            img_resized = img.resize((256, 256), Image.Resampling.LANCZOS)
            
            # 保存到字节流
            buffer = io.BytesIO()
            img_resized.save(buffer, format='PNG', optimize=True)
            png_bytes = buffer.getvalue()
            buffer.close()
            
            return png_bytes
        except:
            # 返回空的1x1透明PNG
            empty_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\x00\x00\x00IEND\xaeB`\x82'
            return empty_png
    
    def process_layer_data(self, layer_data):
        """处理单个图层数据，提取所有属性"""
        layer, layer_type, z_index = layer_data
        
        try:
            # 获取composite图像
            img = self._get_layer_composite(layer)
            if not img:
                return None
            
            # 获取边界
            bounds = layer.bbox
            if not bounds:
                return None
            
            # 计算归一化坐标
            left = bounds[0] / self.psd.width
            top = bounds[1] / self.psd.height
            width = (bounds[2] - bounds[0]) / self.psd.width
            height = (bounds[3] - bounds[1]) / self.psd.height
            
            # 获取图像字节
            image_bytes = self.image_to_png_bytes(img)
            
            # 获取主色调
            color = self.extract_dominant_color(img)
            
            # 获取不透明度
            opacity = self.get_layer_opacity(layer)
            
            # 获取旋转角度
            angle = self.get_layer_angle(layer)
            
            # 获取文本属性
            text, font, font_size, text_align = self.get_text_properties(layer)
            
            return {
                "z": z_index,
                "type": layer_type,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "color": color,
                "opacity": opacity,
                "image_bytes": image_bytes,
                "text": text,
                "font": font,
                "font_size": font_size,
                "text_align": text_align,
                "angle": angle,
                "layer_name": layer.name
            }
            
        except Exception as e:
            print(f"处理图层 {layer.name} 时出错: {e}")
            return None
    
    def collect_all_layers(self):
        """收集所有需要处理的图层信息"""
        layers_to_export = []
        
        def collect_recursive(layers, z_start=0):
            z_index = z_start
            for layer in reversed(list(layers)):
                if not layer.is_visible():
                    continue
                    
                if isinstance(layer, Group):
                    z_index = collect_recursive(layer, z_index)
                    continue
                
                layer_type = self.determine_layer_type_fast(layer)
                if layer_type is None:
                    continue
                    
                bounds = layer.bbox
                if not bounds:
                    continue
                
                layers_to_export.append({
                    'layer': layer,
                    'type': layer_type,
                    'z': z_index,
                    'bounds': bounds,
                    'name': layer.name
                })
                z_index += 1
            return z_index
        
        collect_recursive(self.psd)
        return layers_to_export
    
    def export_preview_optimized(self):
        """优化的预览图导出并转为字节"""
        try:
            # 直接使用PSD的composite方法
            preview = self.psd.composite()
            
            if preview:
                # 转换为RGB
                if preview.mode == 'RGBA':
                    background = Image.new('RGB', preview.size, (255, 255, 255))
                    background.paste(preview, mask=preview.split()[3])
                    preview = background
                elif preview.mode != 'RGB':
                    preview = preview.convert('RGB')
                
                # 转为字节
                buffer = io.BytesIO()
                preview.save(buffer, 'PNG', quality=85, optimize=True)
                preview_bytes = buffer.getvalue()
                buffer.close()
                
                return preview_bytes
        except:
            return None
    
    def extract_optimized(self):
        """优化的提取流程"""
        try:
            # 1. 导出预览图
            preview_bytes = self.export_preview_optimized()
            
            # 2. 收集所有图层信息
            layers_to_export = self.collect_all_layers()
            
            # 3. 使用线程池并行处理图层
            with ThreadPoolExecutor(max_workers=4) as executor:
                # 准备处理任务
                process_tasks = []
                for layer_info in layers_to_export:
                    task = (layer_info['layer'], layer_info['type'], layer_info['z'])
                    process_tasks.append(task)
                
                # 并行处理
                futures = {executor.submit(self.process_layer_data, task): task 
                          for task in process_tasks}
                
                # 收集结果
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        self.layers_info.append(result)
            
            # 4. 保存JSON（新格式）
            self.save_json_enhanced(preview_bytes)
            
            # 清理缓存
            self._composite_cache.clear()
            
            return True
        except Exception as e:
            print(f"处理文件 {self.psd_path} 时出错: {e}")
            return False
    
    def save_json_enhanced(self, preview_bytes):
        """保存增强版的JSON（包含图像字节和所有属性）"""
        json_filename = f"{self.file_id}_layers.json"
        json_path = os.path.join(self.file_output_folder, json_filename)
        
        # 按z值排序
        self.layers_info.sort(key=lambda x: x['z'])
        
        # 构建列表格式（类似data_example）
        list_format = {
            "id": self.file_id.encode('utf-8'),  # 转为字节格式
            "canvas_width": self.psd.width,
            "canvas_height": self.psd.height,
            "length": len(self.layers_info),
            "preview_bytes": preview_bytes if preview_bytes else b'',
            
            # 所有属性都用列表存储
            "z": [l["z"] for l in self.layers_info],
            "type": [l["type"].encode('utf-8') for l in self.layers_info],  # 转为字节
            "left": [float(l["left"]) for l in self.layers_info],
            "top": [float(l["top"]) for l in self.layers_info],
            "width": [float(l["width"]) for l in self.layers_info],
            "height": [float(l["height"]) for l in self.layers_info],
            "color": [l["color"] for l in self.layers_info],
            "opacity": [float(l["opacity"]) for l in self.layers_info],
            "image_bytes": [l["image_bytes"] for l in self.layers_info],
            "text": [l["text"].encode('utf-8') for l in self.layers_info],  # 转为字节
            "font": [l["font"].encode('utf-8') for l in self.layers_info],  # 转为字节
            "font_size": [float(l["font_size"]) for l in self.layers_info],
            "text_align": [l["text_align"].encode('utf-8') for l in self.layers_info],  # 转为字节
            "angle": [float(l["angle"]) for l in self.layers_info],
            "layer_names": [l["layer_name"] for l in self.layers_info]  # 保留用于调试
        }
        
        # 为了正确保存字节数据，需要特殊处理
        # 将字节数据转为base64字符串以便JSON序列化
        json_serializable = {
            "id": list_format["id"].decode('utf-8'),
            "canvas_width": list_format["canvas_width"],
            "canvas_height": list_format["canvas_height"],
            "length": list_format["length"],
            "preview_bytes": base64.b64encode(list_format["preview_bytes"]).decode('utf-8'),
            "z": list_format["z"],
            "type": [t.decode('utf-8') for t in list_format["type"]],
            "left": list_format["left"],
            "top": list_format["top"],
            "width": list_format["width"],
            "height": list_format["height"],
            "color": list_format["color"],
            "opacity": list_format["opacity"],
            "image_bytes": [base64.b64encode(img).decode('utf-8') for img in list_format["image_bytes"]],
            "text": [t.decode('utf-8') for t in list_format["text"]],
            "font": [f.decode('utf-8') for f in list_format["font"]],
            "font_size": list_format["font_size"],
            "text_align": [ta.decode('utf-8') for ta in list_format["text_align"]],
            "angle": list_format["angle"],
            "layer_names": list_format["layer_names"]
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_serializable, f, ensure_ascii=False, indent=2)


def process_single_psd(args):
    """处理单个PSD文件（用于多进程）"""
    psd_file, output_folder = args
    try:
        extractor = OptimizedPSDLayerExtractor(psd_file, output_folder)
        success = extractor.extract_optimized()
        return psd_file, success
    except Exception as e:
        print(f"处理 {psd_file} 时出错: {e}")
        return psd_file, False


def get_all_psd_files(folder_path):
    """获取文件夹中所有PSD文件"""
    psd_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.psd'):
                psd_files.append(os.path.join(root, file))
    return psd_files


def main():
    # 配置
    # psd_folder = r"D:\HCL\PSDProcessing\input\0702_freepik_v5_00b3bbcc38.psd"
    psd_folder = r"D:\HCL\PSDProcessing\input"

    output_folder = r"D:\HCL\PSDProcessing\ouput_0917"
    
    # 确保输出文件夹存在
    os.makedirs(output_folder, exist_ok=True)
    
    # 获取所有PSD文件
    psd_files = get_all_psd_files(psd_folder)
    total_files = len(psd_files)
    
    if total_files == 0:
        print(f"错误：在 {psd_folder} 中未找到PSD文件")
        return
        
    print(f"找到 {total_files} 个PSD文件，开始批量处理...")
    
    # 确定进程数（CPU核心数的一半，但不超过8）
    num_processes = min(multiprocessing.cpu_count() // 2, 16, total_files)
    print(f"使用 {num_processes} 个进程并行处理...")
    
    # 准备任务参数
    tasks = [(psd_file, output_folder) for psd_file in psd_files]
    
    # 使用进程池并行处理
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        # 提交所有任务
        futures = {executor.submit(process_single_psd, task): task[0] 
                  for task in tasks}
        
        # 使用tqdm显示进度
        with tqdm(total=total_files, desc="处理PSD文件") as pbar:
            for future in as_completed(futures):
                psd_file = futures[future]
                try:
                    _, success = future.result()
                    if success:
                        pbar.set_postfix_str(f"完成: {os.path.basename(psd_file)}")
                except Exception as e:
                    print(f"\n错误处理 {psd_file}: {e}")
                pbar.update(1)
    
    print("\n批量处理完成！")


if __name__ == "__main__":
    main()