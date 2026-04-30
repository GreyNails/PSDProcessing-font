import sys, io, subprocess, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Check GitHub rate limit
print("=== GitHub API Rate Limit ===")
r = subprocess.run(
    ['curl', '-sk', '--max-time', '10',
     '-H', 'User-Agent: FontDownloader/1.0',
     'https://api.github.com/rate_limit'],
    capture_output=True, text=True, timeout=15
)
if r.returncode == 0 and r.stdout:
    try:
        data = json.loads(r.stdout)
        core = data.get('resources', {}).get('core', {})
        print(f"  Remaining: {core.get('remaining')}/{core.get('limit')}")
        print(f"  Reset: {core.get('reset')}")
    except:
        print(f"  Raw: {r.stdout[:300]}")
else:
    print(f"  Failed: {r.stderr[:200]}")

# Try getting repo contents via raw URL (no API needed)
print("\n=== Direct raw content access ===")
repos_to_check = [
    ('ichitenfont/I.Ngaan', 'master'),
    ('ichitenfont/I.PenCrane', 'master'),
    ('Pal3love/KingHwa_OldSong', 'main'),
    ('ichitenfont/I.Ming', 'master'),
]

for repo, branch in repos_to_check:
    print(f"\n--- {repo} ---")
    # Use GitHub web page to find font files (not API)
    r = subprocess.run(
        ['curl', '-sk', '--max-time', '15', '-L',
         '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
         f'https://github.com/{repo}'],
        capture_output=True, text=True, timeout=20, encoding='utf-8', errors='replace'
    )
    if r.returncode == 0:
        html = r.stdout
        # Find font file links in the repo page
        font_links = re.findall(r'href="(/[^"]+\.(?:ttf|otf|ttc|zip|woff2?))"', html, re.IGNORECASE)
        if font_links:
            for fl in font_links[:5]:
                print(f"  Font link: {fl}")
        else:
            # Look for release links
            rel_links = re.findall(r'href="(/[^"]*releases[^"]*)"', html)
            if rel_links:
                print(f"  Release links: {rel_links[:3]}")
            # Look for any file links
            all_files = re.findall(r'href="(/[^"]+/blob/[^"]+)"', html)
            font_files = [f for f in all_files if any(f.lower().endswith(ext) for ext in ['.ttf', '.otf', '.ttc', '.zip'])]
            if font_files:
                for ff in font_files[:5]:
                    print(f"  Font in repo: {ff}")
            else:
                # Just show directory structure hints
                dirs = re.findall(r'href="(/[^"]+/tree/[^"]+)"', html)
                for d in dirs[:10]:
                    print(f"  Dir: {d}")
    else:
        print(f"  Failed: {r.stderr[:200]}")
