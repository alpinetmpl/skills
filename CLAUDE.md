# CLAUDE.md

Guidance for Claude Code sessions working **in** this repo. This is a shared agent-skills repo: every skill here is symlinked into each teammate's `~/.claude/skills/` and refreshed on every session (see "How skills propagate"). You are usually editing skills, not application code.

## The one thing to internalize: changes here are live for everyone

Skills in this repo are not a library someone opts into per-project. `install.sh` symlinks each skill dir into `~/.claude/skills/<skill>`, and a `SessionStart` hook re-runs `install.sh` (`git pull --ff-only` + re-link) at the start of **every** Claude Code session for everyone who installed it. So:

- **A push to `main` reaches every teammate's next session.** There is no staging. Treat `main` as production. Prefer a branch + review for anything non-trivial; only fast-forward `main` when you mean to ship.
- A content edit to a `SKILL.md` or a `_shared/` file is live in the local clone **immediately** — the symlink means no re-link is needed. Re-run `install.sh` only when you **add or remove a skill directory** (to create/prune the top-level symlink).
- Because skills load into the model's context by triggering on their `description:`, a bad description doesn't just fail to fire — it can mis-fire into unrelated work across the whole team. Descriptions are load-bearing; change them deliberately.

## How skills propagate (the mechanism)

`install.sh` (idempotent, safe to re-run) does, in order:
1. Clone or `git pull --ff-only` the repo to `~/github.com/alpinetmpl/skills` (override: `SKILLS_CLONE_DIR`, `SKILLS_REPO_URL`).
2. For every top-level dir **containing a `SKILL.md`**, symlink it to `~/.claude/skills/<dir>`. Personal-skill name collisions are backed up to `<skill>.backup.<ts>`; stale symlinks (target deleted from repo) are pruned. Personal skills and unrelated symlinks are never touched.
3. Inject/repair a `SessionStart` hook in `~/.claude/settings.json` that runs `bash <clone>/install.sh >/dev/null 2>&1 || true`. The hook self-heals because it re-runs the installer that (re)writes it. Opt out with `SKILLS_SKIP_HOOK=1`.

Implication: **a top-level directory is a skill iff it has a `SKILL.md`.** Dirs without one (`_shared/`, `tools/`, and root-level `*-workspace/`) are ignored by the installer. Do not add a top-level dir that isn't a skill unless it's one of these ignored shapes — otherwise nothing links it, or worse, it links as a broken "skill." Don't hand-edit the `settings.json` hook; `install.sh` owns it.

## Anatomy of a skill

```
<name>/
  SKILL.md        # required: YAML frontmatter (name, description) + instructions
  references/     # optional supporting docs — may contain symlinks into _shared/
  scripts/        # optional helper scripts — may contain symlinks into _shared/
  evals/          # optional test cases for the skill-creator eval loop
```

- **The directory name MUST equal the `name:` in the frontmatter.** `install.sh` links by directory name; Claude loads and invokes by frontmatter `name`. If they drift, the skill links under one name and triggers under another. When you rename, rename both, then re-run `install.sh` to fix the symlink.
- `description:` is the trigger surface — write it to fire on the user's intents and, just as importantly, to *not* fire on a sibling's. The docs skills carry explicit "Do NOT use for … (that's X)" clauses to prevent cross-fire; match that style.

## Shared references (`_shared/`) — a flat, skill-shaped pool

Content used by **more than one skill** lives once under `_shared/`, a flat pool shaped like a skill's own insides: `_shared/references/` and `_shared/scripts/` (add `_shared/assets/` when something first needs it). There is **no family tier** — the axis is *shared vs. local*, not skill families. (An earlier family-tier model faked cross-family sharing with an intra-`_shared` symlink farm; see `_shared/README.md` for the full convention.)

How a skill consumes it: each skill owns a **real** `references/` (and `scripts/`) directory that mixes its own local files with **symlinks** into the pool, so from inside a skill it's still a flat `references/<file>.md` hop.

- **Multi-consumer files** (≥2 skills) live in the pool, once. **Single-owner files** live in the owning skill's own real `references/`. Promote a file into `_shared/` only when a **real second consumer** appears — never speculatively (that speculation is what bloats shared tiers).
- **Symlink granularity:** independent top-level pool files are symlinked **per-file** — a skill pulls only the ones it cites (today: `repo-layout.md`, pulled by both docs skills). If a cohesive **subject subfolder** emerges whose docs cross-link each other, every consumer symlinks it **whole-dir**, not per-file — a partial pull would leave internal links dangling within the consumer's tree. The general rule: **a skill must symlink the transitive link-closure of what it cites** (the drift check's check 4 catches exactly this). Symlink name == target name.
- Pool filenames are **descriptive** so the flat namespace doesn't collide as it grows — prefer multi-word (`platform-overview.md`) over bare single words. Files inside a subject subfolder don't restate the folder (`credentials/kubectl.md`, not `credentials/kubectl-credentials.md`).

Rules when editing:
- **Always edit the real file under `_shared/`, never a per-skill path** — the per-skill path is a symlink; every consumer sees your change instantly. If a "per-skill copy" looks editable, `ls -la` it first; you're almost certainly looking at a symlink.
- Adding a shared file to a skill = create a symlink (`ln -s ../../_shared/references/<file> <skill>/references/<file>`), never copy it. `tools/check-shared-drift.sh` flags a skill-local file that's byte-identical to a pooled one (the copy-instead-of-symlink drift). Run it before pushing.
- **Consequence:** a skill dir with `_shared/` symlinks is *not* self-contained, so these skills are consumed via the `install.sh` symlinks, not by packaging into a standalone `.skill` bundle (which would leave the symlinks dangling). Keep it that way unless you're deliberately de-sharing a skill.

## Workflow

- **Use the `skill-creator` skill** to create, edit, optimize, or eval skills — it encodes the authoring + benchmarking flow. Reach for it rather than hand-rolling structure.
- **Scratch and eval artifacts** go in root-level `<skill>-workspace/` dirs — gitignored specifically so `install.sh` never mistakes an eval dir for a skill.
- **Changelog:** record repo-level changes in the top-level [`CHANGELOG.md`](CHANGELOG.md) (Keep-a-Changelog-ish, absolute `YYYY-MM-DD` dates, short SHAs).
- **Before shipping a skill change**, sanity-check: dir name == frontmatter `name`; any `_shared/` edits are on the real file; symlinks resolve (`ls -laL <skill>/references`); and the `description:` still fires on the intended intents without poaching a sibling's. Then commit; push to `main` only when you intend it live for everyone.

## Conventions

- Dates in docs/changelogs are absolute (`YYYY-MM-DD`), not relative.
- Ground vendor/product claims in the docs mirror (`docs-query`) before asserting them in a skill — don't ship an unverified "why."
