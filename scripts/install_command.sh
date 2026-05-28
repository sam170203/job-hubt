#!/usr/bin/env bash
# One-time installer: registers `job-hunt` as a shell command.
# Idempotent — re-running does not duplicate the line in ~/.zshrc.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOBHUNT_BIN="$PROJECT_DIR/bin/job-hunt"
ZSHRC="$HOME/.zshrc"

if [ ! -x "$JOBHUNT_BIN" ]; then
  echo "ERROR: $JOBHUNT_BIN not found or not executable." >&2
  exit 1
fi

MARKER="# job-hunt CLI (installed by install_command.sh)"
LINE="alias job-hunt='$JOBHUNT_BIN'"

if [ -f "$ZSHRC" ] && grep -qF "$MARKER" "$ZSHRC"; then
  echo "Already installed in $ZSHRC."
else
  {
    echo ""
    echo "$MARKER"
    echo "$LINE"
  } >> "$ZSHRC"
  echo "Added to $ZSHRC:"
  echo "  $LINE"
fi

echo ""
echo "Done. Run 'source ~/.zshrc' or open a new terminal, then type:"
echo "  job-hunt"
