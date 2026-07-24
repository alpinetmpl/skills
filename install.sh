#!/usr/bin/env bash
# Installs alpinetmpl/skills into ~/.claude/skills as per-skill symlinks so
# shared skills coexist with any personal skills the dev already has. Also adds
# a SessionStart hook that re-runs this script on every Claude Code session,
# so new skills appear automatically and the hook itself self-heals if it
# drifts or goes missing. Idempotent — safe to re-run.
#
# Opt out of the hook with SKILLS_SKIP_HOOK=1.

set -euo pipefail

REPO_URL="${SKILLS_REPO_URL:-https://github.com/alpinetmpl/skills.git}"
CLONE_DIR="${SKILLS_CLONE_DIR:-$HOME/github.com/alpinetmpl/skills}"
SKILLS_DIR="$HOME/.claude/skills"
SETTINGS_FILE="$HOME/.claude/settings.json"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

# 1. Clone (or update) the repo
if [ -d "$CLONE_DIR/.git" ]; then
  echo "Repo present at $CLONE_DIR — pulling latest..."
  git -C "$CLONE_DIR" pull --ff-only
else
  echo "Cloning $REPO_URL to $CLONE_DIR..."
  mkdir -p "$(dirname "$CLONE_DIR")"
  git clone "$REPO_URL" "$CLONE_DIR"
fi

# 2. Migrate from an older whole-folder symlink at ~/.claude/skills, if present
if [ -L "$SKILLS_DIR" ]; then
  current="$(readlink "$SKILLS_DIR")"
  if [ "$current" = "$CLONE_DIR" ]; then
    echo "Removing legacy whole-folder symlink at $SKILLS_DIR — will re-link per skill."
    rm "$SKILLS_DIR"
  else
    echo "ERROR: $SKILLS_DIR is a symlink to $current (not managed by this script). Move it aside and re-run." >&2
    exit 1
  fi
fi

mkdir -p "$SKILLS_DIR"

# 3. Link each skill from the repo into ~/.claude/skills/<skill>
#    A "skill" = a top-level directory in the repo containing SKILL.md
added=0
already=0
backed_up=()

for skill_path in "$CLONE_DIR"/*/; do
  [ -d "$skill_path" ] || continue
  [ -f "$skill_path/SKILL.md" ] || continue
  skill_path="${skill_path%/}"
  skill_name="$(basename "$skill_path")"
  target="$SKILLS_DIR/$skill_name"

  if [ -L "$target" ]; then
    current="$(readlink "$target")"
    if [ "$current" = "$skill_path" ]; then
      already=$((already + 1))
      continue
    fi
    # Existing symlink points somewhere else. If it's inside our clone dir
    # (e.g. stale), replace silently. Otherwise back it up.
    case "$current" in
      "$CLONE_DIR"/*)
        rm "$target"
        ;;
      *)
        backup="${target}.backup.${TIMESTAMP}"
        mv "$target" "$backup"
        backed_up+=("$skill_name (was symlink to $current; saved as $(basename "$backup"))")
        ;;
    esac
  elif [ -e "$target" ]; then
    backup="${target}.backup.${TIMESTAMP}"
    mv "$target" "$backup"
    backed_up+=("$skill_name (was personal skill; saved as $(basename "$backup"))")
  fi

  ln -s "$skill_path" "$target"
  added=$((added + 1))
done

# 4. Clean up stale shared-skill symlinks: links pointing into the clone dir
#    whose target no longer exists. Personal skills and symlinks pointing
#    elsewhere are left untouched.
stale=0
shopt -s nullglob
for link in "$SKILLS_DIR"/*; do
  [ -L "$link" ] || continue
  current="$(readlink "$link")"
  case "$current" in
    "$CLONE_DIR"/*)
      if [ ! -e "$current" ]; then
        rm "$link"
        stale=$((stale + 1))
      fi
      ;;
  esac
done
shopt -u nullglob

echo "Shared skills: $added linked ($already already up to date), $stale stale link(s) removed."
if [ "${#backed_up[@]}" -gt 0 ]; then
  echo "Backed up existing entries (shared version now wins):"
  for entry in "${backed_up[@]}"; do
    echo "  - $entry"
  done
fi

# 5. Add the SessionStart hook to ~/.claude/settings.json (idempotent)
if [ "${SKILLS_SKIP_HOOK:-0}" = "1" ]; then
  echo "SKILLS_SKIP_HOOK=1 set — skipping hook install."
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "WARNING: python3 not found; skipping hook install. Add it manually to $SETTINGS_FILE." >&2
  exit 0
fi

CLONE_DIR="$CLONE_DIR" SETTINGS_FILE="$SETTINGS_FILE" TIMESTAMP="$TIMESTAMP" python3 <<'PY'
import json, os, sys, shutil

path = os.environ["SETTINGS_FILE"]
clone_dir = os.environ["CLONE_DIR"]
ts = os.environ["TIMESTAMP"]
marker = "alpinetmpl/skills"
# On each new Claude Code session, re-run install.sh: pulls the repo,
# links any new skills, cleans up stale links, self-heals this hook.
desired_command = f"bash {clone_dir}/install.sh >/dev/null 2>&1 || true"

data = {}
if os.path.exists(path):
    with open(path) as f:
        text = f.read().strip()
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"ERROR: {path} is not valid JSON ({e}); refusing to modify.", file=sys.stderr)
            sys.exit(1)

hooks = data.setdefault("hooks", {})
session_start = hooks.setdefault("SessionStart", [])

existing = None
for group in session_start:
    for h in group.get("hooks", []):
        if marker in h.get("command", ""):
            existing = h
            break
    if existing:
        break

if existing is not None and existing.get("type") == "command" and existing.get("command") == desired_command:
    print(f"SessionStart hook already up to date in {path}.")
    sys.exit(0)

# About to modify — back up first
if os.path.exists(path):
    shutil.copy(path, f"{path}.backup.{ts}")

if existing is not None:
    existing["type"] = "command"
    existing["command"] = desired_command
    msg = "Updated"
else:
    session_start.append({"hooks": [{"type": "command", "command": desired_command}]})
    msg = "Added"

os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"{msg} SessionStart self-update hook in {path}")
PY
