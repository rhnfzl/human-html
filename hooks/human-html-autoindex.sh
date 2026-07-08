#!/usr/bin/env bash
# PostToolUse autoindex hook (part of the human-html skill).
#
# Regenerates docs/human-html/index.html after direct editor writes, Codex
# apply_patch events, and shell commands that mention the human-html script or
# artifact directory. Editor writes are path-filtered to any
# <workspace>/docs/human-html/**/*.html file. apply_patch is conservatively indexed
# whenever docs/human-html/ exists because Codex patch events do not always
# expose a single target path.
#
# Contract:
#   * Always exit 0 (the script's own check would have failed loudly if
#     the artifact was malformed; we never block the upstream tool call).
#   * Resolves workspace root from $CLAUDE_PROJECT_DIR -> $CURSOR_PROJECT_DIR
#     -> $CODEX_WORKSPACE -> hook JSON .cwd -> pwd.
#
# Pair: hooks/human-html-advisory.sh (PreToolUse nudge for HIL-shaped MD).

set -u

INPUT="$(cat)"

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

HOOK_CWD=$(jq -r '.cwd // empty' <<<"$INPUT")
WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-${CODEX_WORKSPACE:-${HOOK_CWD:-$(pwd)}}}}"
ARTIFACT_DIR="$WORKSPACE_ROOT/docs/human-html"
# Resolve this hook's real path so SCRIPT_PATH points at the installed skill
# copy, wherever it lives (this hook is at <skill-dir>/hooks/).
HOOK_SELF="$(readlink -f "${BASH_SOURCE[0]:-$0}" 2>/dev/null || echo "${BASH_SOURCE[0]:-$0}")"
SKILL_DIR="$(cd "$(dirname "$HOOK_SELF")/.." 2>/dev/null && pwd)"
SCRIPT_PATH="$SKILL_DIR/human_html_artifacts.py"

TOOL_NAME=$(jq -r '.tool_name // empty' <<<"$INPUT")
TARGET_PATH=$(jq -r '.tool_input.file_path // .tool_input.path // empty' <<<"$INPUT")
COMMAND_TEXT=$(jq -r '.command // .tool_input.command // .tool_input.cmd // .tool_input.shell_command // empty' <<<"$INPUT")

case "$TOOL_NAME" in
  Write|Edit|MultiEdit|StrReplace|apply_patch|Bash|Shell|exec_command|functions.exec_command) : ;;
  *) exit 0 ;;
esac

if [ "$TOOL_NAME" = "apply_patch" ]; then
  [ -d "$ARTIFACT_DIR" ] || exit 0
  [ -f "$SCRIPT_PATH" ] || exit 0
  (cd "$WORKSPACE_ROOT" && python3 "$SCRIPT_PATH" index) >&2 2>&1 || true
  exit 0
fi

case "$TOOL_NAME" in
  Bash|Shell|exec_command|functions.exec_command)
    case "$COMMAND_TEXT" in
      *human_html_artifacts.py*|*docs/human-html*) : ;;
      *) exit 0 ;;
    esac
    [ -d "$ARTIFACT_DIR" ] || exit 0
    [ -f "$SCRIPT_PATH" ] || exit 0
    (cd "$WORKSPACE_ROOT" && python3 "$SCRIPT_PATH" index) >&2 2>&1 || true
    exit 0
    ;;
esac

[ -z "$TARGET_PATH" ] && exit 0

if [[ "$TARGET_PATH" != /* ]]; then
  TARGET_PATH="$WORKSPACE_ROOT/$TARGET_PATH"
fi

case "$TARGET_PATH" in
  "$ARTIFACT_DIR"/*) : ;;
  *) exit 0 ;;
esac

case "$TARGET_PATH" in
  *.html) : ;;
  *) exit 0 ;;
esac

# Skip the root gallery itself so we don't loop.
case "$TARGET_PATH" in
  "$ARTIFACT_DIR/index.html") exit 0 ;;
esac

[ -f "$SCRIPT_PATH" ] || exit 0

# Regenerate the gallery. Failures print to stderr but never block.
(cd "$WORKSPACE_ROOT" && python3 "$SCRIPT_PATH" index) >&2 2>&1 || true

exit 0
