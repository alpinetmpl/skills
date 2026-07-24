#!/usr/bin/env python3
"""
discover_urls.py — exhaustively discover documentation URLs for a domain.

Runs a cascade of discovery methods (llms-full.txt, llms.txt, sitemaps,
robots.txt, common alternate sitemap paths) and prints a deduped URL list
filtered to a doc prefix, plus a coverage report so the caller can decide
whether to fall back to manual crawl.

The agent calling this script should compare the section counts against the
live nav. If the nav lists sections the URL list doesn't, discovery was
partial and a manual crawl is needed.

Usage:
    python3 discover_urls.py <domain> [--doc-prefix /docs/] [--output urls.txt]

Examples:
    python3 discover_urls.py tailscale.com --doc-prefix /docs/
    python3 discover_urls.py docs.vendor.io --output /tmp/vendor-urls.txt
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

USER_AGENT = "docs-update-discover/1.0 (+https://github.com/alpinetmpl/docs)"
TIMEOUT = 30


def fetch(url: str) -> tuple[int, str]:
    """GET a URL, return (status, body). Returns (0, '') on network error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return 0, ""


def urls_from_sitemap_xml(body: str, base: str) -> list[str]:
    """Parse a sitemap.xml or sitemap_index.xml body and yield all URLs.

    Recurses one level into sitemap indexes (which contain <sitemap><loc>
    pointing at sub-sitemaps).
    """
    urls: list[str] = []
    try:
        # Strip default namespace to make parsing easier
        cleaned = re.sub(r'\sxmlns="[^"]+"', "", body, count=1)
        root = ET.fromstring(cleaned)
    except ET.ParseError:
        return urls

    # sitemap index: <sitemapindex><sitemap><loc>...</loc></sitemap></sitemapindex>
    for loc in root.findall(".//sitemap/loc"):
        if loc.text:
            sub_url = loc.text.strip()
            status, sub_body = fetch(sub_url)
            if status == 200 and sub_body:
                urls.extend(urls_from_sitemap_xml(sub_body, base))

    # regular sitemap: <urlset><url><loc>...</loc></url></urlset>
    for loc in root.findall(".//url/loc"):
        if loc.text:
            urls.append(loc.text.strip())

    return urls


def urls_from_sitemap_txt(body: str) -> list[str]:
    """sitemap.txt is one URL per line."""
    return [line.strip() for line in body.splitlines() if line.strip().startswith("http")]


def urls_from_llms_txt(body: str, base: str) -> list[str]:
    """Extract URLs from an llms.txt-style markdown file.

    llms.txt is markdown with [title](url) links. We pull all absolute URLs
    and resolve any relative ones against the base domain.
    """
    urls: list[str] = []
    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    bare_re = re.compile(r"https?://[^\s)>\]]+")

    for match in link_re.finditer(body):
        href = match.group(1).strip()
        if href.startswith("http"):
            urls.append(href)
        elif href.startswith("/"):
            urls.append(urljoin(base, href))

    for match in bare_re.finditer(body):
        urls.append(match.group(0))

    return urls


def urls_from_llms_full_txt(body: str, base: str) -> list[str]:
    """llms-full.txt is the same shape as llms.txt for our purposes."""
    return urls_from_llms_txt(body, base)


def sitemap_urls_from_robots(body: str) -> list[str]:
    """Extract `Sitemap:` directives from robots.txt."""
    return [
        line.split(":", 1)[1].strip()
        for line in body.splitlines()
        if line.lower().startswith("sitemap:")
    ]


def filter_to_doc_prefix(urls: list[str], doc_prefix: str | None, domain: str) -> list[str]:
    """Keep only URLs on the target domain whose path starts with doc_prefix.

    If doc_prefix is None, keep all URLs on the target domain.
    """
    kept: list[str] = []
    for url in urls:
        parsed = urlparse(url)
        if parsed.netloc != domain:
            continue
        if doc_prefix and not parsed.path.startswith(doc_prefix):
            continue
        kept.append(url)
    return kept


def section_counts(urls: list[str], doc_prefix: str | None) -> Counter[str]:
    """Bucket URLs by their first path segment after doc_prefix for coverage report."""
    counts: Counter[str] = Counter()
    strip_len = len(doc_prefix) if doc_prefix else 0
    for url in urls:
        path = urlparse(url).path[strip_len:].lstrip("/")
        section = path.split("/", 1)[0] or "(root)"
        counts[section] += 1
    return counts


