# human-html

[![Release](https://img.shields.io/github/v/release/rhnfzl/human-html)](https://github.com/rhnfzl/human-html/releases)
[![License](https://img.shields.io/github/license/rhnfzl/human-html)](LICENSE)
[![Python](https://img.shields.io/badge/python-stdlib%20only-3776ab)](#requirements)
[![Examples](https://img.shields.io/badge/examples-live%20gallery-2ea44f)](https://rhnfzl.github.io/human-html/)
<!-- Enable once skills.sh indexes this repo (it serves "resource not found" until install activity registers):
[![skills.sh](https://skills.sh/b/rhnfzl/human-html)](https://skills.sh/rhnfzl/human-html)
-->

Make the next document a teammate actually reads.

human-html is an Agent Skill for the documents agents produce for humans: plans, code reviews, architecture explainers, understanding docs, research syntheses, decision records, prototypes, status reports, and incident postmortems. Instead of a wall of Markdown that gets skimmed and rubber-stamped, each one lands as a single self-contained HTML page: a plain-language summary at the top, a diagram in every before/after section, color-coded risks, the key evidence inline. An offline validator enforces that shape as a contract, so the quality is mechanical, not aspirational. Markdown keeps the jobs it is good at (scratch notes, references, tickets, agent-to-agent handoffs); HTML becomes the human review layer.

## Quickstart (30 seconds)

1. Install into whichever coding agents you use (the installer auto-detects them):

```bash
npx skills add rhnfzl/human-html
```

2. Initialise a workspace lane:

```bash
python3 <skill-dir>/human_html_artifacts.py init
```

3. Ask your agent for a plan, review, or postmortem, or scaffold one yourself and validate it:

```bash
python3 <skill-dir>/human_html_artifacts.py new plan "Q3 migration"
python3 <skill-dir>/human_html_artifacts.py check
```

`<skill-dir>` is wherever the installer put the skill: `~/.claude/skills/human-html` for Claude Code, `~/.agents/skills/human-html` or `~/.codex/skills/human-html` for Codex, `~/.cursor/skills/human-html` for Cursor.

Other install routes: `npx openskills install rhnfzl/human-html` (AGENTS.md ecosystems); Claude Code natively via `/plugin marketplace add rhnfzl/human-html` then `/plugin install human-html@rhnfzl` (recent versions auto-load the root SKILL.md as a single-skill plugin); or plain `git clone` plus a symlink into your agent's skills directory.

## Why this exists

**Problem #1: humans skim.** Send a teammate a long Markdown plan and you get a rubber stamp, not a review. They miss the assumption buried in paragraph nine and approve something they never really read. The fix is a surface built for a reader with ten minutes: an "In plain terms" summary a PM can parse, navigation, a visual in every comparison, verdicts answer-first, risks in color with the evidence one click deep. Nine artifact kinds cover the review surfaces a software team actually produces, each with its own scaffold.

**Problem #2: document quality does not survive iteration.** Style intentions decay the moment an agent regenerates a file. The fix is a content contract with teeth: ten numbered rules (plain-language summary block, comparison visuals, nav anchors, per-kind required sections, glossary linking, reading guides, mobile responsiveness, no-JS fallbacks, plain language for coined terms, no em dashes in prose), validated mechanically by `check`. Four rules block, the rest warn, and every rule is suppressible per artifact when you disagree with it. A hook rebuilds the gallery index on every write, so the lane stays browsable without anyone remembering to update it.

**Problem #3: sharing tools assume you want to upload.** Here the default is local. An artifact is one self-contained HTML file on your disk; nothing leaves your machine unless you decide it should. Sharing is a menu: commit the files and turn on GitHub Pages (they are already static HTML, there is no build step), run the optional bring-your-own-bucket S3 script (`scripts/publish-s3.sh`, env-driven, zero defaults), drop the file on any static host, or just send it. One qualifier: artifacts with Mermaid diagram blocks load the renderer from a CDN at view time; render diagrams to inline SVG (the recommendation for shipped artifacts) and they are fully offline.

## Steal like an artist

Austin Kleon's book of that name makes the case that nothing is original: you study work worth stealing from, take what resonates, remix it, and make it yours. That is both how this skill was built and how it is meant to be used.

- **The content contract is stolen craft.** The inverted pyramid comes from journalism, answer-first verdicts from decision memos, timeline-plus-actions from incident-response culture, C4 context diagrams from architecture practice, first-use glossing from every major style guide, progressive disclosure from information design. The rules just make the theft repeatable.
- **The nine canonical examples are heist targets, not templates.** Read the one for your kind before writing ([live gallery](https://rhnfzl.github.io/human-html/)), then take its moves: the keycard verdict, the side-by-side comparison panels, the metric tiles, the reading map.
- **`references/patterns.md` is the catalog.** Collapsible deep-dives, tabbed code, comparison grids, sharing recipes, meeting Q&A overlays, worked-example steppers. Lift whatever your artifact needs.
- **The skill expects to be stolen from, too.** Fork it, re-theme the scaffold CSS to your brand, carve out your own Markdown lanes with a `.human-html-allowlist`, suppress any rule per artifact with one comment. MIT licensed; make it yours.

## What's in the box

| Piece | What it does |
|---|---|
| `SKILL.md` | The contract: rules, per-kind scaffolds, illustration menu, wiring instructions |
| `human_html_artifacts.py` | `init` / `new` / `check` / `index` / `deps`; scaffolds, validates, and rebuilds the gallery |
| `hooks/` | Two optional hooks: an advisory nudge when a review-shaped Markdown file is about to land outside the lane, and the gallery autoindex. Both advisory-only, both always exit 0 |
| `examples/` | Nine canonical artifacts, one per kind, all passing the contract warning-free |
| `references/` | Deep dives: adoptable patterns, diagram decision tree, workflow integrations |
| `templates/` | The glossary seed copied into new workspaces |
| `scripts/publish-s3.sh` | The optional S3 sharing helper; requires `HUMAN_HTML_S3_BUCKET`, ships no defaults |

## Requirements

- Python 3.8 or newer, standard library only. No `pip install`, no dependencies.
- Optional: `jq` (the two hooks degrade to silent no-ops without it), `mermaid-cli` (`mmdc`) to render diagrams to inline SVG, `excalidraw-mcp` for hand-drawn diagrams. `python3 <skill-dir>/human_html_artifacts.py deps` reports what is present.

## Trust

No postinstall scripts, no telemetry, no network calls in the core loop. The validator runs fully offline. Hooks are advisory-only and always exit 0. Review `SKILL.md` before installing, as you should for any skill.

## Agent support

Claude Code, Codex, OpenCode, and Gemini CLI read Agent Skills natively. Cursor and others are covered via the universal installers (`npx skills add`, openskills). Hook wiring for Claude Code, Codex, and Cursor is documented in `SKILL.md` under "Wiring".

## License

[MIT](LICENSE)
