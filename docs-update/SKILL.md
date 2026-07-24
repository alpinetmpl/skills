---
name: docs-update
description: >-
  Use this skill when the user wants to LAND doc-worthy content in the
  local docs repo at `~/github.com/alpinetmpl/docs/` — add or refresh vendor
  documentation (submodule clone or web mirror), or ingest long-form
  content like engineering blogs, vendor blogs, and curated
  strategy/essay posts (Anthropic engineering, Cloudflare/Stripe/Grafana
  engineering blogs, Sequoia/a16z/YC articles, Simon Willison posts, fly.io
  blog, etc.). Covers ingestion via git submodule (preferred when a public
  source repo exists), full web mirror, single-article fetch, and
  RSS/Atom-driven blog mirrors. Also covers the investigative "do they
  even have a docs/blog repo?" step that precedes ingestion, and removal
  of sources no longer used. Always ends by committing and pushing. Reach
  for this on intents like "add docs for X", "save this article",
  "ingest/scrape Y's blog", "pull/refresh latest X posts", "update
  submodules", "remove the X submodule", or any request whose end-state is
  the docs repo growing, shrinking, or moving forward. Do NOT use for
  reading, searching, or quoting existing content (that's `docs-query`).
---

# docs-update

Bring new doc-worthy content into `~/github.com/alpinetmpl/docs/`, or refresh existing content to the latest upstream version. Finishes by committing and pushing to `origin/main`.

**Read [references/repo-layout.md](references/repo-layout.md) first** — it's the shared substrate for the docs skills (repo layout, vendor/domain naming, the two-tier README index, and the blog frontmatter contract), owned in one place so this skill and the sibling **docs-query** can't drift on it. Everything you write must respect that layout; the paths below only add the ingestion-specific mechanics.

This skill ingests both flavors of content the repo holds — **reference documentation** (versioned vendor docs, submodule or web mirror) and **doc-worthy long-form** (blogs/articles, always web-mirrored, often a single post). They share one vendor/domain layout; what differs is *discovery* (sitemaps vs. RSS/Atom) and *metadata* (long-form posts carry the frontmatter contract, evergreen reference pages don't). See Path 3 for the blog-specific bits. A sibling skill, **docs-query**, handles reading what this skill imports — don't put query logic here.

## Repo layout (the contract every change must respect)

The layout — vendor/domain naming, submodule vs. web mirror, the two-tier README index — is in [references/repo-layout.md](references/repo-layout.md). The one obligation that's specifically *yours* as the writer: **keep both READMEs current.** The root `README.md` gets an entry per vendor brand; each `<vendor>/README.md` lists every product with its exact path. Drift between the READMEs and what's on disk is the most common failure mode of past changes — you touch these on every ingestion (see "Update READMEs").

## Workflow at a glance

1. Identify the vendor + product (or blog/article) the user wants.
2. **Look upstream first — even if the user says there's no repo.** Always run `gh search repos "<vendor> docs"` and `gh repo list <vendor-org>` before going to web ingestion. Users frequently misremember or assume; a 5-second check beats hours of scraping. Also check whether the URL they gave is the *right* domain — a quick visit to the homepage catches typos and parked domains (e.g. `.co` vs `.com`).
3. Pick the right path:
   - **Path 1 — submodule** when a healthy public docs repo exists.
   - **Path 2 — full web mirror** when the docs only live on a website.
   - **Path 3 — blog/article** when the user wants long-form posts (one curated article, or a whole engineering blog). Mechanically a web mirror, but discovery uses RSS/Atom and every post carries a publish date.
4. Update the vendor README (and root README if this is a brand-new vendor brand).
5. Commit and push. Stage only the files you touched.

## Path 1: Add as git submodule (preferred)

Use whenever the vendor's docs are maintained in a public git repo. Submodules are cheaper to refresh and stay closer to source-of-truth than a scraped mirror.

### Discover the upstream repo

```bash
# GitHub search by org
gh repo list <ORG> --limit 200 --json name,description,isArchived
# Or full-text search if you don't know the org
gh search repos "<product> docs" --limit 20

# Health check the candidate repo before adopting
gh repo view <ORG>/<REPO> --json isArchived,pushedAt,visibility,description
```

Requirements before adoption:
- `isArchived: false`
- `pushedAt` within the last 6 months
- `visibility: PUBLIC`

If not on GitHub, try GitLab (`glab repo view`) or Bitbucket. Same health criteria — recently pushed, public, not archived.

### Add it

```bash
cd ~/github.com/alpinetmpl/docs
git submodule add https://github.com/<ORG>/<REPO>.git <vendor>/<repo>
```

Naming: local path uses lowercase, even if the upstream org has uppercase (e.g. `OT-CONTAINER-KIT` → `ot-container-kit/`). The URL in `.gitmodules` keeps original casing.

Then find the doc content path inside the repo (commonly `docs/`, `website/`, `site/content/`, `content/`). Note it down for the README entry.

For very large repos (>500MB) use `--depth 1`:

```bash
git submodule add --depth 1 https://github.com/<ORG>/<REPO>.git <vendor>/<repo>
```

### Refresh existing submodules

Single submodule:
```bash
cd ~/github.com/alpinetmpl/docs/<vendor>/<repo>
git fetch origin
git checkout origin/main   # or origin/master — whichever is the default
cd ~/github.com/alpinetmpl/docs
git add <vendor>/<repo>
```

All submodules at once. This is more delicate than it looks because the docs repo frequently has pre-existing dirty submodules (other devs' WIP, mixed pins, etc.) that you must NOT stage as part of your refresh.

```bash
cd ~/github.com/alpinetmpl/docs

# 1. Snapshot current submodule SHAs BEFORE updating. This is the key step —
#    we need to know which submodules were already "off pin" before we did
#    anything, so we can ignore those.
git submodule status > /tmp/submodules-before.txt

# 2. Fetch + advance every submodule to its tracked branch's HEAD.
#    Do NOT pass --recursive — nested submodules in upstream repos (e.g.
#    grafana/beyla/.obi-src) frequently have broken refs that abort the
#    whole run. We only care about top-level pointers here.
git submodule update --remote

# 3. Diff before/after, keep only submodules that ACTUALLY moved due to
#    this run. `git submodule status` prints `<sha> <path>` (with leading
#    space/`+`/`-`). Strip the prefix, compare; report paths whose SHA
#    changed.
git submodule status > /tmp/submodules-after.txt
paths_to_stage=$(diff /tmp/submodules-before.txt /tmp/submodules-after.txt \
  | awk '/^[<>]/ {print $3}' | sort -u)

# Why this works: a pre-existing dirty submodule will have the SAME pre/post
# `+`-prefixed line (its dirtiness didn't change), so it won't appear in the
# diff. A genuinely-advanced submodule changes SHA between snapshots, so it
# shows up exactly once on each side of the diff.
#
# DO NOT use `git submodule status | awk '/^\+/'` or `git add -u` —
# both will sweep in pre-existing dirty submodules and pollute the commit.

# 4. Review what moved, then stage by path.
git diff --submodule
echo "$paths_to_stage" | xargs -r git add --
```

If a single submodule's fetch fails (stale upstream refs, broken nested submodule, etc.) the bulk run prints an error and continues for the others. Recover individually with `git remote prune origin && git fetch && git checkout origin/<branch>` inside that submodule, then re-stage just it.

For deeper detail (pinning to a tag, removal, troubleshooting) see `references/submodule-management.md`.

## Path 2: Web-ingested markdown mirror

Use only when no upstream git repo exists.

### CRITICAL: discover EVERY URL before fetching anything

The dominant failure mode of past web ingestion runs has been **missing pages** — the model fetches what it can see in the nav, then declares done while half the docs are absent. Build a complete URL inventory FIRST, fetch SECOND.

Use the bundled discovery script — it runs the full cascade and reports coverage:

```bash
python3 ~/.claude/skills/docs-update/scripts/discover_urls.py <DOMAIN> \
  --doc-prefix /docs/ \
  --output /tmp/<vendor>-urls.txt
```

The script tries, in order:
1. `https://<DOMAIN>/llms-full.txt` — full docs in one file (rare but ideal)
2. `https://<DOMAIN>/llms.txt` — AI-consumable index
3. `https://<DOMAIN>/sitemap.xml` and `sitemap_index.xml`
4. `https://<DOMAIN>/robots.txt` — extract `Sitemap:` directives (sometimes point to non-standard sitemap paths)
5. Common alternates: `/sitemap-docs.xml`, `/docs/sitemap.xml`, `/sitemap.txt`

It outputs a deduped URL list filtered by `--doc-prefix`, plus a coverage report (count per top-level section) that you MUST sanity-check against the live nav. If the visible nav has sections the URL list is missing, the discovery was partial — fall back to manual crawl (`WebFetch` the docs landing page, follow nav links) and merge results.

See `references/web-ingestion.md` for the full discovery decision tree, including what to do when even manual crawl is needed.

### Fetch + convert

For static pages, `WebFetch` returns markdown directly — that's the fast path. For HTML-rendered pages, fetch the HTML and convert:

```bash
# Bulk fetch HTML for the URL list
mkdir -p /tmp/<vendor>-html
xargs -P 4 -I {} sh -c 'curl -sL --compressed "$1" -o "/tmp/<vendor>-html/$(echo $1 | sed "s|https://||;s|/|_|g").html"' _ {} < /tmp/<vendor>-urls.txt

# Convert to markdown, mirroring URL paths to file paths
python3 ~/.claude/skills/docs-update/scripts/html_to_md.py \
  --input /tmp/<vendor>-html \
  --output ~/github.com/alpinetmpl/docs/<vendor>/<domain>/ \
  --base-url https://<DOMAIN>
```

The converter strips nav/footer/scripts/cookie banners, preserves headings, code blocks (with language tags), tables, and lists. Internal links are rewritten to relative paths.

**Before you markdownify: check whether the site is an SPA whose content lives in embedded bootstrap JSON.** Many modern blogs and docs sites (anything built on Next.js, Remix, Nuxt, Expo Router, SvelteKit, etc.) ship a near-empty body in their static HTML and hydrate client-side. Running `html_to_md.py` on their raw HTML produces CSS/JS soup — the title shows up as a single line followed by 400+ lines of inline styles and JS, with the actual prose unreachable. Before fetching at scale, sample one page and grep for known bootstrap-state markers:

```bash
# After fetching a sample page:
grep -oE '__NEXT_DATA__|__EXPO_ROUTER_LOADER_DATA__|__REMIX_DATA__|__NUXT_DATA__|window\.__INITIAL_STATE__|"@context":"https://schema.org"' /tmp/<vendor>-html/sample.html | sort -u
```

If a marker shows up, the article body is almost certainly inside that JSON blob in a clean structured form (Sanity Portable Text, Contentful Rich Text, Markdown source, etc.) — write a small extractor that parses the JSON and renders content directly to markdown. That path beats markdownify by miles for SPAs. See `references/blog-ingestion.md` → "SPA-embedded JSON (Expo Router, Next.js, Remix, Nuxt)" for the full recipe, marker list, and a working precedent (Expo blog, 190 posts, 0 failures).

### Directory structure

URL → file path is a direct mirror:

| URL | File path |
|-----|-----------|
| `https://docs.vendor.com/frontend/auth` | `vendor/docs.vendor.com/frontend/auth.md` |
| `https://docs.vendor.com/frontend/auth/index.html` | `vendor/docs.vendor.com/frontend/auth.md` (if no siblings) or `frontend/auth/index.md` (if it has children) |
| `https://tailscale.com/docs/features/kubernetes-operator/` | `tailscale/tailscale.com/docs/features/kubernetes-operator.md` |

Preserve URL path casing. Use `.md` for everything.

For mirrors over 100 pages, generate a `TABLE_OF_CONTENTS.md` at the mirror root (see `oracle/docs.oracle.com/` for an example).

## Path 3: Blog & article ingestion

For engineering blogs, vendor blogs, and curated essay/strategy posts. Mechanically this is still a web mirror — content lives at `<vendor>/<domain>/<url-path>.md` — but the discovery shortcut is different (RSS/Atom instead of sitemap.xml), the unit of work is often a single article rather than a whole site, and **every post needs a publish date in its frontmatter** so `docs-query` can tell the user "this advice is from 2024-06, still relevant?" downstream.

### Pick the sub-mode

| User intent | Sub-mode | What to do |
|-------------|----------|------------|
| "Save this Sequoia AGI article" / "ingest this one post" | **Single article** | Fetch one URL, save to the matching path with frontmatter. |
| "Ingest Anthropic's engineering blog" / "save Cloudflare's blog" | **Whole blog** | Use RSS/Atom or sitemap to discover all posts, fetch and convert. |
| "Pull the latest posts from <vendor>'s blog" | **Refresh** | Re-run discovery, diff against existing mirror, fetch only new posts. |

### Discover blog post URLs

RSS/Atom is the gold-standard URL inventory for blogs — same role sitemap.xml plays for docs sites. Try these in order, then fall back to the existing discovery cascade:

| Order | Path | Format | Common on |
|-------|------|--------|-----------|
| 1 | `/feed`, `/rss`, `/rss.xml`, `/atom.xml` | RSS/Atom XML | WordPress, Substack, Ghost |
| 2 | `/feed.xml`, `/index.xml` | Atom/RSS XML | Hugo, Jekyll, Gatsby (common static generators) |
| 3 | `/blog/feed/`, `/engineering/rss.xml` | Scoped feeds | Sites that mix blog with other content |
| 4 | Fall through to `discover_urls.py` cascade | sitemap.xml etc. | Custom blogs without RSS |
| 5 | Manual: fetch the blog index page and walk pagination | — | Last resort |

Most modern engineering blogs expose an RSS or Atom feed. A 5-second `curl -sIL <domain>/feed` (or browser visit to `View Source` on the blog index) will usually reveal it. **Always try RSS/Atom before falling back to the sitemap cascade** — feeds are cleaner (they list only posts, not category/tag pages) and they carry the publish date inline.

`WebFetch <feed-url>` returns the parsed feed; extract the `<link>` elements (RSS) or `<entry><link href=...>` (Atom) into a URL list.

### Single-article ingestion (fast path)

```bash
# 1. Fetch the article (WebFetch returns markdown for most modern blogs)
WebFetch <article-url>

# 2. Compute the local path: <vendor>/<domain>/<url-path>.md
#    https://sequoiacap.com/article/2026-this-is-agi/
#    → sequoiacap/sequoiacap.com/article/2026-this-is-agi.md

# 3. Save with frontmatter (see "Article frontmatter" below)
# 4. Update the vendor README; commit; push.
```

### Whole-blog ingestion

```bash
# 1. Try RSS/Atom first
curl -sL https://<domain>/feed > /tmp/<vendor>-feed.xml
# Extract post URLs; sanity-check count (a real engineering blog has dozens)

# 2. If RSS only returns the latest N posts (Substack defaults to 20, some
#    feeds cap at 50), supplement with the sitemap cascade for full coverage
python3 ~/.claude/skills/docs-update/scripts/discover_urls.py <domain> \
  --doc-prefix /blog/ \
  --output /tmp/<vendor>-blog-urls.txt

# 3. Fetch + convert as in Path 2
# 4. Add frontmatter to every file (see below) before committing
```

### Article frontmatter (required for blog content)

Every ingested article gets the YAML frontmatter block from the frontmatter contract in [references/repo-layout.md](references/repo-layout.md) — that's the exact shape `docs-query` reads back, so match its keys. This skill owns *how to populate* each field:

- **title** — from the page `<title>` or `<h1>`.
- **author** — byline if available; the publication name otherwise ("Anthropic engineering", "Sequoia Capital").
- **published** — pull from page metadata (`<meta property="article:published_time">`, RSS `<pubDate>`, OpenGraph). If only month/year is visible, use the 1st (`2024-06-01`). **Never fabricate one** — omit it if you truly can't find it.
- **source_url** — canonical URL of the article.
- **ingested** — today's date, when *we* pulled it.

Omit any field you can't find rather than guessing — `docs-query` treats a missing field as "unknown", not "false".

### Refresh an existing blog mirror

```bash
# 1. Re-fetch the feed; build the current set of post URLs
# 2. List the URLs already mirrored locally (search the existing files'
#    source_url frontmatter, OR derive from the file paths)
ls ~/github.com/alpinetmpl/docs/<vendor>/<domain>/<blog-path>/ | sed 's/\.md$//'

# 3. Diff: fetch only posts in the feed that are NOT already on disk
# 4. For each new post, fetch + convert + add frontmatter
# 5. Commit with message "Refresh <vendor>/<domain>: <N> new posts"
```

**Important:** when refreshing, do NOT re-fetch existing posts — they're snapshots, not evolving documents. Re-fetching costs nothing but creates spurious diffs when the upstream site re-renders boilerplate. Only fetch new URLs.

See `references/blog-ingestion.md` for the deep dive — RSS parsing details, paginated index crawling, handling Substack/Medium/Ghost specifically, and how to handle blog content that lives inside an otherwise-doc-y site (e.g. `tailscale.com/blog`).

## Update READMEs

Two updates, every time:

### Vendor README (`<vendor>/README.md`) — always

Add or update a per-product entry:

```markdown
- **<Product Name>** — `<vendor>/<repo-or-domain>/` _(submodule)_   <!-- or _(web mirror)_, _(blog mirror)_, _(article)_ -->
  - Docs: `<vendor>/<repo-or-domain>/<doc-content-path>`
  - Sub-paths / topics: ...
```

For blog content the entry shape is slightly different — surface the publication name and what kind of posts live there:

```markdown
- **Anthropic Engineering blog** — `anthropic/www.anthropic.com/engineering/` _(blog mirror)_
  - Articles: AI engineering, agent architectures, prompt caching, multi-agent systems
  - Discovery: RSS feed at https://www.anthropic.com/engineering/rss.xml (verify path)
```

For single curated articles, list them as their own entry rather than glomming them into a sibling entry:

```markdown
- **Sequoia: "This is AGI" (2026)** — `sequoiacap/sequoiacap.com/article/2026-this-is-agi.md` _(article)_
```

If the vendor folder is brand new (no `README.md` yet), create one. Copy the shape of an existing vendor README like `grafana/README.md` or `argoproj/README.md`.

You can also use the bundled regenerator to rebuild a vendor README from disk truth (catches drift):

```bash
python3 ~/.claude/skills/docs-update/scripts/regen_vendor_readme.py <vendor>
```

This walks the vendor directory, reads `.gitmodules` for submodule entries, detects web-mirror directories, and rewrites `<vendor>/README.md`. Review the diff before committing — the script is conservative about descriptions but may need product-name tweaks.

### Root README — only for brand-new vendor brands

Add a TOC entry in alphabetical order:

```markdown
## <Vendor Brand>
<one-line description>
- [<Product Name>](<vendor>/README.md)
```

For a new product under an existing vendor brand, the root README stays unchanged — only the vendor README gets touched.

## Commit + push

Always commit and push when the workflow succeeds. The docs repo is shared across machines; uncommitted local state is dead weight.

```bash
cd ~/github.com/alpinetmpl/docs

# Stage ONLY what you touched. Never git add -A / git add . —
# the repo frequently has unrelated dirty submodules.
git add .gitmodules <vendor>/<repo-or-domain> <vendor>/README.md README.md

git commit -m "Add <vendor>/<repo>: <one-line description>"
# Or: "Update <vendor>/<repo> to latest upstream"
# Or: "Ingest <vendor>/<domain>: <N> pages"

git push origin main
```

If `git push` is rejected because someone else pushed in the meantime, `git pull --rebase origin main` and push again. Do not force-push.

## Rules

1. **Submodule beats web mirror — always check upstream first, even when the user claims none exists.** A quick `gh search repos` / `gh repo list <org>` is mandatory. Also sanity-check the user's URL: typos, parked domains, and the wrong TLD (`.co` vs `.com`) are common. Web ingestion is the fallback, not the default. For pure blog content this check is still worth doing (e.g. Cloudflare's blog source lives in `cloudflare/cloudflare-docs`), but failure is expected and falling through to Path 3 is fine.
2. **Discover everything before fetching anything (web/blog ingestion).** The discovery cascade is non-negotiable. For blogs, try RSS/Atom first, then sitemap, then manual crawl. Cross-check URL coverage against the live blog index before declaring discovery complete.
3. **Blog posts carry a publish-date frontmatter — every time.** The `published` field is what makes `docs-query` able to tell users "this article is from 2024, here's the date." Omit fields you can't find, but never *fabricate* a publish date.
4. **Both READMEs stay in sync.** Vendor README always; root README only for new vendor brands. Use `regen_vendor_readme.py` to catch drift.
5. **Naming follows convention.** Submodules: `<vendor>/<repo>/` (lowercase path, original-case URL). Web mirrors and blog mirrors: `<vendor>/<domain>/...`. Single curated articles also live at `<vendor>/<domain>/<url-path>.md` — pick the most natural "vendor" name (publication name lowercased, e.g. `sequoiacap` for Sequoia).
6. **Repo health gates submodule adoption.** Public, not archived, pushed within 6 months.
7. **Selective `git add` only.** Never `git add -A` or `git add .` — the repo often has unrelated dirty submodules. For bulk refresh, both `git add -u` and `git submodule status | awk '/^\+/'` are unsafe (they sweep in pre-existing dirty submodules). Use the before/after snapshot-diff approach shown in the bulk-refresh section.
8. **Never modify submodule contents.** Submodules are read-only clones. Refresh by updating the pointer, never by editing files inside.
9. **Web-ingested markdown stays clean.** Strip nav/footer/scripts/cookie chrome. Keep headings, prose, code blocks (with language tags), tables, lists, image alt text, and links (rewritten to relative). For blog content also strip "Subscribe to newsletter", "Share this post", related-posts widgets, and comment threads.
10. **Don't re-fetch existing blog posts on refresh.** Blog posts are point-in-time snapshots, not evolving documents. Re-fetching produces spurious diffs from boilerplate re-rendering. Refresh = fetch only posts not yet on disk.
11. **Auto commit + push closes every change.** No "stop and let the user review" — the user opted into autonomous commit/push for this skill. If push fails, rebase and retry once; surface the conflict if it persists.
12. **Removal needs explicit ask.** Never delete a vendor directory, submodule, or blog mirror without the user explicitly requesting removal.

## References

- `references/repo-layout.md` — shared docs-family substrate: repo layout, vendor/domain naming, the two-tier README index, and the blog frontmatter contract. Read it first; docs-query reads the same file, so what you write here stays exactly what it expects to find.
- `references/submodule-management.md` — submodule add/update/pin/remove, `.gitmodules` format, troubleshooting
- `references/web-ingestion.md` — full discovery decision tree, fetch+convert details, content-cleaning rules, existing mirror inventory
- `references/blog-ingestion.md` — RSS/Atom parsing, single-article fast path, platform-specific quirks (Substack/Medium/Ghost/Hugo), frontmatter rules, refresh-without-re-fetch protocol

## Scripts

- `scripts/discover_urls.py` — cascade discovery (llms.txt, sitemap.xml, robots.txt, alternates) → deduped URL list + coverage report
- `scripts/html_to_md.py` — batch HTML→markdown conversion that mirrors URL paths into the file tree
- `scripts/regen_vendor_readme.py` — rebuild a vendor's `README.md` from on-disk truth (submodules + mirror dirs)