def discover(domain: str, doc_prefix: str | None) -> dict:
    """Run the full discovery cascade and return raw results per source."""
    base = f"https://{domain}"
    sources: dict[str, dict] = {}

    # 1. llms-full.txt — best case, full docs in one file
    status, body = fetch(f"{base}/llms-full.txt")
    if status == 200 and body:
        urls = urls_from_llms_full_txt(body, base)
        sources["llms-full.txt"] = {"found": True, "url_count": len(urls), "urls": urls}
    else:
        sources["llms-full.txt"] = {"found": False, "status": status}

    # 2. llms.txt — index
    status, body = fetch(f"{base}/llms.txt")
    if status == 200 and body:
        urls = urls_from_llms_txt(body, base)
        sources["llms.txt"] = {"found": True, "url_count": len(urls), "urls": urls}
    else:
        sources["llms.txt"] = {"found": False, "status": status}

    # 3. sitemap.xml and sitemap_index.xml
    for sitemap_path in ("/sitemap.xml", "/sitemap_index.xml"):
        status, body = fetch(f"{base}{sitemap_path}")
        key = sitemap_path.lstrip("/")
        if status == 200 and body:
            urls = urls_from_sitemap_xml(body, base)
            sources[key] = {"found": True, "url_count": len(urls), "urls": urls}
        else:
            sources[key] = {"found": False, "status": status}

    # 4. robots.txt — extract Sitemap: directives, follow non-standard ones
    status, body = fetch(f"{base}/robots.txt")
    if status == 200 and body:
        robots_sitemaps = sitemap_urls_from_robots(body)
        sources["robots.txt"] = {"found": True, "sitemap_count": len(robots_sitemaps), "sitemaps": robots_sitemaps}
        for sm_url in robots_sitemaps:
            # Skip ones we already fetched above
            if sm_url in (f"{base}/sitemap.xml", f"{base}/sitemap_index.xml"):
                continue
            sm_status, sm_body = fetch(sm_url)
            key = f"robots:{sm_url}"
            if sm_status == 200 and sm_body:
                urls = urls_from_sitemap_xml(sm_body, base)
                if not urls:
                    urls = urls_from_sitemap_txt(sm_body)
                sources[key] = {"found": True, "url_count": len(urls), "urls": urls}
            else:
                sources[key] = {"found": False, "status": sm_status}
    else:
        sources["robots.txt"] = {"found": False, "status": status}

    # 5. Common alternate sitemap paths
    for alt in ("/sitemap-docs.xml", "/docs/sitemap.xml", "/sitemap.txt"):
        status, body = fetch(f"{base}{alt}")
        key = alt.lstrip("/")
        if status == 200 and body:
            if alt.endswith(".xml"):
                urls = urls_from_sitemap_xml(body, base)
            else:
                urls = urls_from_sitemap_txt(body)
            if urls:
                sources[key] = {"found": True, "url_count": len(urls), "urls": urls}
            else:
                sources[key] = {"found": False, "status": status, "note": "parsed but empty"}
        else:
            sources[key] = {"found": False, "status": status}

    return {"base": base, "domain": domain, "doc_prefix": doc_prefix, "sources": sources}


def print_report(result: dict, all_urls: list[str], filtered_urls: list[str]) -> None:
    base = result["base"]
    doc_prefix = result["doc_prefix"]

    print(f"\n=== Discovery report for {base} ===\n", file=sys.stderr)
    print(f"Doc prefix filter: {doc_prefix or '(none — kept all on-domain URLs)'}", file=sys.stderr)
    print(f"\nSources tried:", file=sys.stderr)
    any_found = False
    for name, info in result["sources"].items():
        if info.get("found"):
            any_found = True
            if "url_count" in info:
                print(f"  [OK]  {name}: {info['url_count']} URLs", file=sys.stderr)
            elif "sitemap_count" in info:
                sm_list = ", ".join(info["sitemaps"]) if info["sitemaps"] else "(no Sitemap: directives)"
                print(f"  [OK]  {name}: {sm_list}", file=sys.stderr)
        else:
            status = info.get("status", 0)
            label = f"HTTP {status}" if status else "network error"
            print(f"  [--]  {name}: {label}", file=sys.stderr)

    print(f"\nTotal URLs found (raw): {len(all_urls)}", file=sys.stderr)
    print(f"Total URLs after filter: {len(filtered_urls)}", file=sys.stderr)

    if not any_found:
        print(
            "\n!! No discovery source returned anything. Fall back to manual crawl:\n"
            f"   1. WebFetch {base}/ (or {base}/docs/) to see the nav\n"
            f"   2. Follow nav links recursively, building the URL list by hand\n",
            file=sys.stderr,
        )
        return

    if filtered_urls:
        print("\nCoverage by top-level section (sanity-check against the live nav):", file=sys.stderr)
        counts = section_counts(filtered_urls, doc_prefix)
        for section, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {section:30s} {count}", file=sys.stderr)
        print(
            "\nNext step: open the docs landing page in a browser (or WebFetch it),\n"
            "compare these section names to the visible nav. Anything missing means\n"
            "discovery was partial — extend with manual crawl before fetching.\n",
            file=sys.stderr,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("domain", help="The domain to scan, e.g. tailscale.com (no scheme)")
    parser.add_argument(
        "--doc-prefix",
        default=None,
        help="Path prefix to keep, e.g. /docs/ — drops marketing/blog URLs. Default: keep all on-domain.",
    )
    parser.add_argument("--output", type=Path, help="Write filtered URLs to this file (one per line)")
    args = parser.parse_args()

    domain = args.domain.replace("https://", "").replace("http://", "").rstrip("/")

    result = discover(domain, args.doc_prefix)

    all_urls: list[str] = []
    for info in result["sources"].values():
        if info.get("urls"):
            all_urls.extend(info["urls"])

    # Dedupe and filter
    deduped = sorted(set(all_urls))
    filtered = filter_to_doc_prefix(deduped, args.doc_prefix, domain)

    print_report(result, deduped, filtered)

    if args.output:
        args.output.write_text("\n".join(filtered) + ("\n" if filtered else ""))
        print(f"\nWrote {len(filtered)} URLs to {args.output}", file=sys.stderr)
    else:
        for url in filtered:
            print(url)

    return 0 if filtered else 1


if __name__ == "__main__":
    sys.exit(main())
