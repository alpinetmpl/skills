# `_shared/` — the shared reference/script pool

This directory is **not a skill** (it has no `SKILL.md`, so `install.sh` ignores it). It's a flat pool of reference/script content that **more than one skill** uses, authored once so siblings can't drift.

```
_shared/
  references/     # shared docs; subject subfolders allowed when a cohesive cluster emerges
  scripts/        # shared executables (create when a second skill needs one)
  assets/         # (create only when a skill first needs a shared image/template)
```

## The one rule: shared vs. local, not by family

The pool is organized by **who consumes a file**, not by which skill *family* it belongs to. The family axis is a trap — a file consumed by skills in two different families can't live in either family's tree without a symlink farm. So:

- A file belongs in `_shared/` **only once a second skill actually consumes it.**
- A file used by exactly **one** skill lives in that skill's own real `references/` (or `scripts/`), not here.
- **Promote on the real second consumer — never speculatively.** "A future skill might want this" is exactly the reasoning that bloats shared tiers. When the second consumer actually arrives, `git mv` the file into the pool and symlink both skills to it.

## How a skill consumes the pool

Each skill owns a **real** `references/` (and `scripts/`) directory — not a symlink — that mixes its own local files with symlinks into the pool. From inside the skill it's a flat `references/<file>.md` hop either way.

**Symlink granularity has two cases:**

- **Independent top-level files → per-file symlinks.** A skill pulls only the pool files it cites. Today's example — `repo-layout.md` is the shared substrate of the docs skills, so each pulls exactly that file:
  ```
  docs-query/references/repo-layout.md  -> ../../_shared/references/repo-layout.md
  docs-update/references/repo-layout.md -> ../../_shared/references/repo-layout.md
  ```
- **Cohesive subject subfolders → whole-dir symlink, for every consumer.** When a cluster of docs cross-link each other (say, a `credentials/` subfolder where `kubectl.md` links `tailscale.md`), consumers pull the **whole directory**, not a subset — a partial pull would leave those internal links dangling within the consumer's tree:
  ```
  some-skill/references/credentials -> ../../_shared/references/credentials
  ```
  The unifying principle is the **transitive-link-closure** rule: when a skill symlinks a pooled doc, everything that doc cites or links must also be reachable in the skill's tree. For a cross-linked subfolder that's the whole subfolder. `tools/check-shared-drift.sh` (check 4) enforces it.

**Symlink name == target name.** A per-file symlink is named exactly like the file it points at. Relative targets: `../../_shared/references/<file>` from `<skill>/references/`.

## Naming

Pool filenames are **descriptive multi-word** (`platform-overview.md`, `repo-layout.md`, `gitops-workflow.md`) so a flat namespace doesn't collide as it grows — a bare `platform.md` would be a landmine once a second subject needs the name. Files **inside** a subject subfolder don't restate the folder: `credentials/kubectl.md`, not `credentials/kubectl-credentials.md`.

## Adding / changing content

- **Edit the real file here, never a per-skill path** — the per-skill path is a symlink; every consumer sees the change instantly. If a "per-skill copy" looks editable, `ls -la` it first.
- **Wire a shared file into a skill with a symlink, never a copy:**
  ```
  ln -s ../../_shared/references/<file> <skill>/references/<file>
  ```
- **Run the drift check before pushing:** `tools/check-shared-drift.sh` flags dangling symlinks and — the main failure mode — a skill-local *real* file that is byte-identical to a pooled one (i.e. someone copied instead of symlinking). It's a run-before-push script, not a CI gate; there is no CI in this repo.

## Consequence

A skill directory that symlinks into `_shared/` is **not** self-contained. These skills are consumed via the `install.sh` symlinks (the whole clone is present), not by packaging a skill into a standalone `.skill` bundle — that would leave the `_shared/` symlinks dangling. Keep it that way unless you're deliberately de-sharing a skill (move its files home, drop the symlinks).
