#!/usr/bin/env bash
# Cursor preToolUse wrapper for human-html-advisory.sh.
#
# Cursor surfaces hook guidance via JSON stdout (agent_message), not stderr.
# The core advisory hook stays agent-neutral and prints to stderr for
# Claude Code and Codex.

set -u

INPUT="$(cat)"
# Resolve this wrapper's real path; the core hook lives in the same directory.
HOOK_SELF="$(readlink -f "${BASH_SOURCE[0]:-$0}" 2>/dev/null || echo "${BASH_SOURCE[0]:-$0}")"
CORE_HOOK="$(cd "$(dirname "$HOOK_SELF")" 2>/dev/null && pwd)/human-html-advisory.sh"
stderr_file="$(mktemp "${TMPDIR:-/tmp}/human-html-advisory.XXXXXX")"

cleanup() {
  rm -f "$stderr_file"
}
trap cleanup EXIT

if [ ! -x "$CORE_HOOK" ]; then
  exit 0
fi

HOOK_CWD=""
if command -v jq >/dev/null 2>&1; then
  HOOK_CWD=$(jq -r '.cwd // empty' <<<"$INPUT")
fi

echo "$INPUT" | env CURSOR_PROJECT_DIR="${CURSOR_PROJECT_DIR:-$HOOK_CWD}" \
  "$CORE_HOOK" 2>"$stderr_file" || true

if [ ! -s "$stderr_file" ]; then
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  cat "$stderr_file" >&2
  exit 0
fi

jq -n --rawfile msg "$stderr_file" '{agent_message: $msg}'
exit 0
