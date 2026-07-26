#!/usr/bin/env python3
"""Validate the shipped canonical examples against the content contract.

The examples are what an agent copies from: SKILL.md tells it to read the canonical
example for a kind before writing a new artifact of that kind. So an example that
violates the contract is worse than a documentation bug, because the example wins. This
runs in CI on every push and pull request, and again at release time.

Two things it checks that the unit suite does not:

1. **Nothing is grandfathered.** Each example is validated under its OWN
   `artifact-created` date, which is the honest test. But an artifact dated before
   `RULES_EFFECTIVE_DATE` is exempt from the whole content contract, so a shipped example
   with a stale date would pass by never being checked at all. That is a hole, not a pass.
2. **Warnings are surfaced**, as GitHub annotations when running in Actions. The unit
   suite only fails on errors, which is right for a test but hides the drift that shows up
   as a warning first.

Usage: python3 .github/scripts/check_examples.py [examples-dir]
Exits 1 on any error or grandfathered example; warnings never fail the run.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills/human-html/human_html_artifacts.py"
IN_ACTIONS = bool(os.environ.get("GITHUB_ACTIONS"))


def _load_validator():
    spec = importlib.util.spec_from_file_location("hha", SCRIPT)
    if spec is None or spec.loader is None:
        sys.exit(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the script defines @dataclass types, and dataclasses resolves
    # field types via sys.modules[cls.__module__].
    sys.modules["hha"] = module
    spec.loader.exec_module(module)
    return module


def _say(level: str, message: str) -> None:
    """Annotate in Actions, stay readable in a terminal."""
    print(f"::{level}::{message}" if IN_ACTIONS else f"{level.upper()}: {message}")


def main(argv: list[str]) -> int:
    hha = _load_validator()
    examples_dir = Path(argv[1]) if len(argv) > 1 else REPO / "skills/human-html/examples"
    paths = sorted(examples_dir.glob("*.html"))
    if not paths:
        _say("error", f"no examples found in {examples_dir}")
        return 1

    errors = warnings = 0
    for path in paths:
        # relative_to raises for a directory outside the repo, which the optional argv
        # form allows. The path is only used for display, so fall back to it whole.
        try:
            rel = path.relative_to(REPO)
        except ValueError:
            rel = path
        text = path.read_text(encoding="utf-8")
        parser = hha.ArtifactHTMLParser()
        parser.feed(text)
        created = parser.meta.get("artifact-created", "")
        kind = parser.meta.get("artifact-kind", "")

        if not hha._artifact_in_force(created):
            _say(
                "error",
                f"{rel}: artifact-created '{created}' is before RULES_EFFECTIVE_DATE "
                f"({hha.RULES_EFFECTIVE_DATE}), so the content contract does not apply to "
                "it. A shipped example must be held to the contract it demonstrates.",
            )
            errors += 1
            continue

        found_errors, found_warnings = hha.content_shape_violations(
            rel, text, created, REPO, kind
        )
        for message in found_errors:
            _say("error", message)
            errors += 1
        for message in found_warnings:
            _say("warning", message)
            warnings += 1

    print(f"checked {len(paths)} examples: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
