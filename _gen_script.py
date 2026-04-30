# Script generator - creates the updated download_all_fonts.py
# Run: python _gen_script.py
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SCRIPT_DIR, "download_all_fonts.py")

parts = []

# Part 1: Header and imports
parts.append('''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Font Batch Download Script v2
Uses curl for HTTP (bypasses Python SSL issues in China).
Reads font_download_links.xlsx and downloads fonts from various sources.

Usage:
    python download_all_fonts.py --list                     # List all downloadable fonts
    python download_all_fonts.py --filter free              # Download free commercial fonts
    python download_all_fonts.py --filter all               # Download all non-paid fonts
    python download_all_fonts.py --filter free --max 5      # Test with 5 fonts
    python download_all_fonts.py --vendor "Adobe"           # Filter by vendor keyword
    python download_all_fonts.py --resume                   # Resume interrupted downloads
    python download_all_fonts.py --stats                    # Show download statistics
"""

import openpyxl
import os
import sys
import time
import re
import json
import argparse
import subprocess
from pathlib import Path
from urllib.parse import urlparse, quote, unquote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(SCRIPT_DIR, "font_download_links.xlsx")
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloads")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "download_progress_v2.json")
FAILED_FILE = os.path.join(SCRIPT_DIR, "download_failed_v2.txt")

# GitHub proxy (gh-proxy.com works in China when direct GitHub fails)
GH_PROXY = "https://gh-proxy.com/"
''')

# Part 2: License lists
parts.append('''
FREE_COMMERCIAL = [
    "\u514d\u8d39\u5546\u7528 (SIL OFL)", "\u514d\u8d39\u5546\u7528", "\u514d\u8d39\u5546\u7528 (IPA OFL\u7c7b)",
    "\u514d\u8d39\u5546\u7528(\u6ce8\u518c\u5373\u53ef)", "\u514d\u8d39\u5546\u7528(\u4e2a\u4eba\u7248)", "\u514d\u8d39\u5546\u7528 (\u4f5c\u8005\u5df2\u5ba3\u5e03)",
]
FREE_PERSONAL = [
    "\u514d\u8d39\u4e2a\u4eba", "\u514d\u8d39\u975e\u5546\u7528", "\u514d\u8d39\u975e\u5546\u7528 / \u5546\u4e1a\u9700\u8d2d\u4e70",
    "\u514d\u8d39\u975e\u5546\u7528 (NC = Non-Commercial)", "\u514d\u8d39\u4e2a\u4eba(\u786e\u8ba4\u6388\u6743)",
    "\u514d\u8d39\u4e2a\u4eba / \u5546\u4e1a\u9700\u8054\u7cfb\u4f5c\u8005", "\u9700\u8d2d\u4e70\u5546\u7528\u6388\u6743 (\u4e2a\u4eba\u975e\u5546\u7528\u53ef\u4e0b\u8f7d)",
]
SKIP_LICENSES = [
    "\u9700\u8d2d\u4e70\u5546\u7528\u6388\u6743", "\u5546\u4e1a\u4ed8\u8d39", "\u5546\u4e1a", "\u5546\u4e1a / \u5b57\u7531\u5ba2\u6237\u7aef",
    "\u5546\u4e1a / \u5df2\u4e0d\u6d41\u901a", "\u5546\u4e1a / \u9700\u786e\u8ba4", "\u5546\u4e1a (\u5b57\u5e93\u5df2\u4e0d\u6d3b\u8dc3)",
    "\u5546\u4e1a (\u5b57\u5382\u5df2\u4e0d\u6d3b\u8dc3)", "\u5546\u4e1a (Bitstream)", "\u5546\u4e1a (Fontfabric)",
    "\u5546\u4e1a (Hoefler)", "Windows \u7cfb\u7edf\u6388\u6743 / \u4e0d\u53ef\u5355\u72ec\u4e0b\u8f7d",
    "Windows\u7cfb\u7edf\u6388\u6743 / \u5546\u4e1a", "Windows \u7cfb\u7edf\u6388\u6743",
    "macOS/iOS \u7cfb\u7edf\u6388\u6743 / \u4e0d\u53ef\u5355\u72ec\u518d\u5206\u53d1", "Adobe Creative Cloud \u8ba2\u9605",
    "Trial/Demo (\u5546\u4e1a)", "Trial / \u5546\u4e1a", "\u9700\u8d2d\u4e70\u6388\u6743", "\u9700\u6388\u6743",
]
''')

print(f"Writing to {OUT}...")
with open(OUT, 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(p)
print(f"Part 1+2 written ({os.path.getsize(OUT)} bytes)")
