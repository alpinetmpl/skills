#!/usr/bin/env python3
"""
html_to_md.py — batch convert downloaded HTML to clean markdown.

Walks an input directory of HTML files (one per page), converts each to
markdown via the `markdownify` library, strips the standard chrome
(nav/footer/scripts/styles/cookie banners), and writes the result into an
output tree that mirrors the original URL path structure.

Files are placed at: <output>/<url-path>.md
- /docs/foo/bar         → <output>/docs/foo/bar.md
- /docs/foo/bar/index   → <output>/docs/foo/bar.md (if no siblings) OR
                          <output>/docs/foo/bar/index.md (if it has children)

Input HTML filenames are expected to encode the URL path. If you used the
fetch loop in SKILL.md (`curl -o /tmp/<vendor>-html/$(echo $url | sed
"s|https://||;s|/|_|g").html`), this script's --base-url + filename decoding
will reconstruct the URL → path mapping correctly.

Usage:
    python3 html_to_md.py --input /tmp/vendor-html \\
                          --output ~/github.com/alpinetmpl/docs/vendor/docs.vendor.com/ \\
                          --base-url https://docs.vendor.com
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from markdownify import markdownify  # type: ignore
except ImportError:
    import subprocess

    print("markdownify not found — installing...", file=sys.stderr)
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "markdownify"], check=True)
    from markdownify import markdownify  # type: ignore

STRIP_TAGS = ["nav", "footer", "script", "style", "header", "aside", "form", "iframe", "noscript", "svg"]

# Selectors that frequently wrap navigation/chrome on doc sites — drop them entirely.
CHROME_SELECTORS_RE = re.compile(
    r"<(div|section|aside)[^>]*\b(class|id)=\"[^\"]*"
    r"(navbar|sidebar|toc|breadcrumb|cookie|consent|edit-this-page|search-box|"
    r"announcement|banner|footer)[^\"]*\"[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


def strip_chrome(html: str) -> str:
    """Pre-process HTML to remove common chrome divs before markdownify."""
    return CHROME_SELECTORS_RE.sub("", html)


def html_filename_to_url_path(filename: str, base_url: str) -> str:
    """Reverse the curl-style encoding `https://host/foo/bar` → `host_foo_bar.html`.

    Assumes underscores in filenames came from path separators. This is the
    encoding the SKILL.md fetch snippet uses; if the user used a different
    encoding they should adjust.
    """
    stem = Path(filename).stem
    base_host = urlparse(base_url).netloc

    # Strip the host prefix if present
    if stem.startswith(base_host.replace(".", "_")):
        stem = stem[len(base_host.replace(".", "_")):]
    elif stem.startswith(base_host):
        stem = stem[len(base_host):]

    # Underscores → slashes for the path
    path = stem.replace("_", "/").lstrip("/")
    return "/" + path if path else "/"


def url_path_to_file_path(url_path: str, output_root: Path, has_children: bool) -> Path:
    """Map a URL path to its markdown file path under output_root.

    /docs/foo/bar          → output_root/docs/foo/bar.md
    /docs/foo/bar/  + child → output_root/docs/foo/bar/index.md
    /docs/foo/bar/  no child → output_root/docs/foo/bar.md
    """
    clean = url_path.strip("/")
    if not clean:
        return output_root / "index.md"

    if has_children:
        return output_root / clean / "index.md"
    return output_root / f"{clean}.md"


def detect_children(url_paths: set[str]) -> set[str]:
    """Return the set of URL paths that have other URLs as children."""
    parents: set[str] = set()
    for p in url_paths:
        clean = p.strip("/")
        if not clean:
            continue
        parts = clean.split("/")
        for i in range(1, len(parts)):
            parents.add("/" + "/".join(parts[:i]) + "/")
            parents.add("/" + "/".join(parts[:i]))
    return parents & url_paths


def convert(html: str) -> str:
    cleaned = strip_chrome(html)
    md = markdownify(
        cleaned,
        heading_style="ATX",
        strip=STRIP_TAGS,
        code_language="",
        bullets="-",
    )
    # Collapse runs of >2 blank lines
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="Directory of .html files")
    parser.add_argument("--output", type=Path, required=True, help="Output directory for .md tree")
    parser.add_argument("--base-url", required=True, help="Source base URL, e.g. https://docs.vendor.com")
    parser.add_argument("--dry-run", action="store_true", help="Show planned writes without writing")
    args = parser.parse_args()

    if not args.input.is_dir():
        print(f"Input directory does not exist: {args.input}", file=sys.stderr)
        return 1

    html_files = sorted(args.input.rglob("*.html")) + sorted(args.input.rglob("*.htm"))
    if not html_files:
        print(f"No HTML files found under {args.input}", file=sys.stderr)
        return 1

    # First pass: collect all URL paths so we know which are parents-of-children
    url_paths_by_file: dict[Path, str] = {}
    for f in html_files:
        url_path = html_filename_to_url_path(f.name, args.base_url)
        url_paths_by_file[f] = url_path

    children = detect_children(set(url_paths_by_file.values()))

    written = 0
    skipped = 0
    args.output.mkdir(parents=True, exist_ok=True)

    for f, url_path in url_paths_by_file.items():
        try:
            html = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"  [skip] {f}: {e}", file=sys.stderr)
            skipped += 1
            continue

        md = convert(html)
        if len(md.strip()) < 50:
            print(f"  [skip] {f}: converted output is near-empty (likely nav-only page)", file=sys.stderr)
            skipped += 1
            continue

        out_path = url_path_to_file_path(url_path, args.output, has_children=url_path in children)

        if args.dry_run:
            print(f"  {f.name} → {out_path}")
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md, encoding="utf-8")
        written += 1

    print(f"\nConverted {written} files, skipped {skipped}.", file=sys.stderr)
    if not args.dry_run:
        print(f"Output: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
