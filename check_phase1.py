import json

with open(r'E:\HCL\fonts\download_phase1.json', encoding='utf-8') as f:
    d = json.load(f)

print('Phase 1 downloaded:')
for item in d['downloaded']:
    print(f'  {item["font"]} <- {item["zip"]}')
print(f'Total: {len(d["downloaded"])}')