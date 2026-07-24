# The docs mirror: layout & contracts

Shared substrate for the docs skills (docs-query + docs-update). **docs-query reads** this repo; **docs-update writes** it. Both skills must agree on where content lives, how it's named, and what metadata every file carries — so those facts live here once instead of drifting between two copies. Read this first; each skill's SKILL.md then adds only its own side (finding + citing, or ingesting + committing).

Root of everything: `~/github.com/alpinetmpl/docs/` (~20k markdown files across 80+ sources).

## Two flavors of content

The repo holds two kinds of content that share one layout but differ in how you date them:

- **Reference documentation** — versioned, evergreen vendor docs (Kubernetes, Grafana, Vault, Terraform, Cilium…). Either submodule-cloned or web-mirrored. Dated by the submodule pin + upstream commit, or the web-mirror snapshot.
- **Doc-worthy long-form** — engineering blogs, vendor blogs, and curated essay/strategy posts (Anthropic engineering, Cloudflare/Stripe blogs, Sequoia/a16z articles, Simon Willison posts…). Always web-mirrored, often a single article. Each post carries a YAML frontmatter block whose `published:` date is what usually matters — a 2022 essay's advice can be stale today no matter when we snapshotted it.

## Vendor / domain layout

- Each **top-level directory is a vendor**, named after the GitHub org or publication, **lowercase** — e.g. `grafana/`, `kubernetes/`, `anthropic/`, `sequoiacap/`, `ot-container-kit/`. (Upstream `OT-CONTAINER-KIT` → local `ot-container-kit/`; only the `.gitmodules` URL keeps original casing.)
- Inside a vendor:
  - `<vendor>/<repo>/` — **submodule** clone of an upstream docs repo.
  - `<vendor>/<domain>/…` — **web-ingested mirror** (docs site, blog, or single article) whose subdirectory tree mirrors the URL path. Example: `https://tailscale.com/docs/features/kubernetes-operator/` → `tailscale/tailscale.com/docs/features/kubernetes-operator.md`. Preserve URL-path casing; use `.md` for everything.
- Whether a given `<vendor>/<name>` is a submodule or a web mirror is decided by `~/github.com/alpinetmpl/docs/.gitmodules`: if it's listed there, it's a submodule (read-only clone — its dates come from git history); otherwise it's a web mirror (a point-in-time copy — its date is the last time docs-update wrote it).

## Two-tier README index

The READMEs are the fast path — the map from a product to the exact folder its docs live in. Both tiers must stay current; **drift between the READMEs and what's actually on disk is the family's most common failure mode.**

- **Root `README.md`** — light table of contents, one entry per vendor brand, linking to the vendor README(s).
- **`<vendor>/README.md`** — per-vendor list of every product/blog in that folder, each with the **exact content path** (e.g. `cloudnative-pg/docs/website/docs`, `grafana/loki/docs/sources`, `kubernetes/website/content/en/docs`). Use the path it gives you; don't guess — doc-path conventions vary by upstream (`docs/`, `website/`, `site/content/`, `content/`, `src/content/docs/`).

## Blog / article frontmatter contract

Every ingested blog post or article carries a YAML frontmatter block at the top of the markdown. This is the contract that lets **docs-update** record when a post was written and lets **docs-query** answer "how stale is this?" without re-fetching the live page. Reference docs (submodules, doc-site mirrors) do **not** get this block — their dates come from git.

```markdown
---
title: "Multi-agent research system"
author: "Anthropic engineering"
published: "2024-06-15"
source_url: "https://www.anthropic.com/engineering/multi-agent-research-system"
ingested: "2026-05-17"
---

# Multi-agent research system

...post body in markdown...
```

| Field | Meaning |
|-------|---------|
| `title` | Article title (from the page `<title>` or `<h1>`). |
| `author` | Byline if available, else the publication name ("Anthropic engineering", "Sequoia Capital"). |
| `published` | `YYYY-MM-DD` the article was published. The load-bearing date for long-form content. |
| `source_url` | Canonical URL of the article. |
| `ingested` | `YYYY-MM-DD` we pulled it. Use exactly this key (not `scraped`/`fetched`) so docs-query can find it. |

Two rules both sides depend on:

- **Omit a field you can't find rather than guessing** — a missing field reads as "unknown", not "false". Never *fabricate* a `published` date.
- The first lines being a `---` frontmatter block is how you tell a long-form post from a reference page: to read the metadata fast regardless of file size, `head -20 <file> | sed -n '/^---$/,/^---$/p'`.

docs-update owns *how each field is populated* from page metadata; docs-query owns *which date it surfaces* and how the freshness footer is formatted. Both are in the respective SKILL.md — this table is just the shape they share.
