"""Comprehensive Technical SEO & Asset Audit for Agro AI."""
import os
import re
from typing import List, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def audit_html_assets() -> Tuple[int, List[Tuple[str, str, str]]]:
    html_files = [
        "index.html",
        "privacy.html",
        "terms.html",
        "cookies.html",
        "delete-account.html",
    ]
    broken = []
    checked = 0

    for hf in html_files:
        fpath = os.path.join(ROOT, hf)
        if not os.path.exists(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        links = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', content)
        for link in links:
            if link.startswith(("http://", "https://", "mailto:", "tel:", "javascript:", "#", "data:")):
                continue
            clean = link.split("?")[0].split("#")[0].strip()
            if not clean:
                continue
            target = os.path.join(ROOT, clean.lstrip("/"))
            checked += 1
            if not os.path.exists(target) and not os.path.exists(target + ".html"):
                broken.append((hf, link, target))

    return checked, broken

if __name__ == "__main__":
    count, broken_links = audit_html_assets()
    print(f"Audited {count} internal resource links.")
    if broken_links:
        print(f"Found {len(broken_links)} potential broken links:")
        for source, link, target in broken_links:
            print(f"  [{source}] -> {link} (Expected: {target})")
    else:
        print("All internal links, scripts, fonts, and stylesheets resolved successfully!")
