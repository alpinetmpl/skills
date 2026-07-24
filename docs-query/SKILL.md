---
name: docs-query
description: >-
  Look up official vendor documentation AND curated long-form content
  (engineering blogs, vendor blogs, reputable strategy/essay posts) already
  mirrored in the local docs repo at `~/github.com/alpinetmpl/docs/` (~20,000
  markdown files across 80+ sources, kept fresh as git submodules and web
  mirrors). Use this skill whenever the user is ASKING ABOUT a product or
  source we mirror — how-to, config key, CRD/API spec, version-specific
  behavior, "what do the docs say", "does X support Y", a bare vendor+feature
  fragment like "vault transit wrap_ttl", or pointed blog/article questions
  like "what does Anthropic engineering recommend for prompt caching",
  "what did Sequoia say about AGI", "find me Simon Willison's post on X".
  Reach for the local mirror FIRST, before training data or WebSearch, so
  answers match the version/snapshot the team has pinned. Covers
  (non-exhaustive): anthropic (incl. engineering blog), argocd, argo, cilium,
  cloudflare, cloudnativepg/cnpg, crossplane, envoy gateway, fastapi, gemini,
  grafana, harbor, helmfile, k3s, k6, karpenter, keda, kong, kubernetes/k8s,
  kyverno, langchain, langgraph, langfuse, linkerd, litellm, loki, mcp,
  mimir, oci, openhands, opensearch, portkey, rabbitmq, redis, redpanda,
  rook, sequoia, simonwillison, slack, strimzi, tailscale, tempo, terraform,
  vault, vertex ai, zitadel. DO NOT trigger when the user wants to
  add/import/scrape/ingest/refresh/update/remove content (that's
  docs-update), or when a vendor/source name only appears incidentally
  inside a request to write code, draft a message, or review a PR.
---

# docs-query

Find the right authoritative content in `~/github.com/alpinetmpl/docs/` for whatever the user is working on. Read-only — never modify the repo. If the user asks to add or refresh content, hand off to the sibling **docs-update** skill.

**Read [references/repo-layout.md](references/repo-layout.md) first** — it's the shared substrate for the docs skills (repo layout, vendor/domain naming, the two-tier README index, and the blog frontmatter contract), owned in one place so this skill and docs-update can't drift on it. The notes below only add what's query-specific.

The repo holds two flavors of content — **reference documentation** (versioned vendor docs) and **doc-worthy long-form** (blogs/articles). The fast-path workflow (vendor README → grep → quote) is identical for both; what differs is the freshness footer, because long-form posts carry a `published:` date in their frontmatter that's usually the date the user actually cares about. See "Capture freshness" below.

## Why bias toward triggering

The docs repo is the team's canonical, version-pinned mirror of vendor documentation. Answering from it beats answering from training data (which is out of date) and beats WebSearch (which lands on whatever version Google ranks today, often not the version the team has standardized on). The cost of opening this skill is small (~80 lines); the cost of giving an out-of-date or version-mismatched answer is high. **When in doubt, trigger.**

## Step 0 — Refresh the local copy first

Always pull the latest `origin/main` before answering. Other team members and the docs-update skill push frequently, so the local clone drifts. A stale local copy defeats the whole point of having a pinned mirror.

```bash
git -C ~/github.com/alpinetmpl/docs pull --ff-only origin main
```

If the pull fails (network down, conflict from local edits, etc.), proceed with the existing clone but tell the user: "Couldn't pull latest — answering from the local copy as of `<git log -1 --format=%cr>`." Never block on a refresh failure.

If submodule contents look empty after pulling (a new submodule was added remotely), initialize:

```bash
git -C ~/github.com/alpinetmpl/docs submodule update --init --recursive --depth 1
```

This is cheap when no init is needed; only does real work when a new submodule appeared.

## Repo layout in 30 seconds

The full layout — vendor/domain structure, submodule vs. web mirror, the two-tier README index, and the frontmatter block on long-form posts — is in [references/repo-layout.md](references/repo-layout.md). The two facts the lookup workflow leans on: each top-level directory is a **vendor** (lowercase GitHub org or publication), and the **root README → vendor README** pair maps any product to the exact folder its docs live in.

## Lookup workflow

The fast path is two reads then a grep. Don't skip straight to grep — finding the right doc subdirectory makes the grep ~100× cheaper than scanning the whole 20k-file repo.

### Step 1 — Identify the vendor

If you already recognize the product (kubernetes, grafana, cilium, terraform, vault, etc.) you can skip the root README. Otherwise:

```bash
# Read the root README to map product → vendor folder
Read ~/github.com/alpinetmpl/docs/README.md
```

