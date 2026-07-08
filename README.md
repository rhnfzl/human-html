# human-html

[![Release](https://img.shields.io/github/v/release/rhnfzl/human-html)](https://github.com/rhnfzl/human-html/releases)
[![License](https://img.shields.io/github/license/rhnfzl/human-html)](LICENSE)
<!-- Listed at https://skills.sh/rhnfzl/human-html; re-add this badge once its endpoint stops serving "resource not found" (install-count data lags the listing page):
[![skills.sh](https://skills.sh/b/rhnfzl/human-html)](https://skills.sh/rhnfzl/human-html)
-->


Make the next document a teammate actually reads.

An Agent Skill for the documents agents produce for humans: plans, reviews, architecture explainers, research, decisions, prototypes, status reports, postmortems. Each one lands as a single self-contained HTML page (plain-language summary, a diagram in every comparison, color-coded risks) instead of a Markdown wall that gets skimmed and rubber-stamped. An offline validator enforces that shape as a contract. See the [live gallery](https://rhnfzl.github.io/human-html/) of all nine kinds.

## Quickstart (30 seconds)

One command, and it auto-detects your installed agents; that is the whole setup:

```bash
npx skills add rhnfzl/human-html
```

Then ask your agent for a plan, review, or postmortem. The skill has the agent scaffold, validate, and index everything; the `docs/human-html/` lane appears in a workspace with the first artifact. Optional: run `python3 <skill-dir>/human_html_artifacts.py init` once per workspace to seed a glossary, or drive `new` / `check` / `index` by hand; `<skill-dir>` is wherever the installer put the skill (e.g. `~/.claude/skills/human-html`). Also installable via `npx openskills install rhnfzl/human-html`, Claude Code's `/plugin marketplace add rhnfzl/human-html`, or a plain clone + symlink.

## Why this exists

1. **Humans skim.** A long Markdown plan gets a rubber stamp, not a review. These artifacts are built for a reader with ten minutes: summary first, visuals in every comparison, verdicts answer-first, risks in color.
2. **Document quality decays.** Style intentions vanish the moment an agent regenerates a file. Here the shape is a validated contract (`check`): four rules block, the rest warn, every rule suppressible per artifact.
3. **Sharing tools assume upload.** Default is local; nothing leaves your machine. Sharing is a menu: GitHub Pages (artifacts are already static HTML), an optional bring-your-own-bucket S3 script with zero defaults, or any static host. Note: Mermaid blocks load a CDN at view time; render to inline SVG for fully-offline artifacts.

The contract itself is stolen craft, in the [Steal Like an Artist](https://austinkleon.com/steal/) sense: the inverted pyramid, postmortem timelines, C4 diagrams, first-use glossing. The nine canonical examples exist to be stolen from too, and so does the repo: fork it, re-theme it, suppress what you disagree with.

## What's in the box

| Piece | What it does |
|---|---|
| `SKILL.md` | The contract: rules, per-kind scaffolds, illustration menu, hook wiring |
| `human_html_artifacts.py` | `init` / `new` / `check` / `index` / `deps` |
| `hooks/` | Optional advisory nudge + gallery autoindex; advisory-only, always exit 0 |
| `examples/` | Nine canonical artifacts, one per kind, warning-free |
| `references/` | Adoptable patterns, diagram decision tree, workflow integrations |
| `scripts/publish-s3.sh` | Optional S3 sharing; requires `HUMAN_HTML_S3_BUCKET`, no defaults |

## Requirements

Python 3.11+ (stdlib only, no dependencies; older 3.x generally works but is untested). Optional: `jq` for the hooks, `mmdc` for offline diagram rendering, `excalidraw-mcp` for hand-drawn diagrams.

## Trust

No postinstall scripts, no telemetry, no network calls in the core loop; the validator runs fully offline. Review `SKILL.md` before installing, as with any skill.

Claude Code, Codex, OpenCode, and Gemini CLI read Agent Skills natively; Cursor and others via the universal installers.

## License

[MIT](LICENSE)
