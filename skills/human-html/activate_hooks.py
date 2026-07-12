#!/usr/bin/env python3
"""Register human-html hooks in supported global agent settings."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Invalid JSON in {path}: root must be an object")
    return value


def _upsert_owned_hook(entries: list, entry: dict, marker: str, nested: bool = False) -> None:
    def command(item: dict) -> str:
        hooks = item.get("hooks", []) if nested else [item]
        return " ".join(str(hook.get("command", "")) for hook in hooks if isinstance(hook, dict))

    matches = [index for index, item in enumerate(entries) if isinstance(item, dict) and marker in command(item)]
    if not matches:
        entries.append(entry)
        return
    entries[matches[0]] = entry
    for index in reversed(matches[1:]):
        del entries[index]


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(data, indent=2) + "\n"
    if not path.exists() or path.read_text() != rendered:
        path.write_text(rendered)


def activate(home: Path, skill_dir: Path) -> list[Path]:
    hooks_dir = skill_dir.resolve() / "hooks"
    advisory = shlex.quote(str(hooks_dir / "human-html-advisory.sh"))
    cursor_advisory = shlex.quote(str(hooks_dir / "human-html-advisory-cursor.sh"))
    autoindex = shlex.quote(str(hooks_dir / "human-html-autoindex.sh"))
    windsurf = shlex.quote(str(hooks_dir / "human-html-windsurf.sh"))

    nested_agents = [
        (home / ".claude/settings.json", "Edit|Write|MultiEdit|NotebookEdit", "Edit|Write|MultiEdit|Bash"),
        (home / ".codex/hooks.json", "Edit|Write|MultiEdit|NotebookEdit|StrReplace", "Edit|Write|MultiEdit|StrReplace|apply_patch|Bash|Shell|exec_command|functions\\.exec_command"),
    ]
    written = []
    for path, pre_matcher, post_matcher in nested_agents:
        data = _load(path)
        hooks = data.setdefault("hooks", {})
        pre = hooks.setdefault("PreToolUse", [])
        post = hooks.setdefault("PostToolUse", [])
        _upsert_owned_hook(pre, {"matcher": pre_matcher, "hooks": [{"type": "command", "command": advisory, "timeout": 5}]}, "human-html-advisory.sh", True)
        _upsert_owned_hook(post, {"matcher": post_matcher, "hooks": [{"type": "command", "command": autoindex, "timeout": 10}]}, "human-html-autoindex.sh", True)
        _write(path, data)
        written.append(path)

    cursor_path = home / ".cursor/hooks.json"
    cursor = _load(cursor_path)
    cursor.setdefault("version", 1)
    hooks = cursor.setdefault("hooks", {})
    _upsert_owned_hook(hooks.setdefault("preToolUse", []), {"command": cursor_advisory, "matcher": "Edit|Write|MultiEdit|NotebookEdit|StrReplace", "timeout": 5}, "human-html-advisory-cursor.sh")
    _upsert_owned_hook(hooks.setdefault("postToolUse", []), {"command": autoindex, "matcher": "Edit|Write|MultiEdit|StrReplace|Shell", "timeout": 10}, "human-html-autoindex.sh")
    _write(cursor_path, cursor)
    written.append(cursor_path)

    windsurf_path = home / ".codeium/windsurf/hooks.json"
    windsurf_data = _load(windsurf_path)
    hooks = windsurf_data.setdefault("hooks", {})
    _upsert_owned_hook(hooks.setdefault("pre_write_code", []), {"command": f"{windsurf} advisory", "show_output": True}, "human-html-windsurf.sh advisory")
    for event in ("post_write_code", "post_run_command"):
        _upsert_owned_hook(hooks.setdefault(event, []), {"command": f"{windsurf} autoindex", "show_output": False}, "human-html-windsurf.sh autoindex")
    _write(windsurf_path, windsurf_data)
    written.append(windsurf_path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    args = parser.parse_args()
    for path in activate(args.home, Path(__file__).parent):
        print(f"configured {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