For known-vendor shortcuts, see `references/vendor-paths.md` — a fast lookup table of common vendor + product → doc content path mappings.

### Step 2 — Read the vendor README to find the doc path

```bash
Read ~/github.com/alpinetmpl/docs/<vendor>/README.md
```

The vendor README lists every product in that folder with the **exact doc content path** — e.g. `cloudnative-pg/docs/website/docs`, `grafana/loki/docs/sources`, `kubernetes/website/content/en/docs`. Use the path it gives you; don't guess.

### Step 3 — Search within the doc path

```bash
# Keyword search in a specific product's docs
grep -ri "<keyword>" ~/github.com/alpinetmpl/docs/<vendor>/<repo>/<doc-path>/ --include="*.md" -l

# Filename search (when you're hunting for a specific topic page)
find ~/github.com/alpinetmpl/docs/<vendor>/ -name "*<topic>*" -name "*.md"

# Both at once — find files matching a name AND containing a keyword
grep -ri "<keyword>" $(find ~/github.com/alpinetmpl/docs/<vendor>/ -name "*<topic>*" -name "*.md") -l
```

For docs that aren't in standard markdown (e.g. `.mdx`, `.rst`), broaden the include:

```bash
grep -ri "<keyword>" <path>/ --include="*.md" --include="*.mdx" -l
```

### Step 4 — Read and answer

Open the matched files with `Read`. Quote relevant sections back to the user with the path included so they can verify:

```
From `cilium/cilium/Documentation/network/concepts/policy.rst:42`:

  > Cilium supports L3, L4, and L7 network policies...
```

### Step 5 — Capture the freshness of every cited file

A citation without a date is half an answer. The same path can hold different content depending on what SHA the submodule is pinned to, or when the web mirror was last scraped — and product behavior often differs across versions. Before composing the response, grab the timestamps you'll need for each unique file you cite.

**For files inside a submodule** (i.e. the cited path starts with a directory that appears in `~/github.com/alpinetmpl/docs/.gitmodules`):

```bash
# 1. What SHA is the submodule pinned to in the docs repo, and is there a
#    version-y describe tag on it? Run from the docs repo root.
git -C ~/github.com/alpinetmpl/docs submodule status -- <vendor>/<repo>
# Example output:
#  2e3da9a59a5257d905bc3421674a36b568ccdb15 grafana/loki (helm-loki-5.44.1-5528-g2e3da9a59a)
# The trailing parenthesized string is `git describe` on the pinned SHA —
# often the closest thing to a human-readable version (e.g. v1.21.0, 5.44.1).

# 2. When was that pinned commit authored?
git -C ~/github.com/alpinetmpl/docs/<vendor>/<repo> log -1 --format='%h %ad' --date=short
#  → 2e3da9a59a 2026-05-15

# 3. When did the cited *file* last change in the upstream repo?
git -C ~/github.com/alpinetmpl/docs/<vendor>/<repo> log -1 --format='%h %ad' --date=short -- <path/relative/to/submodule/root>
#  → 80b098c88f 2026-04-22
```

The file-level commit is the one that actually matters for accuracy — it tells the user "this guidance reflects the upstream as of April 22". The submodule pin date tells them how recently the team refreshed it.

**For files inside a web-ingested mirror** (i.e. the cited path is under `<vendor>/<domain>/...` and `<vendor>/<domain>` is NOT a submodule):

```bash
# When was this mirror file last written by docs-update? (point-in-time copy,
# so this is the snapshot date the user is reading from.)
git -C ~/github.com/alpinetmpl/docs log -1 --format='%h %ad' --date=short -- <vendor>/<domain>/<file>
#  → 8667b43 2026-03-24
```

**For blog posts and articles** (any cited file whose first lines are a YAML `---` frontmatter block): also read the frontmatter to pull the publish date — that's the date the user actually cares about for blog content. A 2022 essay on RAG architectures is dated regardless of when we ingested it; conversely, our 2026 snapshot of a 2024 article is fine if the user is asking about the article itself.

```bash
# Read just the frontmatter — fast, regardless of file size.
head -20 <file> | sed -n '/^---$/,/^---$/p'
```

The fields and their meanings are the frontmatter contract in [references/repo-layout.md](references/repo-layout.md); on the read side you mainly want `published` and `ingested`. Surface BOTH dates in the footer for blog content: `Published 2024-06-15 · ingested 2026-05-17`. If `published` is missing, fall back to the git snapshot date and say "publish date unknown".

Run these once per unique file you cite — don't re-run for each line you quote from the same file. Batch the lookups before writing the response.

