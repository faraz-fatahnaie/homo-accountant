#!/usr/bin/env bash
# =============================================================================
# Homo Accountant — fetch the final bundle, compare with GitHub, and sync.
#
# Run on YOUR machine (where the GitHub account/SSH is configured).
#
# Usage:
#   ./scripts/sync-github.sh --bundle homo-accountant-history.bundle
#   ./scripts/sync-github.sh --bundle ../homo-accountant-history.bundle \
#       --repo git@github.com:faraz-fatahnaie/homo-accountant.git
#
# Behavior:
#   * clones the bundle into ./homo-accountant (fresh, disposable copy)
#   * adds the GitHub remote (never touches any other local repo)
#   * prints local (bundle) HEAD vs GitHub origin/main and a verdict:
#       - UP-TO-DATE   everything matches
#       - BEHIND       GitHub is behind -> offers push
#       - DIVERGED     histories differ -> needs --force to overwrite
#   * with --push, automatically pushes when behind (force-with-lease only
#     when you also pass --force for a diverged remote)
# =============================================================================
set -euo pipefail

BUNDLE=""
REPO_URL="git@github.com:faraz-fatahnaie/homo-accountant.git"
DO_PUSH=0
DO_FORCE=0

usage() { sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle) BUNDLE="${2:?--bundle requires a path}"; shift 2 ;;
    --repo)   REPO_URL="${2:?--repo requires a URL}"; shift 2 ;;
    --push)   DO_PUSH=1; shift ;;
    --force)  DO_FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$BUNDLE" ]] || { echo "--bundle is required" >&2; usage >&2; exit 2; }
[[ -f "$BUNDLE" ]] || { echo "bundle not found: $BUNDLE" >&2; exit 1; }

log()  { printf '\033[1;34m[sync]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[sync] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"; }
require_cmd git

# ---------------------------------------------------------------------------
# 1. Fresh clone from the bundle (disposable copy — never modifies other repos)
# ---------------------------------------------------------------------------
WORKDIR="homo-accountant"
if [[ -d "$WORKDIR/.git" ]]; then
  log "reusing existing $WORKDIR (git fetch from bundle)"
  git -C "$WORKDIR" fetch -q "$(pwd)/$BUNDLE" main 2>/dev/null || {
    rm -rf "$WORKDIR"
    log "re-cloning bundle -> $WORKDIR"
    git clone -q "$BUNDLE" "$WORKDIR"
  }
else
  rm -rf "$WORKDIR"
  log "cloning bundle -> $WORKDIR"
  git clone -q "$BUNDLE" "$WORKDIR"
fi
cd "$WORKDIR"

# ---------------------------------------------------------------------------
# 2. GitHub remote
#    NOTE: `git clone <bundle>` auto-sets origin to the BUNDLE file path.
#    Always point origin at the real GitHub URL, or the comparison would
#    compare the bundle against itself (false UP-TO-DATE).
# ---------------------------------------------------------------------------
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
log "remote set: origin $REPO_URL"

# ---------------------------------------------------------------------------
# 3. Compare
# ---------------------------------------------------------------------------
LOCAL_HEAD="$(git rev-parse HEAD)"
REMOTE_HEAD="$(git ls-remote origin refs/heads/main | awk '{print $1}')"

log "bundle  (local)  main = $LOCAL_HEAD"
log "github (remote)  main = ${REMOTE_HEAD:-<none>}"

if [[ -z "$REMOTE_HEAD" ]]; then
  log "verdict: GitHub has no main branch yet (fresh repo)"
  if [[ "$DO_PUSH" -eq 1 ]]; then
    git push -u origin main
  else
    log "run with --push to create it:  ./scripts/sync-github.sh --bundle $BUNDLE --push"
  fi
  exit 0
fi

if [[ "$LOCAL_HEAD" == "$REMOTE_HEAD" ]]; then
  log "verdict: UP-TO-DATE — GitHub main matches the bundle exactly."
  git log --oneline -1
  exit 0
fi

# is remote an ancestor of local? (behind => fast-forward push possible)
if git merge-base --is-ancestor "$REMOTE_HEAD" "$LOCAL_HEAD" 2>/dev/null; then
  log "verdict: BEHIND — GitHub main ($REMOTE_HEAD) is older than the bundle ($LOCAL_HEAD)"
  if [[ "$DO_PUSH" -eq 1 ]]; then
    git push -u origin main
    log "pushed. re-check:"
    git ls-remote origin refs/heads/main
  else
    log "run with --push to fast-forward:  ./scripts/sync-github.sh --bundle $BUNDLE --push"
  fi
  exit 0
fi

# otherwise histories diverged (GitHub has commits the bundle does not)
log "verdict: DIVERGED — GitHub main and the bundle share no direct ancestry."
if [[ "$DO_FORCE" -eq 1 && "$DO_PUSH" -eq 1 ]]; then
  log "overwriting GitHub main with the bundle (force-with-lease)…"
  git push --force-with-lease origin main
  log "pushed. re-check:"
  git ls-remote origin refs/heads/main
else
  log "to overwrite GitHub main with the bundle, run with BOTH: --push --force"
  exit 1
fi
