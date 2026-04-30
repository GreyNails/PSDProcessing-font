# Append part 6: main function
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SCRIPT_DIR, "download_all_fonts.py")

content = r'''

# ============================================================
# Deduplication
# ============================================================
def deduplicate_downloads(fonts):
    """Group fonts sharing the same download URL."""
    groups = {}
    for font in fonts:
        link = font["link"]
        if link not in groups:
            groups[link] = []
        groups[link].append(font)
    result = [(group[0], group) for group in groups.values()]
    print(f"Deduplicated: {len(fonts)} fonts -> {len(result)} unique download sources")
    return result


# ============================================================
# CLI and main
# ============================================================
def print_stats(progress, fonts):
    done = sum(1 for v in progress.values() if v == "done")
    failed = sum(1 for v in progress.values() if v == "failed")
    manual = sum(1 for v in progress.values() if v == "manual")
    total = len(fonts)
    remaining = total - done - failed - manual

    print(f"\n{'='*60}")
    print(f"Download Statistics")
    print(f"{'='*60}")
    print(f"Total fonts in Excel:  {total}")
    print(f"Downloaded (done):     {done}")
    print(f"Failed:                {failed}")
    print(f"Manual needed:         {manual}")
    print(f"Remaining:             {remaining}")
    print(f"{'='*60}")

    if failed > 0:
        print(f"\nFailed fonts:")
        for font in fonts:
            if progress.get(font["font_name"]) == "failed":
                print(f"  - {font['font_name']} ({font['vendor']}) -> {font['link']}")


def main():
    parser = argparse.ArgumentParser(description="Font Batch Download Script v2 (curl-based)")
    parser.add_argument("--filter", choices=["free", "personal", "all", "none"],
                        default="free",
                        help="License filter (default: free)")
    parser.add_argument("--vendor", type=str, default=None,
                        help="Filter by vendor keyword")
    parser.add_argument("--max", type=int, default=None,
                        help="Max number of fonts to download")
    parser.add_argument("--list", action="store_true",
                        help="List fonts only, do not download")
    parser.add_argument("--stats", action="store_true",
                        help="Show download statistics")
    parser.add_argument("--resume", action="store_true",
                        help="Resume: skip already downloaded fonts")
    parser.add_argument("--reset", action="store_true",
                        help="Reset progress and start fresh")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory (default: ./downloads)")
    parser.add_argument("--no-proxy", action="store_true",
                        help="Disable gh-proxy.com for GitHub")
    args = parser.parse_args()

    # Check curl is available
    try:
        subprocess.run(['curl', '--version'], capture_output=True, timeout=5)
    except Exception:
        print("ERROR: curl is required but not found. Install curl and try again.")
        sys.exit(1)

    # Load data
    fonts = load_fonts_from_excel()
    progress = load_progress()

    if args.reset:
        progress = {}
        save_progress(progress)
        print("Progress reset.")

    if args.no_proxy:
        global GH_PROXY
        GH_PROXY = ""

    download_dir = args.output or DOWNLOAD_DIR
    os.makedirs(download_dir, exist_ok=True)

    # Filter
    filtered = filter_fonts(fonts, args.filter, args.vendor)

    if args.max:
        filtered = filtered[:args.max]

    if args.stats:
        print_stats(progress, filtered)
        return

    if args.list:
        print(f"\n{'='*80}")
        print(f"Font List ({len(filtered)} fonts)")
        print(f"{'='*80}")
        for i, font in enumerate(filtered, 1):
            status = progress.get(font["font_name"], "pending")
            marker = "[OK]" if status == "done" else "[FAIL]" if status == "failed" else "[ ]"
            print(f"  {i:3d}. {marker} {font['font_name']}")
            print(f"       {font['cn_name']} | {font['vendor']} | {font['license']}")
            print(f"       {font['link']}")
        return

    # Deduplicate and download
    groups = deduplicate_downloads(filtered)

    print(f"\n{'='*60}")
    print(f"Starting download: {len(groups)} sources for {len(filtered)} fonts")
    print(f"Output: {download_dir}")
    print(f"{'='*60}")

    done_count = 0
    fail_count = 0
    skip_count = 0

    for i, (rep_font, group_fonts) in enumerate(groups, 1):
        font_name = rep_font["font_name"]

        # Skip if already done (resume mode)
        if args.resume and progress.get(font_name) == "done":
            skip_count += 1
            continue

        print(f"\n[{i}/{len(groups)}]")
        success = download_font(rep_font, progress, download_dir)

        # Mark all fonts in the group
        for gf in group_fonts:
            if success:
                progress[gf["font_name"]] = "done"
            elif progress.get(gf["font_name"]) != "done":
                progress[gf["font_name"]] = "failed"

        if success:
            done_count += 1
        else:
            fail_count += 1

        save_progress(progress)
        time.sleep(0.5)

    # Summary
    print(f"\n{'='*60}")
    print(f"Download Complete")
    print(f"{'='*60}")
    print(f"  Downloaded: {done_count}")
    print(f"  Failed:     {fail_count}")
    print(f"  Skipped:    {skip_count}")
    print(f"  Total:      {len(groups)}")

    # Write manual download list
    manual_fonts = [f for f in filtered if progress.get(f["font_name"]) in ("failed", "manual")]
    if manual_fonts:
        manual_file = os.path.join(download_dir, "_MANUAL_DOWNLOADS.txt")
        with open(manual_file, "w", encoding="utf-8") as f:
            f.write("# Fonts that need manual download\n")
            f.write("# font_name\tcn_name\tvendor\tlicense\tlink\n")
            for font in manual_fonts:
                f.write(f"{font['font_name']}\t{font['cn_name']}\t{font['vendor']}\t{font['license']}\t{font['link']}\n")
        print(f"\nManual download list: {manual_file}")


if __name__ == "__main__":
    main()
'''

with open(OUT, 'a', encoding='utf-8') as f:
    f.write(content)

print(f"Part 6 written, total: {os.path.getsize(OUT)} bytes")
