#!/usr/bin/env bash
# check-shared-drift.sh — guardrail for the flat _shared/ pool.
#
# Run before pushing. It is a run-script, not a CI gate (this repo has no CI).
# Four checks:
#   1. Dangling symlinks anywhere in the repo (excl. .git).
#   2. Copy-instead-of-symlink drift: a skill-local REAL file whose contents are
#      byte-identical to a file in _shared/ (it should be a symlink into the pool).
#   3. Cited-path resolution: every references/… and scripts/… path a live SKILL.md
#      points at actually resolves.
#   4. Cross-link resolution: every relative markdown link INSIDE a reference doc
#      resolves from each skill tree that pulls it in. Catches the failure mode where
#      a pooled doc links a sibling that a per-file-symlink consumer didn't also pull
#      (e.g. a pooled doc links a sibling in a subject subfolder, but a skill only
#      symlinked one file from that subfolder). This is why cohesive cross-linking
#      subject subfolders are consumed whole-dir, not per-file.
#
# Exit 0 = clean; non-zero = at least one check failed. Usage: tools/check-shared-drift.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Space-separated allowlist for check 3: paths a SKILL.md "cites" that aren't
# committed files — runtime-created paths, or prose the path regex false-matches
# ("scripts/cookie" comes from "strips nav/footer/scripts/cookie banners").
RUNTIME_ALLOWLIST="scripts/cookie"

rc=0
note() { printf '  %s\n' "$*"; }

# --- Check 1: dangling symlinks -------------------------------------------------
echo "[1/4] dangling symlinks"
dangling=0
while IFS= read -r link; do
  if [ ! -e "$link" ]; then note "DANGLING: $link -> $(readlink "$link")"; dangling=1; rc=1; fi
done < <(find . -path ./.git -prune -o -type l -print)
[ "$dangling" -eq 0 ] && note "ok — none"

# --- Check 2: copy-instead-of-symlink drift -------------------------------------
echo "[2/4] shared-content drift (skill-local real file == a pooled file)"
hash_of() { shasum "$1" 2>/dev/null | awk '{print $1}'; }
# Build: sha -> _shared path (real files only; symlinks excluded by -type f w/o -L)
declare -a SHARED_SHAS=() SHARED_PATHS=()
while IFS= read -r f; do
  SHARED_SHAS+=("$(hash_of "$f")"); SHARED_PATHS+=("$f")
done < <(find _shared -type f ! -name README.md)
drift=0
# For each real file inside a skill's references/ or scripts/, compare against the pool.
while IFS= read -r f; do
  fsha="$(hash_of "$f")"
  for i in "${!SHARED_SHAS[@]}"; do
    if [ "$fsha" = "${SHARED_SHAS[$i]}" ]; then
      note "DRIFT: $f is a byte-identical copy of ${SHARED_PATHS[$i]} — symlink it instead"
      drift=1; rc=1; break
    fi
  done
done < <(find . -path ./.git -prune -o -path './_shared' -prune -o \
              \( -path '*/references/*' -o -path '*/scripts/*' \) -type f -print)
[ "$drift" -eq 0 ] && note "ok — no duplicated shared content"

# --- Check 3: cited-path resolution ---------------------------------------------
echo "[3/4] cited reference/script paths resolve"
missing=0
for skillmd in */SKILL.md; do
  skill="${skillmd%/SKILL.md}"
  while IFS= read -r p; do
    p="${p%/}"; p="${p%.}"; p="${p%,}"   # strip trailing slash / sentence punctuation
    case " $RUNTIME_ALLOWLIST " in *" $p "*) continue;; esac
    [ -e "$skill/$p" ] || { note "UNRESOLVED: $skill/$p (cited in $skillmd)"; missing=1; rc=1; }
  done < <(grep -oE '(references|scripts)/[A-Za-z0-9_./-]+' "$skillmd" | sort -u)
done
[ "$missing" -eq 0 ] && note "ok — all cited paths resolve"

# --- Check 4: internal cross-link resolution (per skill tree) --------------------
# For each skill, read every reference doc AS SEEN from that skill's tree (-L follows
# symlinks into _shared) and resolve its relative links relative to that skill-tree
# location. A pooled doc that links a sibling the consumer didn't pull in fails here.
echo "[4/4] internal cross-links resolve from each consuming skill"
xbroken=0
for skillmd in */SKILL.md; do
  skill="${skillmd%/SKILL.md}"
  [ -d "$skill/references" ] || continue
  while IFS= read -r f; do
    dir="$(dirname "$f")"
    grep -oE '\]\([A-Za-z0-9_][A-Za-z0-9_./-]*\)' "$f" 2>/dev/null | sed -E 's/^\]\(//; s/\)$//' | while IFS= read -r lnk; do
      case "$lnk" in http*|\#*|mailto:*) continue;; esac
      [ -e "$dir/$lnk" ] || echo "  CROSSLINK-BROKEN: $f -> $lnk"
    done
  done < <(find -L "$skill/references" -name '*.md' -type f 2>/dev/null)
done > /tmp/_xlink_$$ 2>/dev/null
if [ -s /tmp/_xlink_$$ ]; then cat /tmp/_xlink_$$; xbroken=1; rc=1; else note "ok — all internal cross-links resolve"; fi
rm -f /tmp/_xlink_$$

echo
[ "$rc" -eq 0 ] && echo "PASS — _shared pool is consistent." || echo "FAIL — see findings above."
exit "$rc"
