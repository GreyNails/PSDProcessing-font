from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer, Group
import os

def remove_top_layer(input_path, output_path):
    """
    删除PSD文件中最上面的图层（Photoshop中显示在最顶部的图层）
    
    参数:
    input_path: 输入PSD文件路径
    output_path: 输出PSD文件路径
    """
    try:
        # 打开PSD文件
        psd = PSDImage.open(input_path)
        print(f"成功打开PSD文件: {input_path}")
        
        # 获取所有图层
        layers = list(psd)
        
        if not layers:
            print("PSD文件中没有图层")
            return
        
        # 在psd-tools中，图层顺序是反的
        # 最后一个图层（索引-1）是Photoshop中最上面的图层
        top_layer_index = len(layers) - 1
        top_layer = layers[top_layer_index]
        print(f"找到最上层图层: {top_layer.name} (索引: {top_layer_index})")
        
        # 将最上面的图层设置为不可见
        psd[top_layer_index].visible = False
        
        # 保存修改后的PSD文件
        psd.save(output_path)
        print(f"成功保存到: {output_path}")
        print(f"已将图层 '{top_layer.name}' 设置为不可见")
        
        # 显示所有图层信息
        print("\n当前图层结构（从上到下）：")
        for i in range(len(layers) - 1, -1, -1):
            visibility = "可见" if psd[i].visible else "隐藏"
            print(f"  图层 {len(layers) - i}: {psd[i].name} ({visibility})")
        
    except Exception as e:
        print(f"处理PSD文件时出错: {str(e)}")

def remove_top_layer_completely(input_path, output_path):
    """
    完全删除最上层图层的另一种方法
    通过重新构建图层列表来实现
    """
    try:
        from PIL import Image
        
        # 打开PSD文件
        psd = PSDImage.open(input_path)
        layers = list(psd)
        
        if not layers:
            print("PSD文件中没有图层")
            return
        
        # 获取最上层图层信息
        top_layer_index = len(layers) - 1
        top_layer = layers[top_layer_index]
        print(f"准备删除最上层图层: {top_layer.name}")
        
        # 创建一个新的合成图像，排除最上层
        width, height = psd.size
        composite_image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        # 从底层开始合成（不包括最顶层）
        for i in range(len(layers) - 1):  # 排除最后一个（最顶层）
            layer = layers[i]
            if layer.visible and hasattr(layer, 'composite'):
                layer_image = layer.composite()
                if layer_image:
                    # 获取图层位置
                    left, top, right, bottom = layer.bbox
                    composite_image.paste(layer_image, (left, top), layer_image)
                    print(f"  合成图层: {layer.name}")
        
        # 保存结果
        output_png = output_path.replace('.psd', '_without_top_layer.png')
        composite_image.save(output_png)
        print(f"\n已将结果保存为: {output_png}")
        
    except Exception as e:
        print(f"处理PSD文件时出错: {str(e)}")

def list_layers(psd_path):
    """
    列出PSD文件中的所有图层（按Photoshop中的顺序）
    """
    try:
        psd = PSDImage.open(psd_path)
        layers = list(psd)
        
        print(f"\nPSD文件 '{psd_path}' 中的图层（从上到下）：")
        print("-" * 50)
        
        # 反向遍历以匹配Photoshop中的显示顺序
        for i in range(len(layers) - 1, -1, -1):
            layer = layers[i]
            layer_num = len(layers) - i
            visibility = "👁️ " if layer.visible else "🚫"
            print(f"{visibility} 图层 {layer_num}: {layer.name}")
            
    except Exception as e:
        print(f"读取PSD文件时出错: {str(e)}")

# 使用示例
if __name__ == "__main__":
    # 设置输入输出路径
    input_file = "F:\dataprocesing\街舞.psd"  # 替换为你的输入文件路径
    output_file = "output_jiewu_v2.psd"  # 替换为你想要的输出文件路径
    
    # 先列出所有图层
    print("=== 原始文件图层信息 ===")
    list_layers(input_file)
    
    # # 方法1：将最上层设置为不可见
    # print("\n=== 执行删除操作 ===")
    # remove_top_layer(input_file, output_file)
    
    # 方法2：创建不包含最上层的合成图像
    remove_top_layer_completely(input_file, output_file)