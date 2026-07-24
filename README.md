# skills

A working template for two things:

1. **Distributing Claude Code agent skills from one git repo** — every skill here is symlinked into each user's `~/.claude/skills/` by `install.sh`, and a `SessionStart` hook re-pulls the repo at the start of every Claude Code session. Push to `main` → live in everyone's next session. No per-project setup, no drift between machines.
2. **Running a local docs mirror** — a companion git repo that holds version-pinned vendor documentation (as git submodules and web mirrors) plus curated long-form content (engineering blogs, essays) with publish-date frontmatter. The `docs-query` and `docs-update` skills here operate that repo, so answers come from the exact doc version your team has pinned instead of training data or whatever the web serves today.

Fork it, search-and-replace the org name, and both systems are yours (see [Adapting to your org](#adapting-to-your-org)).

## Skills

The authoritative description of each skill is the `description:` in its `SKILL.md`.

- **docs-query** — read/search the local docs mirror: two-tier README index → grep within the right doc path → quote with file paths and a "Sources & freshness" footer (submodule pin dates, mirror snapshot dates, blog publish dates).
- **docs-update** — land content in the docs mirror: add/refresh vendor docs as git submodules (preferred) or web mirrors, ingest whole engineering blogs or single articles via RSS/Atom discovery, keep the README index in sync, commit and push.
- **skill-creator** — author, edit, eval, and benchmark skills in this repo (based on Anthropic's skill-creator, Apache 2.0 — see `skill-creator/LICENSE.txt`). Extended with a placement policy: skills default to this global repo so the distribution mechanism keeps everyone current.

## Install

```bash
# one-liner
curl -fsSL https://raw.githubusercontent.com/alpinetmpl/skills/main/install.sh | bash

# or, if you've already cloned the repo
./install.sh
```

Environment overrides: `SKILLS_CLONE_DIR` (clone location, default `~/github.com/alpinetmpl/skills`), `SKILLS_REPO_URL` (clone URL, default HTTPS; set an SSH URL if you prefer), `SKILLS_SKIP_HOOK=1` (don't install the SessionStart hook).

What it does:

- Clones (or pulls, `--ff-only`) the repo to the clone dir.
- For each top-level directory containing a `SKILL.md`, creates `~/.claude/skills/<skill>` → `<clone>/<skill>`. Your personal skills are left untouched.
- **Name collisions:** if `~/.claude/skills/<skill>` already exists as a real dir or as a symlink pointing somewhere outside the clone, it's renamed to `<skill>.backup.<timestamp>` and the shared version takes over. Restore or merge manually if needed.
- **Stale cleanup:** symlinks that point into the clone dir but whose target has been deleted from the repo are removed. Personal skills and unrelated symlinks are never touched.
- Adds a **`SessionStart` hook** to `~/.claude/settings.json` that re-runs `install.sh` on every new Claude Code session. This pulls the repo, links any new skills, cleans up symlinks for removed skills, and self-heals the hook if it gets edited or deleted. Set `SKILLS_SKIP_HOOK=1` to skip. `settings.json` is backed up before any modification.

To update manually any time: `git -C ~/github.com/alpinetmpl/skills pull` (or just re-run `./install.sh`).

## The docs mirror (companion repo)

The docs skills assume a second repo cloned at `~/github.com/alpinetmpl/docs`. It's plain git — create an empty repo and let `docs-update` grow it:

- Each **top-level directory is a vendor** (lowercase GitHub org or publication name).
- Vendor docs land as **git submodules** when a public docs repo exists (cheap to refresh, close to source of truth), otherwise as **web-mirrored markdown** whose file tree mirrors the URL paths.
- Blog posts and articles carry **YAML frontmatter** (`title`, `author`, `published`, `source_url`, `ingested`) so lookups can report how fresh — or how dated — a piece of advice is.
- A **two-tier README index** (root README → vendor README → exact doc path) makes lookup two reads and a grep instead of a 20k-file scan.

The full contract lives in `_shared/references/repo-layout.md`, which both docs skills read so they can't drift on it. `docs-query` never writes; `docs-update` always finishes with a commit and push.

## Layout

The repo root is the skills folder — each skill is a top-level directory.

```
<name>/
  SKILL.md           # frontmatter (name, description) + instructions
  references/        # optional supporting docs
  scripts/           # optional helper scripts
  evals/             # optional test cases for the skill-creator eval loop
```

Top-level dirs without a `SKILL.md` (`_shared/`, `tools/`) are ignored by the installer. Root-level `*-workspace/` dirs are gitignored — that's where skill-creator eval runs put their artifacts.

### Shared references (`_shared/`)

Content used by **more than one skill** lives once under `_shared/`, a flat pool shaped like a skill's own insides — `_shared/references/` and `_shared/scripts/`. Each skill owns a **real** `references/` (and `scripts/`) directory that mixes its own local files with **symlinks** into the pool, so from inside a skill it's still a flat `references/<file>.md` hop:

```
_shared/                         # no SKILL.md — install.sh ignores it
  references/
    repo-layout.md               # multi-consumer: docs-query + docs-update

docs-query/references/           # a REAL dir:
  vendor-paths.md                #   local file (single-owner, lives here)
  repo-layout.md -> ../../_shared/references/repo-layout.md   # per-file symlink
```

**Rules of the pool** (see [`_shared/README.md`](_shared/README.md) for the full version):

- **Shared vs. local, not by family.** A file belongs in `_shared/` only once a **second** skill actually consumes it. A file used by exactly one skill lives in that skill's own real `references/`. Promote on the real 2nd consumer, not speculatively.
- **Edit the real file under `_shared/`, never a per-skill copy** — the per-skill path is a symlink; every consumer sees the change instantly.
- **Symlink granularity:** independent top-level pool files are symlinked **per-file** (a skill pulls just the ones it cites). Cohesive subject subfolders whose docs cross-link each other are symlinked **whole-dir by every consumer** — a partial pull would break a citation or an internal link. A skill symlinks the transitive link-closure of what it cites. Symlink name == target name.
- Names in the pool are **descriptive** (`repo-layout.md` works today; prefer multi-word like `platform-overview.md` as it grows) so a flat namespace doesn't collide.
- `tools/check-shared-drift.sh` catches the main failure modes — dangling symlinks, a skill-local file that's a byte-identical copy of a pooled one, cited paths that don't resolve, and cross-links broken by a partial pull. Run it before pushing.

(Consequence: a skill dir with `_shared/` symlinks isn't self-contained, so these skills are consumed via the `install.sh` symlinks, not by packaging into a standalone `.skill` bundle, which would leave the symlinks dangling.)

## Adapting to your org

1. Fork (or copy) this repo under your own org, and create an empty `docs` repo next to it.
2. Search-and-replace `alpinetmpl` with your org name across the repo — it appears in `install.sh` (clone URL, clone dir, hook marker), both docs skills (the `~/github.com/<org>/docs` path), and this README.
3. Edit the `docs-query` skill's `description:` vendor list to match what your mirror actually holds, and prune `docs-query/references/vendor-paths.md` down to your own contents — both are trigger/lookup surfaces that should agree with disk.
4. Have everyone run the install one-liner once; the SessionStart hook keeps them current from then on.

Treat `main` as production: a push reaches every teammate's next session. See [`CLAUDE.md`](CLAUDE.md) for the conventions Claude Code sessions follow when editing this repo.