If a command errors (file doesn't exist in git yet, broken submodule), don't block — note "freshness unknown" for that citation and keep going.

## When the vendor is unknown

If you can't identify the vendor from the user's question:

1. Skim the root README for clues — vendor descriptions cover the product space.
2. If still unclear, repo-wide grep is acceptable as a fallback (slower but works):
   ```bash
   grep -ri "<distinctive-phrase>" ~/github.com/alpinetmpl/docs/ --include="*.md" -l | head -20
   ```
3. Once a vendor surfaces, drop back into the standard workflow (read vendor README → grep within the right path).

## When the docs aren't in the repo

If you've checked thoroughly and the vendor isn't there, tell the user — don't silently fall back to training-data answers without flagging it. Two reasonable next steps:

1. Offer to import them via the **docs-update** skill: "We don't have docs for X locally. Want me to bring them in?"
2. Use `WebSearch` / `WebFetch` against the official docs site, and clearly note that this is the live web version, not our pinned mirror.

## What to report back

For every answer drawn from the local docs, include:

- The **file path** relative to the docs repo root (e.g. `grafana/loki/docs/sources/configure/_index.md:120`).
- A **direct quote** of the relevant lines (don't paraphrase when accuracy matters).
- A **freshness footer** at the end of the response — one entry per unique source file you cited. This is the cue the user needs to judge whether the answer matches the version they're running. Format:

  ```
  ## Sources & freshness
  - `grafana/loki/docs/sources/configure/storage.md` — submodule pinned at
    `2e3da9a` (helm-loki-5.44.1-5528-g2e3da9a59a, 2026-05-15); file last
    touched upstream 2026-04-22 (80b098c88f).
  - `tailscale/tailscale.com/docs/features/kubernetes-operator.md` —
    web mirror, snapshot taken 2026-03-24 (8667b43).
  - `anthropic/www.anthropic.com/engineering/multi-agent-research.md` —
    blog post, published 2024-06-15 by Anthropic engineering; ingested
    2026-05-17 (b9d77a1).
  - `sequoiacap/sequoiacap.com/article/2026-this-is-agi.md` — article,
    published 2026-04-08; ingested 2026-05-10 (3f1a2c4).
  ```

  Keep it terse — one bullet per file, dates in `YYYY-MM-DD`, short SHAs. If a version string is in the path or the `git describe` output (e.g. `v1.21.x`, `helm-loki-5.44.1`), surface it; it's often the most useful piece for the user. For blog/article content, the *published* date is usually what the user cares about most — call it out first.
- If the freshness lookup failed for some reason, say "freshness unknown" for that file rather than omitting it — silence reads as "this is fresh."

This lets the user click straight to the source and immediately see what version of the docs they're reading.

## Rules

1. **Always pull origin/main first.** A stale local copy gives stale answers — that defeats the whole point of the pinned mirror. Use `git -C ~/github.com/alpinetmpl/docs pull --ff-only origin main` before any lookup. If it fails, fall through and warn the user about the staleness.
2. **Trigger broadly.** Mentions of any vendor we mirror, or any how-to / config / spec / reference question about a tool we mirror, should pull in this skill. Don't wait for explicit "find docs" phrasing.
3. **Read-only.** Never modify files under `~/github.com/alpinetmpl/docs/`. Submodule contents in particular are read-only clones — changes there are silently lost on the next `git submodule update`.
4. **Two-tier README index is the fast path.** Root README → vendor README → grep within the listed doc path. Don't scan the whole repo when one folder is needed.
5. **Quote with file paths AND freshness.** Every claim cites a file path (relative to the docs root) with a line number, and the response ends with a "Sources & freshness" footer giving the submodule pin date + file's last upstream change (for submodule sources), the snapshot date (for web mirrors), OR the article publish date + ingestion date (for blog content with YAML frontmatter). Same path can carry different content at different pins, and product behavior often differs across versions — the date is what lets the user trust the answer applies to their deployment. For blog content the *publish* date is the load-bearing one: a 2022 essay's advice may be stale today even if we ingested it last week.
6. **Flag when the docs aren't there.** Don't silently fall back to training data — explicitly tell the user the local repo doesn't have them and offer the next step.
7. **Hand off writes to docs-update.** If the user says anything that implies adding, importing, refreshing, scraping, or updating docs, do not start that work here — hand off to the sibling skill.

## References

- `references/repo-layout.md` — shared docs-family substrate: repo layout, vendor/domain naming, the two-tier README index, and the blog frontmatter contract. Read it first; docs-update owns the same file, so it never drifts from what this skill expects to read.
- `references/vendor-paths.md` — Vendor + product → exact doc content path. Fast lookup table for known vendors; skips the README hop.
