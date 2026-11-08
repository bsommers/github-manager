#!/usr/bin/env bash
# Install GMAC as a global `gmac` command (via uv tool). Idempotent; safe to re-run to upgrade.
#   scripts/install.sh                 editable install from this clone (code changes apply immediately)
#   scripts/install.sh --git [REF]     install from GitHub instead (no clone needed; REF = branch/tag)
#   scripts/install.sh --install-uv    also install uv first, using Astral's official installer
#   scripts/install.sh --uninstall     remove the gmac command (keeps your config and keychain entries)
#   scripts/install.sh --dry-run       print what would run, change nothing
# Never reads or writes credentials; login is delegated to gh/glab (`gmac auth login`).
set -euo pipefail

REPO_URL="https://github.com/bsommers/github-manager"
MODE=editable REF="" DRY=0 GET_UV=0 UNINSTALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --git)        MODE=git; if [ "${2:-}" ] && [ "${2#-}" = "$2" ]; then REF="$2"; shift; fi ;;
    --install-uv) GET_UV=1 ;;
    --uninstall)  UNINSTALL=1 ;;
    --dry-run)    DRY=1 ;;
    -h|--help)    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)            echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

say() { printf '%s\n' "$*"; }
run() { if [ "$DRY" = 1 ]; then say "[dry-run] $*"; else "$@"; fi; }

if ! command -v uv >/dev/null 2>&1; then
  if [ "$GET_UV" = 1 ]; then
    say "Installing uv with Astral's official installer (https://astral.sh/uv)..."
    if [ "$DRY" = 1 ]; then say "[dry-run] curl -LsSf https://astral.sh/uv/install.sh | sh"
    else curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; fi
  else
    say "uv is required (it also provides Python and all dependencies)."
    say "Install it from https://docs.astral.sh/uv/ or re-run with --install-uv."
    [ "$DRY" = 1 ] || exit 1
  fi
fi

if [ "$UNINSTALL" = 1 ]; then
  run uv tool uninstall gmac
  say "Removed. Your config and any stored tokens were left untouched."
  exit 0
fi

if [ "$MODE" = git ]; then
  SRC="git+$REPO_URL${REF:+@$REF}"
  run uv tool install --force "$SRC"
else
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  [ -f "$ROOT/pyproject.toml" ] || { say "run from a clone, or use --git" >&2; exit 1; }
  run uv tool install --editable --force "$ROOT"
fi

[ "$DRY" = 1 ] && exit 0

BIN_DIR="$(uv tool dir --bin 2>/dev/null || echo "$HOME/.local/bin")"
if ! command -v gmac >/dev/null 2>&1; then
  say ""
  say "gmac is installed in $BIN_DIR but that is not on your PATH."
  say "Run:  uv tool update-shell   then open a new terminal."
  exit 0
fi

say ""
say "Installed: $(command -v gmac)"
for cli in gh glab; do
  command -v "$cli" >/dev/null 2>&1 && say "found $cli (gmac reuses its login)" \
    || say "note: $cli not found; install it for browser login, or use env tokens / gmac auth login --token"
done
say ""
gmac auth status || true
say ""
say "Next:  gmac auth login      # if a provider shows 'none'"
say "       gmac sources add <your-github-user>"
say "       gmac tui | gmac gui | gmac repos"
