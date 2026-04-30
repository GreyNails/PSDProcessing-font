import pandas as pd
import json

df = pd.read_excel(r'E:\HCL\fonts\font_download_links.xlsx', sheet_name=1, engine='openpyxl', header=2)
df.columns = ['font_name', 'category', 'source', 'license', 'download_url', 'notes']
df = df.dropna(subset=['font_name'])
df = df[df['font_name'].astype(str).str.strip() != '']
df = df[~df['font_name'].astype(str).str.contains('font_name|原字体名称', na=False)]

data = []
for _, row in df.iterrows():
    fn = str(row['font_name']).strip() if pd.notna(row['font_name']) else ''
    url = str(row['download_url']).strip() if pd.notna(row['download_url']) else ''
    cat = str(row['category']).strip() if pd.notna(row['category']) else ''
    src = str(row['source']).strip() if pd.notna(row['source']) else ''
    lic = str(row['license']).strip() if pd.notna(row['license']) else ''
    if fn and fn != 'nan':
        data.append({'font_name': fn, 'category': cat, 'source': src, 'license': lic, 'download_url': url})

with open(r'E:\HCL\fonts\font_download_links_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'Total fonts extracted: {len(data)}')
for item in data[:10]:
    print(f'  {item["font_name"]} -> {item["download_url"]}')
