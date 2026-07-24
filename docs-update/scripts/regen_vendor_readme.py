#!/usr/bin/env python3
"""
regen_vendor_readme.py — rebuild a vendor's README.md from on-disk truth.

Reads .gitmodules at the docs repo root to find submodules belonging to the
vendor, scans the vendor directory for web-mirror domains (sibling dirs that
look like `<domain.tld>/`), and writes a fresh `<vendor>/README.md`.

The script is conservative about product names and descriptions: it preserves
existing entries from the current README when it can match by path, and only
inserts skeleton stubs for previously-unseen entries that the human must fill
in.

Usage:
    python3 regen_vendor_readme.py <vendor>
    python3 regen_vendor_readme.py grafana
    python3 regen_vendor_readme.py grafana --dry-run

The docs repo is assumed to live at ~/github.com/alpinetmpl/docs/ unless
$DOCS_REPO is set in the environment.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def docs_repo_root() -> Path:
    env = os.environ.get("DOCS_REPO")
    if env:
        return Path(env).expanduser()
    return Path.home() / "github.com" / "alpinetmpl" / "docs"


def parse_gitmodules(gitmodules_path: Path) -> list[tuple[str, str]]:
    """Return list of (path, url) for every submodule in .gitmodules."""
    if not gitmodules_path.exists():
        return []
    entries: list[tuple[str, str]] = []
    current_path: str | None = None
    current_url: str | None = None
    for line in gitmodules_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("[submodule"):
            if current_path and current_url:
                entries.append((current_path, current_url))
            current_path = None
            current_url = None
        elif line.startswith("path"):
            current_path = line.split("=", 1)[1].strip()
        elif line.startswith("url"):
            current_url = line.split("=", 1)[1].strip()
    if current_path and current_url:
        entries.append((current_path, current_url))
    return entries


def looks_like_domain(name: str) -> bool:
    """Heuristic: directory name looks like a domain if it has dots and a TLD-ish suffix."""
    if "." not in name:
        return False
    parts = name.split(".")
    if len(parts) < 2:
        return False
    # Last part: 2-6 chars (com, org, io, etc.)
    return 2 <= len(parts[-1]) <= 6 and parts[-1].isalpha()


def detect_doc_path(product_dir: Path) -> str | None:
    """Find the most likely docs subdirectory inside a product directory.

    Returns the relative path from the docs repo root, or None.
    """
    candidates = [
        "docs",
        "website/docs",
        "site/content",
        "content",
        "docs/sources",
        "docs/content",
        "src/content/docs",
        "apps/docs/content",
    ]
    for c in candidates:
        if (product_dir / c).is_dir():
            return c
    return None


def parse_existing_readme(readme_path: Path) -> dict[str, dict]:
    """Best-effort: pull existing entries from the README, keyed by repo path.

    Looks for lines like:
        - **<Name>** — `<path>/` _(submodule)_
          - Docs: `<path>/<docs>`
    Returns {path: {"name": ..., "docs_path": ..., "sub_paths": [...]}}.
    """
    if not readme_path.exists():
        return {}

    text = readme_path.read_text()
    entries: dict[str, dict] = {}

    block_re = re.compile(
        r"^- \*\*(?P<name>[^*]+)\*\*\s*[—-]\s*`(?P<path>[^`]+)`(?:\s*_\(.*?\)_)?\s*\n"
        r"(?P<body>(?:^\s+- .*\n?)*)",
        re.MULTILINE,
    )
    docs_re = re.compile(r"^\s+- Docs:\s*`([^`]+)`", re.MULTILINE)
    subpaths_re = re.compile(r"^\s+- Sub-paths(?:\s*/\s*topics)?:\s*(.+)$", re.MULTILINE)

    for m in block_re.finditer(text):
        path = m.group("path").rstrip("/")
        body = m.group("body") or ""
        docs_match = docs_re.search(body)
        sub_match = subpaths_re.search(body)
        entries[path] = {
            "name": m.group("name").strip(),
            "docs_path": docs_match.group(1) if docs_match else None,
            "sub_paths": sub_match.group(1).strip() if sub_match else None,
        }
    return entries


def render_entry(name: str, path: str, kind: str, docs_path: str | None, sub_paths: str | None) -> str:
    """Render a single product entry block."""
    kind_label = f" _({kind})_" if kind else ""
    lines = [f"- **{name}** — `{path}/`{kind_label}"]
    if docs_path:
        lines.append(f"  - Docs: `{docs_path}`")
    if sub_paths:
        lines.append(f"  - Sub-paths / topics: {sub_paths}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vendor", help="Vendor directory name (e.g. grafana, kubernetes)")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing the README")
    args = parser.parse_args()

    repo = docs_repo_root()
    vendor_dir = repo / args.vendor
    if not vendor_dir.is_dir():
        print(f"Vendor directory not found: {vendor_dir}", file=sys.stderr)
        return 1

    readme_path = vendor_dir / "README.md"
    existing = parse_existing_readme(readme_path)

    # 1. Submodules for this vendor
    all_submodules = parse_gitmodules(repo / ".gitmodules")
    vendor_submodules = [
        (path, url) for path, url in all_submodules if path.startswith(f"{args.vendor}/")
    ]

    # 2. Web-mirror directories (sibling dirs that look like domains)
    submodule_paths = {p for p, _ in vendor_submodules}
    mirror_dirs: list[str] = []
    for child in sorted(vendor_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        rel = f"{args.vendor}/{child.name}"
        if rel in submodule_paths:
            continue
        if looks_like_domain(child.name):
            mirror_dirs.append(rel)

    # 3. Render
    title = args.vendor.replace("-", " ").replace("_", " ").title()
    out_lines = [f"# {title}", "", "_Regenerated by `regen_vendor_readme.py` — review and polish before committing._", "", "## Sources", ""]

    for path, _url in sorted(vendor_submodules):
        prev = existing.get(path) or {}
        name = prev.get("name") or path.split("/", 1)[1].replace("-", " ").title()
        docs_path = prev.get("docs_path")
        if not docs_path:
            detected = detect_doc_path(repo / path)
            docs_path = f"{path}/{detected}" if detected else None
        out_lines.append(render_entry(name, path, "submodule", docs_path, prev.get("sub_paths")))
        out_lines.append("")

    for path in sorted(mirror_dirs):
        prev = existing.get(path) or {}
        domain = path.split("/", 1)[1]
        name = prev.get("name") or domain
        docs_path = prev.get("docs_path") or f"{path}/docs"
        # Only suggest docs_path if it exists
        if not (repo / docs_path).exists():
            docs_path = prev.get("docs_path") or path
        out_lines.append(render_entry(name, path, "web mirror", docs_path, prev.get("sub_paths")))
        out_lines.append("")

    output = "\n".join(out_lines).rstrip() + "\n"

    if args.dry_run:
        sys.stdout.write(output)
    else:
        readme_path.write_text(output)
        print(f"Wrote {readme_path}", file=sys.stderr)
        print(f"  submodules: {len(vendor_submodules)}, mirrors: {len(mirror_dirs)}", file=sys.stderr)
        print("Review and commit when satisfied.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
