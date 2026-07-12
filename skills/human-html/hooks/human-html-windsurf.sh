#!/usr/bin/env bash
# Adapt Windsurf hook JSON to the agent-neutral human-html hook shape.

set -u

MODE="${1:-}"
INPUT="$(cat)"

command -v jq >/dev/null 2>&1 || exit 0

case "$MODE" in
  advisory)
    TARGET="human-html-advisory.sh"
    TOOL_NAME="Write"
    ;;
  autoindex)
    TARGET="human-html-autoindex.sh"
    case "$(jq -r '.agent_action_name // empty' <<<"$INPUT")" in
      post_write_code) TOOL_NAME="Write" ;;
      post_run_command) TOOL_NAME="Shell" ;;
      *) exit 0 ;;
    esac
    ;;
  *) exit 0 ;;
esac

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
jq -c --arg tool "$TOOL_NAME" '{
  tool_name: $tool,
  cwd: (.tool_info.cwd // env.PWD),
  tool_input: {
    file_path: (.tool_info.file_path // ""),
    command: (.tool_info.command_line // "")
  }
}' <<<"$INPUT" | "$HOOK_DIR/$TARGET" || true
exit 0
