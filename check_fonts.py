import os

path = r'E:\HCL\fonts\unmatched_fonts'
files = sorted([f for f in os.listdir(path) if f.endswith(('.ttf','.otf'))])
print(f'Total font files in unmatched_fonts/: {len(files)}')
print()

for f in files:
    full = os.path.join(path, f)
    sz = os.path.getsize(full)
    with open(full, 'rb') as fh:
        magic = fh.read(4)
    tag = 'OTF' if magic == b'OTTO' else 'TTF'
    status = 'SMALL!' if sz < 20000 else 'OK'
    print(f'{f}: {sz:,} bytes, {tag}, {status}')