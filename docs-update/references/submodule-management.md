# Submodule management

Detailed procedures for git submodule operations in the docs repository at `~/github.com/alpinetmpl/docs/`. The SKILL.md covers the common add/refresh paths; this file is for the longer-tail operations: pinning, removing, troubleshooting.

## Table of contents

- [Pre-flight checks](#pre-flight-checks)
- [Add a new submodule](#add-a-new-submodule)
- [Refresh submodules](#refresh-submodules)
- [Pin to a specific version](#pin-to-a-specific-version)
- [Remove a submodule](#remove-a-submodule)
- [.gitmodules format](#gitmodules-format)
- [Troubleshooting](#troubleshooting)

## Pre-flight checks

```bash
# Health-check candidate repo
gh repo view <ORG>/<REPO> --json isArchived,pushedAt,visibility,description,defaultBranchRef

# Expected:
#   isArchived: false
#   pushedAt: within last 6 months
#   visibility: PUBLIC
```

```bash
# Find the doc subdirectory in the upstream repo
gh api repos/<ORG>/<REPO>/contents --jq '.[].name'
# Common conventions: docs/, website/, content/, site/content/, src/content/docs
```

For repos not on GitHub:

```bash
# GitLab
glab repo view <ORG>/<REPO>
# Bitbucket — use the web UI or `curl https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>`
```

## Add a new submodule

```bash
cd ~/github.com/alpinetmpl/docs
git submodule add https://github.com/<ORG>/<REPO>.git <vendor>/<repo>
```

For very large repos (>500MB — `kubernetes/website` is the canonical example) use shallow clone:

```bash
git submodule add --depth 1 https://github.com/<ORG>/<REPO>.git <vendor>/<repo>
```

Naming rules:
- Local path is lowercase even if the upstream org uses uppercase or mixed case (`OT-CONTAINER-KIT` → `ot-container-kit/`).
- `.gitmodules` `url` keeps the original-case URL.
- `.gitmodules` is updated automatically by `git submodule add` — do not hand-edit.

Post-add:

```bash
# Verify
git submodule status <vendor>/<repo>

# Update vendor README — either by hand or with the regenerator
python3 ~/.claude/skills/docs-update/scripts/regen_vendor_readme.py <vendor>

# Commit (selective add — never -A or .)
git add .gitmodules <vendor>/<repo> <vendor>/README.md
# If the vendor brand is new to root README, add it too:
git add README.md
git commit -m "Add <vendor>/<repo>: <one-line>"
git push origin main
```

## Refresh submodules

### Refresh one submodule

```bash
cd ~/github.com/alpinetmpl/docs/<vendor>/<repo>
git fetch origin
git checkout origin/main   # or origin/master — check defaultBranchRef
cd ~/github.com/alpinetmpl/docs
git add <vendor>/<repo>
git commit -m "Update <vendor>/<repo> to latest upstream"
git push origin main
```

### Refresh ALL submodules

```bash
cd ~/github.com/alpinetmpl/docs
git submodule update --remote      # fast-forwards each submodule to upstream HEAD
git diff --submodule               # review changes
git add -u                         # stage pointer changes only (this is safe — only modifies tracked submodule entries)
git commit -m "Update all submodules to latest upstream"
git push origin main
```

`git add -u` is safe here even with the "selective add" rule, because submodule pointer changes are isolated — it won't pick up any unrelated dirty submodule contents (those would be tracked inside the submodule, not in the parent).

### Initialize after fresh clone

```bash
cd ~/github.com/alpinetmpl/docs
git submodule update --init --recursive
```

## Pin to a specific version

Useful when an upstream is fast-moving and we want stability, or when the latest commit breaks something.

```bash
cd ~/github.com/alpinetmpl/docs/<vendor>/<repo>

# Pin to a tag
git fetch --tags origin
git checkout v1.2.3

# Or pin to a specific commit
git checkout abc1234

# Go back and commit the pinned pointer
cd ~/github.com/alpinetmpl/docs
git add <vendor>/<repo>
git commit -m "Pin <vendor>/<repo> to v1.2.3"
git push origin main
```

Document the pin reason in the vendor README so future refreshes don't blindly bump it back.

## Remove a submodule

```bash
cd ~/github.com/alpinetmpl/docs

# 1. Deinit
git submodule deinit -f <vendor>/<repo>

# 2. Remove git metadata
rm -rf .git/modules/<vendor>/<repo>

# 3. Remove from working tree and index
git rm -f <vendor>/<repo>

# 4. Update vendor README (remove the entry); update root README if this was the vendor's last product

# 5. Commit
git add .gitmodules <vendor>/README.md README.md
git commit -m "Remove <vendor>/<repo> submodule"
git push origin main
```

If the vendor directory is now empty (no submodules, no mirrors, no README), remove it:

```bash
rmdir <vendor>  # only succeeds if truly empty
```

## .gitmodules format

```ini
[submodule "<vendor>/<repo>"]
	path = <vendor>/<repo>
	url = https://github.com/<ORG>/<REPO>.git
```

- All URLs are HTTPS, never SSH (some collaborators don't have SSH keys configured).
- `path` is lowercase; `url` preserves original casing.
- The `[submodule "..."]` name matches the path.

Example:

```ini
[submodule "grafana/loki"]
	path = grafana/loki
	url = https://github.com/grafana/loki.git
[submodule "ot-container-kit/redis-operator"]
	path = ot-container-kit/redis-operator
	url = https://github.com/OT-CONTAINER-KIT/redis-operator.git
```

## Troubleshooting

### Empty submodule directory after clone

Submodules weren't initialized:

```bash
git submodule update --init --recursive
```

### "fatal: No submodule mapping found in .gitmodules for path"

`.gitmodules` is missing an entry for that path, or the path doesn't match. Check the `[submodule]` name and `path` values match the actual directory.

### Submodule on detached HEAD

This is normal — submodules check out a specific commit, not a branch. To move it forward:

```bash
cd <vendor>/<repo>
git checkout origin/main
cd ~/github.com/alpinetmpl/docs
git add <vendor>/<repo>
```

### Push rejected because remote has new commits

```bash
git pull --rebase origin main
git push origin main
```

Do not force-push. If the rebase has conflicts in `.gitmodules`, keep both submodule entries — they're additive.

### Slow clone for a large submodule

Use `--depth 1`:

```bash
git submodule update --init --depth 1 <vendor>/<repo>
```

This loses git history but gets the current docs in seconds rather than minutes.

### `git submodule update --remote` did nothing

The submodule's `branch` may not be set in `.gitmodules`. By default `--remote` updates to the upstream's default branch (usually `main` or `master`). If you need to track a specific branch:

```ini
[submodule "<vendor>/<repo>"]
	path = <vendor>/<repo>
	url = https://...
	branch = release-2.x
```
