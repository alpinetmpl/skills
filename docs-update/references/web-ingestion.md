# Web-based doc ingestion

How to mirror vendor documentation as clean markdown when no upstream git repo exists. The SKILL.md describes the discovery-first protocol and the `discover_urls.py` script that automates it; this file goes deeper on edge cases, content rules, and the existing mirror inventory.

## Table of contents

- [When to use web ingestion](#when-to-use-web-ingestion)
- [Discovery — the full picture](#discovery--the-full-picture)
- [Tool selection](#tool-selection)
- [Fetch + convert details](#fetch--convert-details)
- [Content standards](#content-standards)
- [Directory structure](#directory-structure)
- [Existing mirrors](#existing-mirrors)
- [Refreshing a mirror](#refreshing-a-mirror)

## When to use web ingestion

Decision order:

1. Public git repo with the docs? → submodule (see `submodule-management.md`).
2. Vendor publishes `llms.txt` or `llms-full.txt`? → ingest from that (often cleaner than scraping HTML).
3. Otherwise → full web ingestion.

Web ingestion is the heaviest path. Use it only when 1 and 2 are unavailable.

## Discovery — the full picture

The single biggest failure mode of past web-ingestion runs is **missing pages**: the model fetches what's visible in the nav, declares done, and the user later discovers entire sections were never imported.

**Always run the discovery script first.** It cascades through every source and gives you a coverage report:

```bash
python3 ~/.claude/skills/docs-update/scripts/discover_urls.py <domain> \
  --doc-prefix /docs/ \
  --output /tmp/<vendor>-urls.txt
```

### Sources, in cascade order

| Order | Source | What it is | When it works |
|-------|--------|------------|---------------|
| 1 | `<domain>/llms-full.txt` | Whole docs in one file | Modern AI-first vendors (rare but ideal) |
| 2 | `<domain>/llms.txt` | AI-consumable index | A few modern vendors (Anthropic, some startups) |
| 3 | `<domain>/sitemap.xml` | XML site index | Most marketing-style sites |
| 4 | `<domain>/sitemap_index.xml` | Index of sub-sitemaps | Large sites (Google, Stripe, etc.) |
| 5 | `<domain>/robots.txt` → `Sitemap:` | Points to non-standard sitemap paths | Sites that don't expose sitemaps at the default path |
| 6 | Common alternates: `/sitemap-docs.xml`, `/docs/sitemap.xml`, `/sitemap.txt` | Vendor-specific quirks | Some docs platforms (Docusaurus, GitBook) |
| 7 | Manual crawl from the docs landing page | Last resort | When 1–6 yield nothing or are clearly partial |

The script runs 1–6 automatically. You handle 7 if needed.

### The cross-check step (do not skip)

After the script reports coverage, **compare its section names to the live nav** on the docs landing page:

```bash
WebFetch https://<domain>/docs/
```

Look at the top-level sections in the nav. If the discovery report shows `[guides, api, reference]` but the live nav has `[guides, api, reference, tutorials, integrations]`, the discovery was partial. Extend with a manual crawl of the missing sections:

```bash
WebFetch https://<domain>/docs/tutorials/
WebFetch https://<domain>/docs/integrations/
# follow nav links recursively, building the URL list by hand
```

Then concatenate the manual URLs onto your discovery output before proceeding to fetch.

### When all discovery sources are empty

For very small or very legacy docs sites this happens. Manual crawl is the only option:

1. `WebFetch` the docs landing page.
2. Extract all internal links (anything starting with `/` or with the same host).
3. For each link, repeat — but bound depth to avoid getting lost in non-docs paths.
4. Build the URL list manually.

If the doc set is small (<20 pages) this is fast. If it's large, push back and ask the user whether the docs are worth importing.

## Tool selection

| Tool | Best for | Caveats |
|------|----------|---------|
| `WebFetch` | Static pages, returns markdown directly | Misses content on JS-heavy SPAs |
| `curl` + `html_to_md.py` | Bulk static-site downloads | Need `--compressed`; handle gzip + redirects |
| **Custom JSON extractor** | SPAs with embedded bootstrap JSON (Next.js, Expo Router, Remix, Nuxt) | Best quality when applicable — see `blog-ingestion.md` → "SPA-embedded JSON" |
| `agent-browser` | SPAs with no embedded JSON state | Slow, one page at a time |
| `wget -r` | Bulk static-site mirror with link following | Raw HTML output; convert separately |

### Recommended sequence

1. Try `WebFetch` on one page — does it return reasonable markdown?
2. If yes, loop `WebFetch` over the URL list one page at a time (or use `xargs -P` with `curl` for parallelism).
3. If `WebFetch` returns mostly empty content **or** the converted markdown is dominated by inline CSS/JS, the site is JS-rendered. Before reaching for `agent-browser`:
   - Grep the raw HTML for SPA bootstrap-state markers (`__NEXT_DATA__`, `__EXPO_ROUTER_LOADER_DATA__`, `__REMIX_DATA__`, `__NUXT_DATA__`, `window.__INITIAL_STATE__`, `<script type="application/ld+json">`).
   - If a marker is present, the article body is almost certainly inside that JSON blob in clean structured form. Write a small extractor that parses the JSON and renders directly to markdown — quality and speed both beat `agent-browser`. See `blog-ingestion.md` for the recipe and known platforms.
4. Only fall through to `agent-browser` (slow, headless Chrome) when both static HTML and bootstrap JSON are missing the content.

## Fetch + convert details

### `WebFetch` loop (one page at a time)

```bash
while read url; do
  rel=$(echo "$url" | sed "s|https://<domain>||;s|^/||")
  out="~/github.com/alpinetmpl/docs/<vendor>/<domain>/${rel:-index}.md"
  mkdir -p "$(dirname "$out")"
  WebFetch "$url" > "$out"
done < /tmp/<vendor>-urls.txt
```

### Bulk `curl` + batch convert (faster for static sites)

```bash
mkdir -p /tmp/<vendor>-html
xargs -P 4 -I {} sh -c \
  'curl -sL "$1" -o "/tmp/<vendor>-html/$(echo $1 | sed s\|https://\|\|\;s\|/\|_\|g).html"' _ {} \
  < /tmp/<vendor>-urls.txt

python3 ~/.claude/skills/docs-update/scripts/html_to_md.py \
  --input /tmp/<vendor>-html \
  --output ~/github.com/alpinetmpl/docs/<vendor>/<domain>/ \
  --base-url https://<domain>
```

The converter strips chrome (nav/footer/scripts/cookie banners), preserves headings, code blocks (with language tags), tables, lists, image alt text, and rewrites internal links to relative paths.

## Content standards

### Keep

- Headings (h1–h6 → `#`–`######`)
- Paragraphs and prose
- Code blocks with language tags (```python, ```bash, ```yaml, ...)
- Tables (pipe tables)
- Ordered and unordered lists
- Image references with alt text (optionally download images to `assets/`)
- Internal links — rewrite to relative paths so they work within the local mirror
- Blockquotes and callouts (`>`)

### Strip

- Navigation, sidebars, top-bars, menus
- Footers and copyright
- Cookie banners and consent dialogs
- `<script>`, `<style>`, inline JS
- Ads, tracking pixels, analytics tags
- Breadcrumbs
- "Edit this page on GitHub" links
- Search input widgets
- Social sharing buttons
- Version pickers (encode the version in the directory path instead)

### Quality checks before commit

1. Headings form a logical hierarchy (no skipped levels — `#` then `###` is a red flag).
2. Code blocks have language tags.
3. No absolute self-domain URLs that should be relative.
4. No HTML artifacts (`<div>`, `<span>` shouldn't appear in markdown output).
5. No empty or near-empty files (pages that were 100% nav).
6. Spot-check 3-5 random pages and compare to the live site.

## Directory structure

Web-ingested content lives at `<vendor>/<domain>/`. Subdirectories mirror the URL path.

```text
<vendor>/<domain>/
  <url-path-segments>/
    <page>.md
```

### Examples

| Source URL | Local path |
|-----------|------------|
| `https://tailscale.com/docs/` | `tailscale/tailscale.com/docs/index.md` |
| `https://tailscale.com/docs/features/kubernetes-operator/` | `tailscale/tailscale.com/docs/features/kubernetes-operator.md` |
| `https://docs.vendor.com/frontend/auth` | `vendor/docs.vendor.com/frontend/auth.md` |
| `https://docs.oracle.com/en-us/iaas/Content/Compute/home.htm` | `oracle/docs.oracle.com/en-us/iaas/Content/Compute/home.md` |

### Conventions

- `.md` extension for everything (convert `.html`, `.htm`).
- A trailing `/` URL becomes `<parent>.md` when there are no sibling pages, or `<parent>/index.md` when the directory has children. The `html_to_md.py` script handles this automatically.
- Preserve URL path casing exactly. If the URL uses `Content/Compute/`, keep that casing locally.
- For mirrors with 100+ pages, generate a `TABLE_OF_CONTENTS.md` at the mirror root. See `oracle/docs.oracle.com/` for an existing example.

## Existing mirrors

Snapshot of web-ingested mirrors currently in the repo:

| Directory | Source | Approach | Notes |
|-----------|--------|----------|-------|
| `anthropic/platform.claude.com/` | platform.claude.com | Manual download | Claude Agent SDK docs |
| `grafana/grafana.com/` | grafana.com | Selective download | Kubernetes Monitoring docs subset only |
| `martinbaillie/martin.baillie.id/` | martin.baillie.id | Manual download | Blog posts under `wrote/` |
| `oracle/docs.oracle.com/` | docs.oracle.com | Bulk + convert | ~840 pages, has `TABLE_OF_CONTENTS.md` |
| `oracle/oracle.com/` | oracle.com | Selective download | OCI Compute pricing pages |
| `tailscale/tailscale.com/` | tailscale.com | Full site mirror | Includes docs, kb, blog |
| `cloudflare/developers.cloudflare.com/` | developers.cloudflare.com | Bulk + convert | ~5,900 pages |

This list will drift — verify against the actual repo contents before treating it as authoritative.

## Refreshing a mirror

### Single page

1. Re-fetch the page with `WebFetch`.
2. Diff against the existing local file: `diff <local-file> /tmp/new.md`.
3. If changes, replace and commit:
   ```bash
   cp /tmp/new.md <local-file>
   git add <local-file>
   git commit -m "Update <vendor> docs: <page>"
   git push origin main
   ```

### Full mirror refresh

1. Re-run the discovery script. If new URLs appear, the doc set has grown — note these for fresh ingestion.
2. Re-run the fetch + convert flow into a temp directory.
3. Diff the temp tree against the live tree:
   ```bash
   diff -r ~/github.com/alpinetmpl/docs/<vendor>/<domain>/ /tmp/<vendor>-fresh/
   ```
4. If acceptable, sync changes:
   ```bash
   rsync -a --delete /tmp/<vendor>-fresh/ ~/github.com/alpinetmpl/docs/<vendor>/<domain>/
   git add <vendor>/<domain>/
   git commit -m "Refresh <vendor>/<domain> mirror (<N> pages)"
   git push origin main
   ```

Use `--delete` only if the discovery covered the same scope as before. If discovery was narrower this time, skip `--delete` to avoid blowing away pages that still exist upstream but weren't in the latest URL list.
