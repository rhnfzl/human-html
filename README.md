<p align="center">
  <img src="skills/human-html/assets/human-html-banner.webp" alt="human-html" width="640">
</p>

# human-html

[![skills.sh](https://skills.sh/b/rhnfzl/human-html)](https://skills.sh/rhnfzl/human-html)
[![Release](https://img.shields.io/github/v/release/rhnfzl/human-html)](https://github.com/rhnfzl/human-html/releases)
[![License](https://img.shields.io/github/license/rhnfzl/human-html)](LICENSE)


Make the next document a teammate actually reads.

An Agent Skill for the documents agents produce for humans: plans, reviews, architecture explainers, research, decisions, prototypes, status reports, postmortems. Each one lands as a single self-contained HTML page (plain-language summary, a diagram in every comparison, color-coded risks) instead of a Markdown wall that gets skimmed and rubber-stamped. An offline validator enforces that shape as a contract. See the [live gallery](https://rhnfzl.github.io/human-html/) of all nine kinds.

## Quickstart (30 seconds)

One command, and it auto-detects your installed agents; that is the whole setup:

```bash
npx skills add rhnfzl/human-html
```

Then ask your agent for a plan, review, or postmortem. The agent scaffolds, validates, and indexes everything; the `docs/human-html/` lane appears in a workspace with the first artifact.

Enable the optional advisory and autoindex hooks globally for Claude Code, Codex, Cursor, and Windsurf:

```bash
python3 <skill-dir>/activate_hooks.py
```

The command merges with existing settings and is safe to rerun. Replace `<skill-dir>` with the installed skill path shown by your installer, commonly `~/.agents/skills/human-html`.

<details>
<summary>Other install routes and manual use</summary>

- `npx openskills install rhnfzl/human-html` (AGENTS.md ecosystems)
- Claude Code natively: `/plugin marketplace add rhnfzl/human-html`, then `/plugin install human-html@rhnfzl`
- Manual: clone this repo and symlink `skills/human-html/` into your agent's skills directory
- Drive the CLI yourself: `python3 <skill-dir>/human_html_artifacts.py new|check|index`, where `<skill-dir>` is wherever the installer put the skill (e.g. `~/.claude/skills/human-html`). `init` is optional and seeds a workspace glossary.

</details>

## Why this exists

1. **Humans skim.** A long Markdown plan gets a rubber stamp, not a review. These artifacts are built for a reader with ten minutes: summary first, visuals in every comparison, verdicts answer-first, risks in color.
2. **Document quality decays.** Style intentions vanish the moment an agent regenerates a file. Here the shape is a validated contract (`check`): three rules always block, `nav-anchors` blocks unless the artifact is in dynamic mode, the rest warn, and every rule is suppressible per artifact. The checks are markers, not proofs, and [`references/artifact-spine.md`](skills/human-html/references/artifact-spine.md) says exactly what each one does and does not establish.
3. **Sharing tools assume upload.** Default is local; nothing leaves your machine. Sharing is a menu: GitHub Pages (artifacts are already static HTML), an optional bring-your-own-bucket S3 script with zero defaults, or any static host. Note: Mermaid blocks load a CDN at view time; render to inline SVG for fully-offline artifacts.

The contract itself is stolen craft, in the [Steal Like an Artist](https://austinkleon.com/steal/) sense: the inverted pyramid, postmortem timelines, C4 diagrams, first-use glossing. The nine canonical examples exist to be stolen from too, and so does the repo: fork it, re-theme it, suppress what you disagree with.

## The nine kinds

Each kind has its own scaffold and a canonical example showing what good looks like ([full gallery](https://rhnfzl.github.io/human-html/)):

| Kind | The reader wants to |
|---|---|
| [plan](https://rhnfzl.github.io/human-html/skills/human-html/examples/plan-canonical.html) | execute: outcome, sequence, risks, rollback |
| [review](https://rhnfzl.github.io/human-html/skills/human-html/examples/review-canonical.html) | inspect a change: verdict first, concerns ranked |
| [architecture](https://rhnfzl.github.io/human-html/skills/human-html/examples/architecture-canonical.html) | understand a proposed change to system shape |
| [understanding](https://rhnfzl.github.io/human-html/skills/human-html/examples/understanding-canonical.html) | understand how something works today |
| [research](https://rhnfzl.github.io/human-html/skills/human-html/examples/research-canonical.html) | learn what the digging found |
| [decision](https://rhnfzl.github.io/human-html/skills/human-html/examples/decision-canonical.html) | decide: options, consequences, reversibility |
| [prototype](https://rhnfzl.github.io/human-html/skills/human-html/examples/prototype-canonical.html) | feel a proposed thing before it exists |
| [status](https://rhnfzl.github.io/human-html/skills/human-html/examples/status-canonical.html) | catch up: where we are, blockers, next |
| [incident](https://rhnfzl.github.io/human-html/skills/human-html/examples/incident-canonical.html) | learn from failure: timeline, root cause, actions |

## When the shape is the argument: dynamic mode

The nine kinds pre-decide a section skeleton before anyone knows what the artifact needs to say. That is the right trade most of the time and the wrong one sometimes. A findings taxonomy, a four-way design exploration, a line-by-line map of a port: each of those has a natural shape, and the shape carries part of the argument. Forcing it into `plan` sections makes the document worse.

```bash
python3 <skill-dir>/human_html_artifacts.py new review "Blindspot pass on RFC 214" --mode dynamic
```

One question decides which to use: **does the reader benefit from this looking like the last one?** Yes means use a kind, because comparability across instances is the value; this week's status report should look like last week's so the difference stands out. No means go dynamic. Unclear means use the kind, since a kind that fits slightly badly costs a reader less than an invented structure that fits nothing.

Dynamic mode stands down exactly three rules, all of them about *which sections exist*: `required-section`, `read-map`, and `nav-anchors` (from block to warn). Nothing that aims at the reader is relaxed. The artifact still has to render on a phone, exist with JavaScript off, answer first, put a real visual in every comparison, and gloss its terms. The split is clean because the rules were always two populations wearing one coat: `required-section` says *a plan looks like this*, `viewport-meta` says *a human on a phone can read this*.

Structure is yours; style is not. Dynamic artifacts inherit the scaffold's tokens and type scale rather than inventing a palette, and [`references/artifact-spine.md`](skills/human-html/references/artifact-spine.md) is the standard the validator cannot check: what an artifact must never do whatever shape it takes. Three examples ship ([blindspot pass](https://rhnfzl.github.io/human-html/skills/human-html/examples/dynamic-blindspot-pass.html), [design directions](https://rhnfzl.github.io/human-html/skills/human-html/examples/dynamic-design-directions.html), [port correspondence](https://rhnfzl.github.io/human-html/skills/human-html/examples/dynamic-port-correspondence.html)) and they deliberately share no structure, so none of them reads as the template.

## Seeing the artifact, with and without JavaScript

`render` screenshots an artifact through headless Chrome so an agent can look at its own output and fix a clipped diagram before a human ever opens it:

```bash
python3 <skill-dir>/human_html_artifacts.py render <file>          # what a reader sees
python3 <skill-dir>/human_html_artifacts.py render <file> --no-js   # what a JS-disabled preview sees
```

`--no-js` matters more than it sounds. Artifacts get opened in iOS Quick Look, Android file previews, and email, all of which render HTML and CSS but run no JavaScript. The validator can only grep for a `<noscript>`; it cannot tell whether the fallback is real. On its first use `--no-js` found that this repo's own `prototype-canonical.html` had a broken static floor, hidden for weeks behind a rule that reported clean.

## What's in the box

| Piece | What it does |
|---|---|
| `skills/human-html/SKILL.md` | The contract: rules, per-kind scaffolds, dynamic mode, illustration menu, hook wiring |
| `skills/human-html/human_html_artifacts.py` | `init` / `new` / `check` / `index` / `deps` / `embed-svg` / `render` |
| `skills/human-html/activate_hooks.py` | Idempotently enables the optional hooks for supported agents |
| `skills/human-html/hooks/` | Optional advisory nudge + gallery autoindex; advisory-only, always exit 0 |
| `skills/human-html/examples/` | Nine canonical artifacts, one per kind, plus three dynamic-mode examples that share no structure; all warning-free |
| `skills/human-html/references/` | The artifact spine, adoptable patterns, diagram decision tree, workflow integrations |
| `skills/human-html/scripts/publish-s3.sh` | Optional S3 sharing; requires `HUMAN_HTML_S3_BUCKET`, no defaults |
| `tests/` | 32 stdlib `unittest` tests over the validator and the shipped examples: `python3 -m unittest discover -s tests` |

## Requirements

Python 3.11+ is all you need. The tools below are optional, but each one unlocks a nicer experience and gets more out of the skill:

| Tool | Enables | Install |
|---|---|---|
| [`jq`](https://jqlang.github.io/jq/) | the two hooks (they no-op silently without it) | `brew install jq` (or your package manager) |
| [`mmdc`](https://github.com/mermaid-js/mermaid-cli) | rendering Mermaid diagrams to inline SVG for offline artifacts | `npm i -g @mermaid-js/mermaid-cli` |
| [`excalidraw-mcp`](https://github.com/excalidraw/excalidraw-mcp) | hand-drawn diagrams | install the companion skill, or run `python3 <skill-dir>/human_html_artifacts.py deps --fix` |

Run `python3 <skill-dir>/human_html_artifacts.py deps` to see what is present.

## Trust

The skill does nothing behind your back:

- No telemetry, no analytics, no phone-home.
- No postinstall scripts; installing copies files, it does not execute code.
- No network calls in the core loop, and the validator runs fully offline.
- The hooks are advisory-only and always exit 0.

As with any skill, read `skills/human-html/SKILL.md` before you install.

## Agent support

human-html is a standard [Agent Skill](https://agentskills.io), so it works anywhere that reads the format. Confirmed native support (the agent auto-loads `SKILL.md`, no installer needed): Claude Code, Codex, Cursor, GitHub Copilot, Gemini CLI, OpenCode, Zed, Amp, Warp, Kiro, Crush, Qwen Code, and Pi. Anything else is covered by the universal installers (`npx skills add`, `openskills`), which target 70+ agents including Windsurf, Cline, and Aider.

## License

[MIT](LICENSE)
