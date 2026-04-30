from psd_tools import PSDImage

def extract_fonts_from_psd(psd_file_path):
    psd = PSDImage.open(psd_file_path)
    fonts = []
    for layer in psd:
        if layer.kind == 'type':
            fonts.append(layer.font.name)
    return fonts

psd_file_path = r'D:\HCL\PSDProcessing\input\0702_freepik_v5_00b3bbcc38.psd'  # 替换为实际的PSD文件路径
font_list = extract_fonts_from_psd(psd_file_path)
for font in font_list:
    print(font)