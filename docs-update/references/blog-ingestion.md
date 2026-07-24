# Blog & article ingestion

How to bring engineering blogs, vendor blogs, and curated essay/strategy posts into `~/github.com/alpinetmpl/docs/`. The SKILL.md covers the decision flow and the article-frontmatter rule; this file goes deeper on RSS/Atom parsing, platform-specific quirks, and refresh semantics.

## Table of contents

- [When this path applies](#when-this-path-applies)
- [Pick a "vendor" name for non-vendor sources](#pick-a-vendor-name-for-non-vendor-sources)
- [RSS/Atom discovery in detail](#rssatom-discovery-in-detail)
- [Single-article fast path](#single-article-fast-path)
- [Whole-blog ingestion](#whole-blog-ingestion)
- [Article frontmatter (the contract)](#article-frontmatter-the-contract)
- [Platform-specific quirks](#platform-specific-quirks)
- [Refreshing without re-fetching](#refreshing-without-re-fetching)
- [Suggested initial sources](#suggested-initial-sources)

## When this path applies

Use the blog/article path (Path 3 in SKILL.md) when the content is:

- Time-stamped and author-attributed (a post, not a docs page).
- Authoritative or curated — vendor engineering blogs, recognized publications, individual thought leaders the team trusts.
- Likely to be referenced by date or topic later (e.g. "what did Anthropic engineering say about prompt caching in 2024?").

Use Path 2 (full web mirror) instead when:

- The content is evergreen documentation that happens to sit on a marketing site (no per-page publish date in any meaningful sense).
- You want everything on a domain, not just the blog section.

The line gets fuzzy on sites like `tailscale.com` that have docs + blog + KB on the same domain. In that case run Path 2 over `/docs/` and Path 3 over `/blog/`, then commit both — they're sibling paths under the same vendor/domain folder.

## Pick a "vendor" name for non-vendor sources

The repo layout requires a top-level vendor folder. For obvious vendors (Anthropic, Cloudflare, Grafana) the existing folder applies. For non-vendor sources, choose a name that's stable, lowercase, and unambiguous:

| Source | Suggested vendor folder | Rationale |
|--------|------------------------|-----------|
| Sequoia Capital | `sequoiacap/` | Matches their primary domain stem |
| Andreessen Horowitz | `a16z/` | Common short form, matches `a16z.com` |
| Y Combinator | `ycombinator/` | Matches `ycombinator.com`; do not use `yc` (ambiguous) |
| Paul Graham essays | `paulgraham/` | Personal site, author-named is clearest |
| Simon Willison | `simonwillison/` | Same |
| fly.io blog | `flyio/` (or extend the existing if present) | Strip the dot for shell-friendliness |
| Dan Luu | `danluu/` | Personal site |

When in doubt: lowercase, alphanumeric only (drop dots/dashes), favor the domain stem over a brand name (more stable over time).

## RSS/Atom discovery in detail

RSS and Atom feeds are XML lists of recent posts. They typically include `<title>`, `<link>`, `<pubDate>` (or `<published>` for Atom), and sometimes the full content inline.

### Common feed paths

Try in this order:

```bash
# WordPress (Stripe, Cloudflare on some sub-blogs, many vendor blogs)
curl -sIL https://<domain>/feed
curl -sIL https://<domain>/feed/

# Substack
curl -sIL https://<domain>/feed
# (substacks are at <name>.substack.com/feed)

# Ghost
curl -sIL https://<domain>/rss/
curl -sIL https://<domain>/blog/rss/

# Hugo / Jekyll / Gatsby (static site generators)
curl -sIL https://<domain>/feed.xml
curl -sIL https://<domain>/index.xml
curl -sIL https://<domain>/atom.xml
curl -sIL https://<domain>/rss.xml

# Scoped feeds for sites with mixed content
curl -sIL https://<domain>/blog/feed
curl -sIL https://<domain>/engineering/rss.xml
curl -sIL https://<domain>/category/engineering/feed
```

A 200 response with `Content-Type: application/rss+xml`, `application/atom+xml`, or `application/xml` confirms a feed. A redirect (301/302) usually points to the canonical feed path — follow it.

### Look in the HTML head if path probing fails

Every blog SHOULD advertise its feed via `<link rel="alternate" type="application/rss+xml" href="...">` in the homepage `<head>`. Fetch the homepage and grep:

```bash
WebFetch https://<domain>/  # or grep the raw HTML
grep -Eo 'rel="alternate"[^>]*type="application/(rss|atom)\+xml"[^>]*' /tmp/<domain>.html
```

### Extract URLs from the feed

Once you have the feed XML, pull the post URLs. Quick approaches:

```bash
# Atom
grep -oE '<link[^>]*href="[^"]+"' /tmp/feed.xml | grep -v 'rel="self"' | sed 's/.*href="//;s/".*//'

# RSS
grep -oE '<link>[^<]+</link>' /tmp/feed.xml | sed 's|<link>||;s|</link>||'
```

For more robust parsing (handling CDATA, namespaces), use Python:

```python
import feedparser
feed = feedparser.parse("https://<domain>/feed")
for entry in feed.entries:
    print(entry.link, entry.published)
```

### Feed truncation

Most feeds cap at 10–50 recent posts. If the blog has more than that, the feed alone won't give full coverage. Two options:

1. **Sitemap supplement** — `discover_urls.py <domain> --doc-prefix /blog/` to enumerate all `/blog/<slug>` URLs from sitemap.xml.
2. **Paginated index walk** — fetch `<domain>/blog/page/2/`, `page/3/`, etc., extracting post links from each.

Combine results, dedupe, and proceed.

## Single-article fast path

When the user says "save this article" or "ingest this one post" and gives a URL:

```bash
# 1. Pick the path
url="https://sequoiacap.com/article/2026-this-is-agi/"
domain="sequoiacap.com"
vendor="sequoiacap"
rel_path=$(echo "$url" | sed "s|https://${domain}||;s|/$||")
local_path="$HOME/github.com/alpinetmpl/docs/${vendor}/${domain}${rel_path}.md"
mkdir -p "$(dirname "$local_path")"

# 2. Fetch
WebFetch "$url"  # returns markdown for most modern blogs
# (save the output to /tmp/article.md, then process)

# 3. Extract metadata for the frontmatter
#    title    → <title> or first h1
#    author   → <meta name="author"> or visible byline
#    published → <meta property="article:published_time">, OG, JSON-LD, or in-page date
#    These are sometimes only in the raw HTML, not in WebFetch's markdown rendering.
#    If WebFetch doesn't surface them, `curl -sL "$url" | grep -E '(author|published_time|article:)'`

# 4. Compose the file with frontmatter (see "Article frontmatter" below)
# 5. Update <vendor>/README.md to list the article
# 6. Commit, push.
```

## Whole-blog ingestion

```bash
# Setup
domain="www.anthropic.com"
vendor="anthropic"
blog_prefix="/engineering"   # the scoped section under the domain
out_dir="$HOME/github.com/alpinetmpl/docs/${vendor}/${domain}${blog_prefix}"
mkdir -p "$out_dir"

# 1. Discover post URLs (feed first, sitemap fallback)
WebFetch "https://${domain}${blog_prefix}/rss.xml" > /tmp/${vendor}-feed.xml
# Extract <link>s; if feed is truncated, supplement:
python3 ~/.claude/skills/docs-update/scripts/discover_urls.py "${domain}" \
  --doc-prefix "${blog_prefix}/" \
  --output /tmp/${vendor}-blog-urls.txt
# Merge feed URLs + sitemap URLs, dedupe.

# 2. Fetch + convert each post
while read url; do
  rel=$(echo "$url" | sed "s|https://${domain}||;s|^/||;s|/$||")
  out="${out_dir}/$(basename "$rel").md"
  WebFetch "$url" > /tmp/post.md
  # Extract metadata from the raw HTML if WebFetch's markdown loses it:
  curl -sL "$url" > /tmp/post.html
  title=$(grep -oP '(?<=<title>)[^<]+' /tmp/post.html | head -1)
  published=$(grep -oP 'property="article:published_time" content="\K[^"]+' /tmp/post.html | head -1 | cut -c1-10)
  author=$(grep -oP '(?<=<meta name="author" content=")[^"]+' /tmp/post.html | head -1)

  # Write the file with frontmatter prepended
  {
    echo "---"
    echo "title: \"$title\""
    [ -n "$author" ] && echo "author: \"$author\""
    [ -n "$published" ] && echo "published: \"$published\""
    echo "source_url: \"$url\""
    echo "ingested: \"$(date +%Y-%m-%d)\""
    echo "---"
    echo ""
    cat /tmp/post.md
  } > "$out"
done < /tmp/${vendor}-blog-urls.txt

# 3. Update <vendor>/README.md
# 4. Commit, push.
```

For large blogs (>100 posts) consider `xargs -P 4` for parallel fetching, but keep concurrency modest — being a polite scraper preserves access.

## Article frontmatter (the contract)

```yaml
---
title: "<the article title>"
author: "<byline OR publication name>"
published: "YYYY-MM-DD"
source_url: "<canonical URL>"
ingested: "YYYY-MM-DD"
---
```

Rules:

- **Use this exact key set.** `docs-query` reads these specific keys; renaming breaks the freshness footer.
- **`published` must be `YYYY-MM-DD`.** If only year/month is available, use the 1st of the month (`2024-06-01`) — not a guess at the day.
- **Omit unknown fields rather than guessing.** Missing is fine; wrong is harmful.
- **`ingested` is today's date**, not the modification time of the file. Set it once on initial ingestion; don't update on refresh (since refresh doesn't re-fetch existing posts).
- **Quoting:** YAML strings should be double-quoted to survive colons, apostrophes, and HTML entities in titles.

### Why the date matters

When `docs-query` cites a blog post, it surfaces both `published` (when the author wrote it) and `ingested` (when our snapshot was taken). The first is what users actually care about — a 2022 essay on RAG architectures is dated regardless of how fresh our copy is. Without the publish date, users can't judge whether the advice is current. This is the single most common failure mode of LLM blog summaries — confidently citing stale advice — and the frontmatter eliminates it.

## Platform-specific quirks

### Substack

- Feed at `<name>.substack.com/feed` returns the latest 20 posts in full markdown-ish form.
- For older posts use the sitemap: `<name>.substack.com/sitemap.xml`.
- Substack adds a "Subscribe" CTA at the top and bottom of every post — strip these during conversion.
- Some Substacks are paywalled; truncated posts are obvious (ends mid-sentence with "Continue reading"). Don't ingest paywalled excerpts; ask the user whether to skip or pause.

### Medium

- Feed at `medium.com/feed/@<username>` or `medium.com/feed/<publication>` — capped at 10 posts.
- Medium aggressively renders client-side; `WebFetch` often returns nav-only content. Fall back to `agent-browser` or use the unofficial `https://medium.com/_/api/posts/<id>` JSON endpoint.
- Medium URLs include the slug + post ID (`-1234abcd`). Strip the ID for the local filename if you want stable paths.

### Ghost

- Feed at `<domain>/rss/`.
- Sitemap at `<domain>/sitemap.xml` includes a sub-sitemap per content type (`sitemap-posts.xml`, `sitemap-pages.xml`).
- Clean HTML, easy to convert. Recommended platform.

### Hugo / Jekyll / Gatsby (Anthropic, Cloudflare, Stripe, many vendor blogs)

- Feeds at `/feed.xml`, `/index.xml`, or `/atom.xml`.
- Often have an `llms.txt` or similar (Anthropic does for the docs side; check for the blog).
- Static HTML, `WebFetch` works well, conversion is clean.

### WordPress

- Feeds at `/feed`, `/feed/`, or `/?feed=rss2`.
- May paginate via `/feed/?paged=2`.
- Categories have their own feeds: `/category/engineering/feed/`.
- Strip "Posted in", "Tagged with", author boxes, related-posts widgets.

### SPA-embedded JSON (Expo Router, Next.js, Remix, Nuxt, modern Medium)

This isn't a platform — it's a *failure mode* that cuts across platforms. Modern SPAs hydrate client-side: the static HTML response carries near-empty body markup plus a JSON blob (or several) that contains the actual content. `html_to_md.py` and `markdownify` on that HTML produce 400+ lines of inline CSS / JS / runtime initialization with the article title buried somewhere in the middle as a plain text line, and the prose totally unreachable.

**Detect it before fetching at scale.** Fetch one sample page and grep for known bootstrap markers:

```bash
grep -oE '__NEXT_DATA__|__EXPO_ROUTER_LOADER_DATA__|__REMIX_DATA__|__NUXT_DATA__|window\.__INITIAL_STATE__|"@context":"https://schema.org"' sample.html | sort -u
```

Markers seen in the wild:

| Marker | Platform | Notes |
|---|---|---|
| `__NEXT_DATA__` | Next.js | Inside `<script id="__NEXT_DATA__" type="application/json">…</script>`. Most common. |
| `__EXPO_ROUTER_LOADER_DATA__` | Expo Router | Assigned to `globalThis.__EXPO_ROUTER_LOADER_DATA__ = JSON.parse("…escaped JSON…")`. JSON is double-encoded — once as a JS string literal, once as JSON. State-machine through the JS escapes to find the end of the literal; lazy regex `"(.+?)"\)` breaks on escaped quotes. Working precedent: the Expo blog (`expo/expo.dev/blog/`, 190 posts, 0 failures). |
| `__REMIX_DATA__` | Remix | Inside a `<script>window.__REMIX_DATA__ = {…}</script>` block. |
| `__NUXT_DATA__` / `window.__NUXT__` | Nuxt 3 / 2 | Inside `<script id="__NUXT_DATA__">` or assigned to `window.__NUXT__`. |
| `window.__INITIAL_STATE__` | Vue 2, older SSR | Generic store-hydration pattern. |
| `<script type="application/ld+json">` | Schema.org JSON-LD | Often duplicates the article body in a structured form; useful as a fallback even on non-SPA pages. |

**Extract from the JSON, don't markdownify.** The JSON typically holds the article in one of these formats — render to markdown directly:

- **Sanity Portable Text** (Expo blog, many indie blogs) — array of `{_type: "block", style, listItem, children: [{_type: "span", text, marks}]}` blocks plus images, code, and embeds. Render each block by type; render spans with mark-aware bold/italic/link wrapping.
- **Contentful Rich Text** — array of nodes with `nodeType: "paragraph" | "heading-1" | "unordered-list" | …` and `content: [{nodeType: "text", value, marks}]`.
- **Plain markdown source** — sometimes the CMS gives you the raw markdown string directly. Lucky.
- **Article HTML inside the JSON** — second-best; pass that string to markdownify rather than the whole-page HTML.

**Extraction recipe (generic):**

1. Read the HTML.
2. Find the bootstrap marker via state-machine, not regex, when the JSON is embedded as a JS string literal (escape handling kills regex).
3. `json.loads()` twice if double-encoded.
4. Find the post object — it's usually under a route-keyed dict like `{"/blog/<slug>": {"post": {...}}}`. Walk and look for an object with a `body`/`content` field.
5. Render the body to markdown by content type (Portable Text / Rich Text / HTML / markdown).
6. Write `.md` with YAML frontmatter, exactly as a normal blog post would have.

**Why this matters:** the JSON blob has clean, structured content. No nav chrome. No cookie banners. No "Subscribe" CTAs. No related-posts widgets. The strip step you'd otherwise do becomes "do nothing." Quality is dramatically better than the markdownify-on-soup fallback, and you sidestep the need for `agent-browser` or headless Chrome.

If a site has BOTH server-rendered HTML and a bootstrap JSON, prefer the JSON. It's cleaner, and you don't have to maintain selectors against the rendered DOM.

### Tailscale-style mixed sites (docs + blog + KB)

Already covered above — ingest `/docs/`, `/blog/`, `/kb/` separately under the same `<vendor>/<domain>/`. The vendor README should distinguish them:

```markdown
- **Tailscale**
  - Docs: `tailscale/tailscale.com/docs/` _(web mirror)_
  - Blog: `tailscale/tailscale.com/blog/` _(blog mirror, RSS-discovered)_
  - KB: `tailscale/tailscale.com/kb/` _(web mirror)_
```

## Refreshing without re-fetching

Blog posts are immutable. A 2024 article doesn't change in 2026 (and if it does, that's a content correction the team probably wants to know about — handle it manually). Therefore refresh = "fetch posts not yet on disk".

```bash
# 1. Pull the current feed
WebFetch "https://${domain}/feed" > /tmp/feed.xml
# Extract URLs into /tmp/feed-urls.txt

# 2. List local post slugs
find ~/github.com/alpinetmpl/docs/${vendor}/${domain}/ -name '*.md' \
  -not -name 'index.md' -not -name 'README.md' \
  | sed "s|.*${domain}/||;s|\.md$||" > /tmp/local-slugs.txt

# 3. Translate feed URLs to slugs the same way
sed "s|https://${domain}/||;s|/$||" /tmp/feed-urls.txt > /tmp/feed-slugs.txt

# 4. Diff
comm -23 <(sort /tmp/feed-slugs.txt) <(sort /tmp/local-slugs.txt) > /tmp/new-slugs.txt
echo "$(wc -l < /tmp/new-slugs.txt) new posts to ingest"

# 5. Fetch + convert + frontmatter for each new slug, as in whole-blog ingestion.
```

If the feed only goes back N posts and you want to catch posts published *between* the last refresh and "now-N", check the sitemap instead — sitemaps usually include all posts.

## Suggested initial sources

A starting menu of high-signal blogs the team might want to ingest. Don't ingest these speculatively — wait for the user to ask. Listed for reference only.

| Source | URL | Feed | Vendor folder | Notes |
|--------|-----|------|---------------|-------|
| Anthropic Engineering | https://www.anthropic.com/engineering | check `<head>` for `application/rss+xml` | `anthropic/www.anthropic.com/engineering/` | Joins existing `anthropic/` vendor folder |
| Sequoia Capital | https://www.sequoiacap.com/article/ | RSS likely under `/feed` | `sequoiacap/sequoiacap.com/article/` | Curated articles, not full firehose |
| a16z | https://a16z.com/ | `/feed/` (WordPress) | `a16z/a16z.com/` | High volume; curate selected posts |
| Cloudflare Blog | https://blog.cloudflare.com/ | `/rss/` | `cloudflare/blog.cloudflare.com/` | Engineering-heavy; sibling to existing `cloudflare/developers.cloudflare.com/` |
| Stripe Engineering | https://stripe.com/blog/engineering | check feed | `stripe/stripe.com/blog/engineering/` | New vendor folder if not present |
| fly.io Blog | https://fly.io/blog/ | `/blog/feed.xml` | `flyio/fly.io/blog/` | Infra/networking content |
| Grafana Blog | https://grafana.com/blog/ | check feed | `grafana/grafana.com/blog/` | Joins existing `grafana/` vendor folder |
| Simon Willison | https://simonwillison.net/ | `/atom.xml` | `simonwillison/simonwillison.net/` | AI/LLM-heavy, daily posts; curate or full |
| Paul Graham essays | http://www.paulgraham.com/articles.html | no feed; manual | `paulgraham/paulgraham.com/` | Static HTML, easy to convert |
