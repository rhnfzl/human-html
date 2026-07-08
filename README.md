# human-html

[![Release](https://img.shields.io/github/v/release/rhnfzl/human-html)](https://github.com/rhnfzl/human-html/releases)
[![License](https://img.shields.io/github/license/rhnfzl/human-html)](LICENSE)
[![Python](https://img.shields.io/badge/python-stdlib%20only-3776ab)](#requirements)
[![Examples](https://img.shields.io/badge/examples-live%20gallery-2ea44f)](https://rhnfzl.github.io/human-html/)
<!-- Enable once skills.sh indexes this repo (it serves "resource not found" until install activity registers):
[![skills.sh](https://skills.sh/b/rhnfzl/human-html)](https://skills.sh/rhnfzl/human-html)
-->

An agent skill that makes the next document a teammate can actually read, instead of a wall of Markdown that gets skimmed.

When an agent produces something a human is meant to read to make a decision (a plan, a code review, an architecture explainer, an understanding doc, a research synthesis, a decision aid, a prototype, a status report, or an incident postmortem) this skill lands it as a single self-contained HTML page: a plain-language summary at the top, a diagram in every before/after section, color-coded risks, the key snippets inline. Markdown stays for what it is good at (scratch notes, durable references, ticket drafts, meeting transcripts, agent-to-agent handoffs); HTML becomes the human review layer. A small offline validator enforces that split as a content contract, so the surfaces stay readable rather than drifting back into skimmable walls. Everything runs locally: no network calls in the core loop, no telemetry, no uploads.

## Install

Primary, via the universal skills installer (auto-detects which coding agents are installed):

```bash
npx skills add rhnfzl/human-html
```

Alternatives:

- AGENTS.md ecosystems: `npx openskills install rhnfzl/human-html`
- Claude Code plugin (the marketplace install provides the `/human-html` command and, on recent Claude Code versions, auto-loads the root `SKILL.md` as a single-skill plugin):
  ```
  /plugin marketplace add rhnfzl/human-html
  /plugin install human-html@rhnfzl
  ```
- Manual: `git clone https://github.com/rhnfzl/human-html`, then symlink the checkout into your agent's skills directory (see "Quick start" for where that is per agent).

## Quick start

Four commands drive the whole loop. Run them from your workspace root:

```bash
python3 <skill-dir>/human_html_artifacts.py init                 # seed docs/human-html/ once per workspace
python3 <skill-dir>/human_html_artifacts.py new plan "Migrate auth to JWT"   # scaffold a new artifact
python3 <skill-dir>/human_html_artifacts.py check                # validate against the contract (offline)
python3 <skill-dir>/human_html_artifacts.py index                # rebuild the gallery index.html
```

`<skill-dir>` is wherever your agent installed the skill:

- Claude Code: `~/.claude/skills/human-html`
- Codex: `~/.agents/skills/human-html` or `~/.codex/skills/human-html`
- Cursor: `~/.cursor/skills/human-html`

Inside Claude Code you can also just type `/human-html` and let the command walk you through picking a kind, scaffolding, and validating.

## Live examples

A gallery of the nine canonical artifacts (one per kind, each showing what good looks like) is published at:

https://rhnfzl.github.io/human-html/

## Sharing (local-first)

Every artifact is a single HTML file, self-contained by default. One qualifier: artifacts with Mermaid diagram blocks load the Mermaid renderer from a CDN at view time; render diagrams to inline SVG (the recommendation for shipped artifacts) and they are fully offline. Nothing leaves your machine unless you decide to share it, and sharing is an opt-in menu, not a default:

- **GitHub Pages**: serve `docs/human-html/` (or the repo root) and link the gallery.
- **S3 (bring your own bucket)**: `scripts/publish-s3.sh` is env-driven with zero baked-in defaults. It uploads nothing until you set `HUMAN_HTML_S3_BUCKET` and run it yourself.
- **Any static host**: the files are plain HTML+CSS, so anything that serves a file works.

The skill never uploads on your behalf. The publish script is the only path to the network, and you run it explicitly.

## Requirements

- Python 3.8 or newer, standard library only. No `pip install`, no dependencies.
- Optional: `jq` (the two hooks degrade to silent no-ops without it), `mermaid-cli` (`mmdc`) to render diagrams to inline SVG, `excalidraw-mcp` for hand-drawn diagrams.

## Trust

- No postinstall scripts.
- No telemetry.
- No network calls in the core loop (init / new / check / index all run offline).
- The validator runs fully offline.
- The two hooks are advisory only and always exit 0, so they can never block a tool call.

## Agent support

Claude Code, Codex, OpenCode, and Gemini CLI read Agent Skills natively. Cursor and other agents are covered through the universal installers (`npx skills add` and `npx openskills install`); native skill discovery in Cursor varies by version.

## Hooks

Two optional shell hooks keep the contract self-enforcing once wired:

- **advisory**: nudges an agent that is about to write a human-review Markdown file in a place where an HTML artifact belongs.
- **autoindex**: regenerates the gallery `index.html` automatically whenever an artifact lands, so you never hand-edit the index.

Both are opt-in, advisory only, and always exit 0. See the "Wiring" section of `SKILL.md` for the per-agent settings (Claude Code, Codex, Cursor).

## License

MIT. See [LICENSE](LICENSE).
