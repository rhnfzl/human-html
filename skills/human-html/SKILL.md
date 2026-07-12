---
name: human-html
description: Use when creating a human review surface, such as a plan, review, architecture explainer, understanding doc, research synthesis, decision aid, prototype, status report, or incident postmortem. Put the artifact under docs/human-html/ as HTML instead of Markdown. Markdown stays for scratch notes, durable references, ticket notes, drafts, and meetings. Provides scaffolds, validation, index refresh, glossary support, and hooks for Claude Code and Codex.
license: MIT
metadata:
  version: "1.2.3"
  author: "rhnfzl"
---

# human-html

## What this is, in plain terms

Picture a tech lead, a product manager, or a teammate opening one of your documents for the first time. They have ten minutes. They want to know what the work is, whether the plan is sound, where the risk sits, and what they need to do next.

If the document is a long Markdown file, they skim. Skim turns into rubber-stamp. They miss the assumption that was buried in paragraph nine. They approve something they didn't really read.

If the document is a single HTML page with a plain-language summary at the top, a diagram in every before/after section, color-coded risks, a checklist, and the key snippets inline, they read. They ask sharper questions. They catch the thing that was wrong. They redirect work before it lands in the wrong place.

This skill enforces that switch as a workspace contract. When an agent (you, Claude, Codex, or anyone else) produces a *human review surface* (a plan, a code review, an architecture explainer, an understanding doc, a research synthesis, a decision aid, a prototype, a status report, or an incident postmortem) the artifact lands as HTML under `docs/human-html/` of the active workspace. Not as Markdown. Markdown is still the right format for scratch notes, ticket drafts, durable references, and meeting transcripts; it is the agent's memory layer. HTML is the human's review layer. The split is the point.

The skill enforces two layers of contract: a **file contract** (naming, metadata, allowlist; unchanged since the original file-contract release) and a **content contract** (PM-summary block, diagram-in-comparison, nav-when-many-sections, required sections per kind, glossary linking, read-map, Q&A overlay schema, metadata ribbon, provenance footer, mobile responsiveness, and no-JS robustness; effective for artifacts created on or after `2026-05-25`). Earlier artifacts are grandfathered. The content rules are validated mechanically by `human_html_artifacts.py check`; four rules always block (pm-summary, comparison-visual, nav-anchors, viewport-meta), required sections block for `incident` and warn for other kinds, and read-map / Q&A / glossary / ribbon / provenance / table-responsive / js-content-fallback warn when applicable. Each violation prints a `[rule=<id>]` suffix; per-artifact suppression is available via `<!-- human-html-disable: ... -->`.

Adoption costs ten seconds per workspace. After that, two hooks keep the contract self-enforcing: one nudges an agent that is about to write a human-review Markdown file in the wrong place; the other regenerates the gallery `index.html` automatically whenever an artifact lands.

## What you get

- A `docs/human-html/` artifact lane containing top-level artifacts named `YYYY-MM-DD-kind-slug.html`, optional nested portable collections, plus an auto-generated `index.html` gallery: responsive cards in reverse-chronological order, each with a one-line summary and keyword chips, plus a no-dependency client-side filter (text box + kind chips, progressive-enhancement so cards still render with JS off). A single malformed file never blocks the build - the gallery skips it, warns, and shows a notice (skip-and-warn).
- Nine named *kinds* that cover the human-review surfaces a software team actually produces: `plan`, `review`, `architecture`, `understanding`, `research`, `decision`, `prototype`, `status`, `incident`. Each kind ships with its own scaffold and a canonical example showing what good looks like.
- A small Python script that scaffolds new artifacts with the correct filename, metadata, and per-kind section skeleton (PM-summary block, nav, kind-appropriate sections, diagram placeholders in comparison sections); recursively validates artifacts and nested collections against both the file contract and the content contract; and rebuilds the gallery.
- Two shell hooks that nudge toward the harness when an agent is about to drift, and that keep the gallery current without the agent remembering to refresh it.
- A per-workspace customization knob (`.human-html-allowlist`) for the small set of cases where a workspace has Markdown lanes the baseline does not anticipate.
- A per-workspace `GLOSSARY.md` (seeded on `init`) for shared jargon definitions, plus a validator WARN rule that nudges artifacts to wrap or link known terms.

## When to use it

Use the harness whenever the next artifact will be read by a human to make a decision, redirect work, approve a change, or build understanding of a system. If it would be reasonable to send the artifact to a teammate, the answer is HTML under `docs/human-html/`.

Do not use it for:

- Agent-to-agent handoffs (those parse better as Markdown).
- Source-of-truth specs that get edited weekly in git (HTML diffs are noisy; Markdown wins for git review).
- Short answers under ~20 lines (a chat reply is enough).
- Anything that is not intended for a human reader.

---

## Content contract

Every artifact whose `artifact-created` is on or after `2026-05-25` (the `RULES_EFFECTIVE_DATE` baked into `human_html_artifacts.py`) must satisfy the numbered content rules below. The validator also WARNs on missing metadata ribbon and provenance footer/schema (see those subsections under "Adoptable patterns"). Earlier artifacts are grandfathered and only need to pass the older identity rules (filename pattern, metadata, body marker, link validity). The cutoff lives in the script so all workspaces share the same policy.

### Rule 1 - PM-language summary block (BLOCKS)

Every artifact opens with a top-level `<section data-audience="pm">` containing a three-bullet plain-language block (product context before technical detail):

```html
<section data-audience="pm" class="pm-summary">
  <h2>In plain terms</h2>
  <ul>
    <li><strong>What this does for the user:</strong> One sentence a PM can grasp without engineering context.</li>
    <li><strong>Why it matters:</strong> One sentence on the constraint, deadline, or stakeholder ask driving this.</li>
    <li><strong>What's being asked:</strong> The decision, approval, or review action you want the reader to take.</li>
  </ul>
</section>
```

The `data-audience="pm"` attribute is what the validator checks. Class names and bullet wording can vary; only the attribute is load-bearing.

Per-section PM-language leads (a 1-sentence opener inside each `<h2>` section) are strongly recommended but not validated - that's a writer's judgment call the validator can't reliably enforce.

### Rule 2 - Visual in every comparison section (BLOCKS)

When an `<h2>` or `<h3>` heading contains an explicit comparison pair, the section MUST contain at least one of:

- A mermaid diagram: `<div class="mermaid">flowchart LR ...</div>`
- An inline `<svg>`
- A side-by-side panel grid using the `grid-cols-2` class
- A comparison `<table>`
- An `<img>` (for custom-drawn diagrams)
- A `<pre class="diagram">` (ASCII / CSS-box sketch, e.g. a C4-L1 diagram), or any element carrying `data-visual="true"` (an explicit escape hatch for a custom visual the above miss)

Prose alone is not enough. Which visual to pick depends on what the comparison shows - see `references/diagram-types.md` for the decision tree.

The validator matches explicit pairs only (see `COMPARISON_HEADING_RE` in the script), for example:

- `Before / after`, `before and after`
- `Current vs proposed`, `baseline / target`, `old vs new`
- `Previously vs now`

Standalone words like "current", "proposed", or "target" in headings such as "Target audience" or "Current blockers" do **not** trigger the rule. Headings that genuinely compare two states should use one of the explicit pair forms above so the validator can find them.

### Rule 3 - Nav anchor list when an artifact has more than 3 `<h2>` sections (BLOCKS)

An artifact with more than three `<h2>` sections must include a `<nav>` element with same-page anchor links that point to existing IDs (typically a table-of-contents block before the first section). Reader navigation matters once the doc is more than one screen.

```html
<nav class="toc" aria-label="On this page">
  <strong>On this page</strong>
  <ol>
        <li><a href="#section-one">Section one</a></li>
        <li><a href="#section-two">Section two</a></li>
  </ol>
</nav>
```

### Rule 4 - Required sections per kind (BLOCKS for `incident`, WARNS for others)

Each kind has a small set of sections it should contain. The validator (Vale-style severity model) treats most as WARN, but two are BLOCK because shipping the artifact without them is structurally broken:

| Kind | Required section (heading regex) | Severity |
|---|---|---|
| `incident` | `\btimeline\b` | **BLOCK** - a postmortem without a timeline is not a postmortem |
| `incident` | `\b(corrective\s+actions?\|actions?\|next\s+steps?)\b` | **BLOCK** - no actions = no learning |
| `incident` | `\b(impact\|customer\s+impact\|business\s+impact)\b` | WARN |
| `incident` | `\b(root\s+cause\|contributing\s+factors?)\b` | WARN |
| `plan` | `\brollback\b` | WARN |
| `decision` | `\bconsequences?\b` | WARN |
| `architecture` | `\bopen\s+questions?\b` | WARN |

Staged rollout (report-only -> warn -> block) is supported: ship a new rule as WARN, raise to BLOCK after observing how many artifacts comply.

### Rule 5 - Glossary linking for known terms (WARNS)

If `docs/human-html/GLOSSARY.md` exists in the workspace and an artifact uses a term defined there without wrapping it in `<abbr title="...">` or linking to `<a href="GLOSSARY.md#term">`, the validator prints a `WARN:` line (does not block). The glossary file is workspace-specific; teams add their own jargon definitions.

If the glossary doesn't exist yet, the warning never fires.

### Rule 6 - Reading guide on long artifacts (WARNS)

For `architecture`, `decision`, `review`, `plan`, and `incident` artifacts with more than 3 `<h2>` sections, the validator WARNs if there is no reading guide. Mark it with `class="read-map"` or `aria-label="Reading map"` so the validator can find it (the class name is kept for compatibility). The guide should be depth-based (Quick read vs Full read), not role-based. Other kinds (`prototype`, `understanding`, `research`, `status`) are exempt.

### Rule 7 - Meeting Q&A overlay schema (WARNS)

If an artifact carries `data-meeting-qa="true"` on any element (typically the overlay section), the validator looks for a `<script type="application/ld+json" id="meeting-qa-data">` block and WARNs on each malformed question. Required per question: `id`, `text`, string `status` (one of `answered`, `partially_answered`, `deferred`, `action_item`, `duplicate`, `inferred`), and `topic` (or `topic_tags`). When `status` is `inferred`, also required: numeric non-boolean `confidence` between 0 and 1, plus `rationale`.

### Rule 8 - Mobile responsiveness (BLOCKS on viewport, WARNS on tables)

**Teammates open these on their phones.** Two mechanical checks back the "works on mobile" requirement:

- **`viewport-meta` (BLOCKS):** the artifact must carry `<meta name="viewport" content="width=device-width, initial-scale=1">`. Without it, mobile browsers render the page at a fake desktop width (~980px) and zoom out - everything is tiny and unusable. The scaffolds already include it; don't remove it.
- **`table-responsive` (WARNS):** any `<table>` must have a responsive treatment - a `@media (max-width: …)` rule that reflows it (e.g. stack each row into a card via per-cell `data-label`), an `overflow-x:auto` scroll wrapper, or `data-responsive-table`. A wide multi-column table with none of these clips or forces a zoomed-out layout on a phone.

The **card-reflow** pattern (what good looks like): on mobile, set `thead{display:none}` and turn each `<tr>`/`<td>` into a block; give each `<td data-label="English">` a `td::before{content:attr(data-label)}` so the column name shows beside its value. Gotchas learned the hard way: (1) a mobile rule like `tr.detail{display:block}` will **override the `[hidden]` attribute** - add `tr.detail[hidden]{display:none}` or collapsed rows render expanded; (2) if a control re-renders a large list on every `input` event, **coalesce the re-render with `requestAnimationFrame`** so the value label paints instantly while dragging on a phone instead of being blocked by the rebuild.

### Rule 9 - No-JS robustness (WARNS)

**JS-disabled previews are common and silent:** iOS **Quick Look** (opening a file from Files / Mail / AirDrop), Android file-manager and in-app previews, and email clients render HTML+CSS but run **no JavaScript** (Apple disabled it in Quick Look for privacy). An artifact whose core content is built by JS (`element.innerHTML = …`) shows up **blank** there - empty tables, empty lists, "0 results".

- **`js-content-fallback` (WARNS):** if the artifact writes content with `.innerHTML` and has no `<noscript>`, it WARNs. The fix is **progressive enhancement**: pre-render the core content (table rows, list items, counts) into the static HTML so it's readable with JS off, and let JS *enhance* it (sort/filter/live controls) when available. Add a `<noscript>` banner pointing the reader to open it in a real browser, and hide the now-inert controls with `<noscript><style>.controls{display:none}</style></noscript>`. Interactive artifacts (the `prototype` kind, dashboards) are exactly where this matters most.

Mermaid source must stay legible when the CDN or JS is unavailable - the scaffold styles unprocessed `.mermaid` blocks as preformatted source (`white-space: pre`, mono, scrollable) so a diagram that never rendered reads as its flowchart text, not a collapsed wall of prose.

### Rule 10 - Plain language for coined terms (WARNS)

The failure this rule targets: a doc introduces a **coined term** (a name specific to this project - "adjudicator", "belief state", "shadow router") and uses it in prose without ever saying, in plain words, what it means. The reader is lost. The fix, from every major style guide (Google, Microsoft, IETF RFC 7322, NN/g, Federal Plain Language Guidelines): **define a coined term on its first use, in plain words, with a concrete example - then use it freely.** Claude's own artifact guidance says the same thing: *write from the user's side of the screen; name things by what people recognize; specific beats clever.*

**How the validator knows what's a coined term - you tell it, it never guesses.** "Is this word jargon?" is audience-relative, so auto-detection over-flags and gets ignored. Every check below fires only on terms **you marked**, via one of:

- The native **`<dfn>` element** on a term's defining instance - the per-doc registry. `<dfn>adjudicator</dfn>`, or `<dfn><abbr title="Server-Sent Events">SSE</abbr></dfn>`.
- The workspace **`GLOSSARY.md`** (`## Term` headings) - shared cross-doc vocabulary (handled by the older `glossary-link` WARN).

Terms in the **allowlist** (`docs/human-html/.jargon-allowlist`, seeded with API/JSON/MCP/SSE/SSO/LLM/… - extend per project) are never flagged. Because everything keys off a declared registry minus the allowlist, the whole suite stays near-zero-false-positive; a doc that uses no `<dfn>` triggers none of it.

**The convention - first-use gloss + example (bake this into prose):**

```html
<p>The tie-breaker step that picks one tool when several could handle a request
   (the <dfn>adjudicator</dfn>) makes the final call - for example, choosing
   invoice-search over generic chat when the accountant says "find unpaid invoices".</p>
```

Plain-first `[plain] (<dfn>term</dfn>)` when readers likely don't know it; term-first when most do. Later uses can link back: `<a href="#adjudicator">adjudicator</a>`.

**Key-terms block** - for `architecture` / `decision` docs that coin several terms, collect them after the summary (supplement to, never a substitute for, the inline first-use gloss):

```html
<dl id="key-terms">
  <dt><dfn id="adjudicator">adjudicator</dfn></dt>
  <dd>The step that picks one winning tool when several could handle a request -
      e.g. invoice-search over generic chat.</dd>
</dl>
```

**The mechanical checks (all WARN, registry-gated, suppressible):** `first-use-gloss` (a `<dfn>` term used bare *before* its definition - put the `<dfn>` on the first use or link the earlier use to `#key-terms`); `term-count` (more than ~8 coined terms - deletion beats definition); `circular-gloss` (a definition that repeats its own term, ISO/IEC 16.5.6); `bare-gloss-ref` (a definition that's only "see X"); `abbr-title` (an `<abbr>` with no `title`, WCAG H28); `heading-debut` (a coined term first appearing in a heading); `key-terms-block` (an architecture/decision doc coining ≥3 terms with no `<dl id="key-terms">`).

**The judgment lane (NOT mechanized - a script would false-positive):** whether a word *is* jargon for this audience, whether a gloss is actually *clear*, whether a section lead reads plainly, and readability scores. These live in the ship checklist below, not the validator. A necessary domain term is not jargon to be scrubbed - the rule flags a *missing gloss*, never the term's right to exist.

### Suppressing a rule on a single artifact

Add an HTML comment naming the rule(s) to suppress anywhere in the artifact body:

```html
<!-- human-html-disable: read-map -->
<!-- human-html-disable: qa-overlay, glossary-link -->
```

Each violation prints its `[rule=<id>]` suffix; use that ID. The literal `all` suppresses every content-shape rule (use sparingly). Suppression is per-artifact; per-section suppression is a future extension.

| Rule ID | Severity | Triggers when |
|---|---|---|
| `pm-summary` | BLOCK | No `<section data-audience="pm">` |
| `comparison-visual` | BLOCK | Comparison heading without a visual |
| `nav-anchors` | BLOCK | More than 3 `<h2>` sections without valid `<nav>` anchors |
| `required-section` | BLOCK/WARN | Kind-specific section missing |
| `glossary-link` | WARN | Glossary term unwrapped |
| `read-map` | WARN | One of those kinds, 4+ `<h2>` sections, no reading guide |
| `qa-overlay` | WARN | `data-meeting-qa="true"` with malformed JSON-LD |
| `meta-ribbon` | WARN | No `data-meta-ribbon="true"` |
| `provenance-footer` | WARN | No provenance marker |
| `provenance-fields` | WARN | Provenance JSON-LD missing documented fields |
| `viewport-meta` | BLOCK | No responsive `<meta name="viewport" … width=device-width>` |
| `table-responsive` | WARN | A `<table>` with no responsive treatment (no `@media`/`overflow-x`) |
| `js-content-fallback` | WARN | Content built with `.innerHTML` but no `<noscript>` fallback |
| `slop-signal` | WARN | Violet AI-default hex, emoji-in-heading, `lorem ipsum`, or "Generated by AI" present |
| `em-dash` | WARN | An em/en dash in prose (dashes inside `pre`/`code`/`script`/`style` are exempt) |

## Pick the kind

Before scaffolding, identify the **job (verb)** and the **reader's goal**, then route:

| If you are… | reader wants to… | kind |
|---|---|---|
| weighing options / choosing | decide | `decision` |
| laying out how work will happen | execute | `plan` |
| judging someone's change | inspect | `review` |
| explaining how a system is shaped / should change | understand a change | `architecture` |
| explaining how something works | understand a thing | `understanding` |
| reporting what digging found | learn | `research` |
| showing where things stand | catch up | `status` |
| demonstrating a proposed thing | feel it | `prototype` |
| writing up an outage after the fact | learn from failure | `incident` |

**avoid_when** (the common mis-pick): `incident` only after the fact - a live situation under control is a `status`; `architecture` is for system shape, not a task list (that's `plan`); `research` reports findings, `decision` records the call made from them.

## Per-kind scaffolds

Nine kinds, each with its own section shape. Running `human_html_artifacts.py new <kind> "<title>"` produces a scaffold that passes the content contract out of the box (PM-summary present, nav present, comparison sections shipped with placeholder diagrams).

| Kind | Section shape | Default comparison visual |
|---|---|---|
| `plan` | Outcome / Approach / Sequence / Risks / Rollback | Mermaid in Approach |
| `review` | Verdict / Strengths / Concerns / Required / Optional | Add Before/After in Concerns on demand |
| `architecture` | Context / Before / after / Recommendation / Sequence / Open questions | Side-by-side mermaid in Before / after |
| `understanding` | What it is / How it works / Gotchas / Where to dig | Mermaid in How it works |
| `research` | Question / Method / Findings / Synthesis / Open threads | Table in Findings |
| `decision` | Decision (Y-statement) / Context / Current vs proposed / Consequences / Reversibility | Table in Current vs proposed |
| `prototype` | Goal / Current vs target / What's mocked / What's real / Try it | Mermaid in Current vs target |
| `status` | Where we are / Recent changes / Blockers / Next | Tiles summary + chip-status table |
| `incident` | Public summary / Timeline / Impact / Root cause / Corrective actions / Lessons learned | Timeline as vertical timestamped list; impact as metric tiles. Mark long quiet spans explicitly (`<div class="gap">2h 14m - no activity</div>`) |

**Opening treatment:** verdict-bearing kinds - `review`, `decision`, `incident`, `status` - open answer-first: a `.keycard` (verdict or number + one sentence) directly after the PM-summary, because the reader's first question is "what's the call?". Explanatory kinds - `understanding`, `architecture`, `research`, `plan`, `prototype` - keep the quiet header; a keycard there is decoration unless a single number genuinely is the story. Never fabricate a hero number to fill the slot.

### Canonical examples

Under `<skill-dir>/examples/<kind>-canonical.html`, the skill ships a worked reference per kind. (`<skill-dir>` here and below is wherever your agent installed this skill: `~/.claude/skills/human-html` for Claude Code, `~/.agents/skills/human-html` or `~/.codex/skills/human-html` for Codex, `~/.cursor/skills/human-html` for Cursor, or wherever your installer placed it.) These are NOT scaffolds (don't copy them blindly into a new artifact) but exemplars of what *good* looks like for that kind. Read the canonical example before writing a new artifact of that kind, especially for `architecture`, `review`, and `decision` where structure carries the most weight.

`architecture-canonical.html` is a fictional worked example modeled on a realistic multi-codebase architecture review and demonstrates all three primary diagram patterns: mermaid for structural change, side-by-side code panels for signature change, comparison tables for enumeration.

## Glossary

`docs/human-html/GLOSSARY.md` is the workspace's shared definition lane. `init` seeds it from `<skill-dir>/templates/GLOSSARY.md` with a baseline of universal terms; teams add domain-specific entries (for example: your project keys, service names, protocol acronyms, and domain-specific terms).

Two acceptable ways to reference a term inside an artifact:

- Inline tooltip: `<abbr title="Model Context Protocol">MCP</abbr>`
- Link to the full definition: `<a href="GLOSSARY.md#mcp">MCP</a>`

The validator WARN rule fires when a glossary-defined term appears in artifact body text without either treatment.

Hover-linked glossary terms (`<abbr title="...">`) are the lightest-weight option and read well in print: hovering reveals the definition inline without leaving the artifact. Reserve the `<a href="GLOSSARY.md#term">` link for terms whose full definition is too long for a tooltip or where the reader benefits from landing on the canonical entry. Both satisfy the validator equally.

## Illustration menu

Artifacts should *show*, not just tell. Reach for the lightest illustration that conveys the idea, match the visual to the concept, and match the depth to what the reader needs. Cost note: a Mermaid block is ~5 - 50 lines of source (token-cheap) but needs the CDN; inline SVG is self-contained but token-heavy - prefer Mermaid unless the artifact must render offline or under a strict CSP. For a **shipped** artifact, invert that default: author in mermaid but render to inline SVG (Mermaid render tool / `mmdc`) and keep the source in an adjacent `<details><pre>` - the shipped state shouldn't depend on the CDN or JS (Quick Look, email, offline archives run none), while a live CDN block is fine for drafts. See `references/diagram-types.md`, "When to use mermaid".

**Concept → visual:**

| The concept is… | Use | Notes |
|---|---|---|
| A process / workflow | Mermaid `flowchart` (`graph LR/TD`) | cheapest |
| Actors exchanging messages over time | Mermaid `sequenceDiagram` | API / SSE / approval flows |
| A state machine / lifecycle | Mermaid `stateDiagram-v2` | |
| A data model / relationships | Mermaid `erDiagram` | |
| Two states (before/after, current/proposed) | side-by-side `grid-cols-2` panels or a comparison table | satisfies Rule 2 |
| System architecture, for any reader | **C4 Level 1 (System Context)** as CSS boxes or ASCII | notation-independent: one box per system + labelled arrows |
| Architecture, deeper | C4 Level 2 (Containers) inside `<details>` | progressive disclosure; most artifacts need only L1+L2 |
| A hand-drawn conceptual flow / whiteboard-style sketch | **Excalidraw** via the `excalidraw-mcp` skill → embed **inline SVG** (the durable copy) + save the source in `diagrams/<date>-<slug>.excalidraw.json` and link it with a relative `<a href="diagrams/...">` (the link checker then guards it) | default for sketchy/deliberate-layout diagrams; see `references/diagram-types.md`. An `excalidraw.com` link is a may-expire convenience, never the only copy; export it from standalone text or it renders blank |
| A UI concept | low-fi ASCII / CSS wireframe in `<pre>` or bordered boxes | conveys layout without a design tool |
| A metric / status snapshot | metric tiles + status pills | colour **and** an icon/label, never colour alone |
| A metric / trend over time | inline-SVG sparkline or pure-CSS bar | no chart library; recipes in `references/diagram-types.md` |
| A KPI number **and** its trend | a `.tile` with an inline-SVG `.spark` sparkline | fill the area, emphasize the endpoint - the endpoint is the number the reader came for |
| A metric **vs the previous period** | a `.tile` with `<span class="delta down good">−12%</span>` | direction (up/down) and valence (good/bad) are orthogonal - an error-rate *drop* is `down good`. Carry the direction in accessible text (a signed value like `−12%`, or `aria-label="down 12%"`), never in the arrow glyph alone (it is hidden from screen readers) |
| An **explanatory chart the reader reasons about** (trend, scoring curve, before/after over a range, multi-series comparison) | an **interactive** inline-SVG chart: static marks + a vanilla-JS hover / crosshair / tooltip / legend-toggle layer | progressive enhancement - renders fully with **no JS**, JS only enhances; recipe in `references/diagram-types.md` "Interactive charts" |
| A **number in a sentence the reader should play with** (an assumption, rate, threshold) | a **reactive inline value** - scrubbable / arrow-adjustable, with dependent numbers/formula/chart recomputing live | progressive enhancement (static shows the default scenario); recipe in `references/diagram-types.md` "Reactive inline values" |

**Callouts** (CSS baked into every scaffold): `<div class="callout callout-note">…</div>` - also `-tip`, `-warning`, `-important`; the first child `<strong>` is the label and gets an icon. Use sparingly: **1 - 2 per artifact, never consecutive**, or they stop signalling.

**Layered understanding:** lead with the overview (a diagram, or the C4-L1 box) and put the deep version behind `<details>`, so a skimmer sees the shape and a deep reader expands. These are levels of *detail*, not audience tiers - don't gate them by role.

**Interactive charts are encouraged wherever they aid understanding** (which is the whole point of an artifact). The default for explanatory data is a **static-SVG chart enhanced with a vanilla-JS hover / crosshair / tooltip / legend layer** - progressive enhancement, so the chart still renders with no JS (Quick Look, email, offline) and JS only adds the interaction. See `references/diagram-types.md` "Interactive charts". Reserve heavyweight *explorable* app-like visuals (live zoom/pan, animated simulation, real-time streams) for flagship artifacts or the `prototype` kind; only those may warrant a charting library (Chart.js/ECharts/Recharts as a bounded escalation, same reference, always with a no-JS floor per Rule 9).

## Anti-slop checklist

Before finalising any artifact, scan for these "AI default" tells and remove them - three or more means restart the styling:

- **Gradient hero / gradient-text headings** - flat colour + real type hierarchy instead.
- **Violet/indigo accent ramp** (`#8b5cf6` / `#7c3aed` / `#a78bfa`) - one purposeful accent, not the LLM-default purple.
- **Emoji as section icons / bullets / status** - use a callout label or a real badge.
- **Glassmorphism / backdrop-blur** on a document - opaque surfaces (blur is prototype-only).
- **Card-everything / three-equal-card rows / dashboard chrome with no real metrics** - prose and tables where they carry meaning; cards only when they do.
- **Placeholder / fake data** (lorem ipsum, John Doe, Acme, invented 99% / 10x) - real values, or label them `sample`.
- **Filler vocabulary** (Elevate, Unlock, Seamless, Transform, Delve) and self-deprecating labels ("rough preview").
- **"Generated by AI" footers, loading spinners on a static doc, Inter/Roboto/Arial as the only personality.**
- **Decorative structure** - 01/02/03 section markers, dividers, or kickers that don't encode a real sequence or grouping. Number steps, sequences, and timelines; nothing else.

The validator enforces a mechanical, low-false-positive subset as a `slop-signal` WARN (violet hexes, emoji-in-heading, `lorem ipsum`, "Generated by AI"); the rest is judgment.

**Token discipline:** one accent colour used in at most a few places; never pure black on pure white (use the `--ink` / `--bg` tokens); derive tints with `color-mix()` rather than hand-picked rgba; if the project has a real design system (theme file / CSS vars), read it and match it. Scaffolds already ship a typography baseline (`text-wrap`, `tabular-nums`, kerning/ligatures, `accent-color`) and an `@media print` baseline (hides controls, `break-inside:avoid`, `print-color-adjust:exact` so status/severity colours survive print-to-PDF for handoff).

### Honor what's already there

Before styling, check `CLAUDE.md`, a theme/tokens file, and brand skills. Precedence: the user's own words > the workspace's existing design system > scaffold defaults. To inherit a brand, append a second `:root` block **after** the scaffold `<style>`:

```html
<style>:root { --accent: …; --accent-2: …; --accent-bg: …; --accent-line: …; --bg: …; --display: …; }</style>
```

Override accent / surface / display tokens only. Never touch the severity triples (they're semantic and contrast-locked to their tints). If the brand accent is low-contrast on the tinted backgrounds, keep the scaffold accent for text and use the brand hue for the display face and stripes only.

**Dark mode.** Every artifact and the gallery ship a light/dark toggle (fixed, top-right). The default follows the reader's OS (`prefers-color-scheme`); an explicit choice persists in `localStorage`; print always renders light. A plain `:root` brand override above styles the LIGHT theme only, because the scaffold's dark palette lives in more specific `:root[data-theme="dark"]` (and matching media) selectors that win over a plain `:root`. To brand the dark theme too, append a second override keyed to the dark selector:

```html
<style>:root[data-theme="dark"] { --accent: …; --bg: …; }</style>
```

To pin an artifact to open in light regardless of the reader's OS, set `<html data-theme="light">` (an individual reader can still switch with the toggle).

## Words are design material

The biggest lever on whether an artifact is *understood* (not just skimmed) is the prose itself - a separate, larger concern than defining coined terms (Rule 10). A glossary lets a reader look a word up; plain prose means they rarely need to. This is Claude's own artifact copy principle applied to a *document*: write from the reader's side of the screen.

**Document prose (the body of a plan / decision / review / architecture):**

- **Lead with the takeaway.** The first sentence of each section states the conclusion; the reasoning follows (inverted pyramid - a reader who stops after one line still leaves with the point). Push the deep version behind `<details>`.
- **One idea per sentence, one point per paragraph.** Break walls of text. A sentence with three clauses and two "which"es wants to be two sentences.
- **Short, concrete, active.** The plain word over the fancy one (*use*, not *utilize*; *so*, not *accordingly*). Active voice with a real subject ("the router picks the tool", not "the tool is selected by the router"). A concrete example beats an abstract description every time.
- **Cut hedging and filler.** Delete "it should be noted that", "in order to", "there is a X that", "basically", "essentially". Say the thing.
- **No em dashes.** Use a comma, colon, parentheses, or " - " instead. The validator WARNs on any em/en dash in prose (`em-dash` rule); dashes inside code blocks are exempt.
- **Name from the reader's side.** What people recognize, not how the system is built (a person manages *notifications*, not *webhook config*). Specific beats clever.

**UI copy (controls, states, errors - dashboards / prototypes):**

- A control label states exactly what happens, and its result state confirms it (`Copy parameters` → `Copied`).
- Error, empty, and fallback text says what went wrong and how to fix it - the layout-audit banner ("This artifact overflows horizontally at this width - wrap wide tables… or they will clip on a phone") is the house example: symptom, cause, fix.

This is **taught, not linted**: readability is judgment. Automated scores (Flesch-Kincaid) tank on legitimate dense technical prose and miss the real problem, so prose quality lives in the ship checklist below, never as a validator gate - the same judgment-lane split as Rule 10.

## Before you ship

Fast self-checks before declaring an artifact done:

- **Squint test** - blur your eyes: is the hierarchy still readable (one clear H1, scannable sections)?
- **Swap test** - would a generic dark theme make this indistinguishable from any other AI output? If yes, it has no point of view.
- **Both-themes / mobile** - check light (and dark if used) and a phone width; the runtime layout-audit banner flags horizontal overflow at the reader's actual width.
- **Jargon test** (the judgment lane the validator can't do) - read each heading and opening sentence as a PM. For every coined term: (1) *Can it be deleted or renamed to a recognized word?* - deletion beats definition; (2) would an outsider to this project get it on first read?; (3) swap the gloss in for the term in a sentence - does it still parse with no new mystery words? (bad: "customer churn is when customers churn"); (4) how many novel terms is the reader asked to hold at once? Above ~5, cut or rename rather than define more. A *necessary* domain term is not jargon - keep the right technical noun, just gloss it on first use.
- **Plain-prose test** (understandable, not just skimmable) - read your longest paragraph aloud. Does its first sentence carry the point? Any sentence you run out of breath on gets split. Any *utilize / in order to / it should be noted / basically* gets cut. Any "the X is done by Y" gets flipped to "Y does X". Could a PM restate the section in their own words after one read? If not, it isn't done - this is the lever the glossary can't pull.
- **Completeness** - no TODOs, ellipses, or "repeat for the rest"; no invented data unless labelled `sample`; mark uncertain claims with <span class="needs-verification">needs verification</span>.

## Further references

Deep-dive material lives in on-demand `references/` files so this skill stays lean (loaded only when relevant):

- **`references/patterns.md`** - adoptable patterns: collapsible deep-dives, tabbed code, design-system swatches, arrow-key deck nav, hosting/sharing (keep it local, GitHub Pages, optional bring-your-own-bucket S3 via `scripts/publish-s3.sh`, or any static host), the single-file posture, and the comprehension patterns **worked-example + self-explanation** and a **learner-paced stepper**.
- **`references/workflow-integrations.md`** - the decisions-captured coding-agent handoff block (with confidence tiers), the meeting Q&A overlay schema, and the re-entry-context convention.
- **`references/diagram-types.md`** - concept→diagram decision tree, Mermaid traps, inline-SVG craftsmanship, micro-chart recipes, and the progressive-enhancement **interactive charts** + **reactive inline values** recipes.

## Developer reference

### File contract

```
docs/human-html/
  index.html                       auto-generated gallery
  README.md                        per-workspace contract restatement
  GLOSSARY.md                      workspace jargon definitions (seeded on init)
  YYYY-MM-DD-kind-slug.html        one artifact per file
  <collection>/
    index.html                     optional portable collection hub
    *.html                         collection pages, validated by metadata
```

Required metadata in every artifact:

```html
<meta name="artifact-kind" content="<one of 9 kinds>">
<meta name="artifact-audience" content="human">
<meta name="artifact-created" content="YYYY-MM-DD">
<meta name="artifact-source" content="<optional free text; the validator defaults it to 'local' when absent>">
<meta name="artifact-summary" content="<optional: one-line gallery card text; auto-derived from the PM-summary if absent>">
<meta name="artifact-keywords" content="<optional: comma-separated; derived from kind + slug if absent>">
<body data-human-html-artifact="true">
```

The `<head>` also carries a per-kind emoji SVG favicon (`<link rel="icon">`, a self-contained `data:` URI). It is chosen by kind and **stable across revisions** - do not change it on rework, since readers find the tab by its icon.

Before publishing, fill `<meta name="artifact-summary">` (or make the PM-summary's first bullet carry the one-line story): when both are empty the gallery card's subtitle falls back to the bare title, and a card whose subtitle repeats its title tells the reader nothing. Say what the artifact *concludes*, not what it *is*.

Required content (for artifacts created on or after `2026-05-25`):

```html
<section data-audience="pm" class="pm-summary"> ... </section>
<nav class="toc"> ... </nav>   <!-- required when >3 h2 sections; anchors must resolve -->
<!-- visuals required inside any h2/h3 whose heading matches the comparison regex -->
```

### Invocation

```bash
# Initialise a workspace (creates docs/human-html/, README, GLOSSARY, empty index)
python3 <skill-dir>/human_html_artifacts.py init

# Scaffold a new artifact with the per-kind section skeleton (also refreshes the gallery)
python3 <skill-dir>/human_html_artifacts.py new <kind> "<title>"

# Validate file contract + content contract; exits non-zero on errors, exits 0 on warnings
python3 <skill-dir>/human_html_artifacts.py check

# Manually regenerate the gallery (rarely needed; the autoindex hook handles it)
python3 <skill-dir>/human_html_artifacts.py index
```

The script resolves the workspace root differently for **read-side** vs **create-side** commands:

- **`check` / `index`** (locate an existing lane): 1) `$HUMAN_HTML_ROOT` if set; 2) walk up from the current directory - first ancestor containing `docs/human-html/` wins; 3) current directory. So these are callable from any subdirectory of a workspace.
- **`new` / `init`** (create): 1) `$HUMAN_HTML_ROOT` if set; 2) the **current directory** - create commands deliberately do **not** walk up, so an artifact lands in `docs/human-html/` of the project you are actually in, not a sibling's or ancestor's lane. If an ancestor already has a lane, `new` still creates in the CWD but prints a `WARN` (a separate lane forks the gallery); set `HUMAN_HTML_ROOT` to reuse the ancestor's.

`check` exits 1 on any error (file contract violation or content contract violation in an in-force artifact); warnings (read-map, Q&A schema, glossary linking, provenance schema gaps, metadata ribbon gaps) print to stderr with a `WARN:` prefix and do not affect the exit code.

`write_index` (called by `new`, `init`, `index`, and the autoindex hook) raises only on file contract errors so that content shape issues do not break gallery generation during iteration. Use `check` to surface content shape issues explicitly.

### Hooks

Both hooks live at `<skill-dir>/hooks/` (see Canonical examples above for what `<skill-dir>` means) and resolve workspace root via `$CLAUDE_PROJECT_DIR` -> `$CURSOR_PROJECT_DIR` -> `$CODEX_WORKSPACE` -> hook JSON `.cwd` -> `pwd` fallback. They are advisory only; neither blocks any tool call.

**Advisory hook** (`hooks/human-html-advisory.sh`, PreToolUse). Fires on `Edit | Write | MultiEdit | NotebookEdit | StrReplace`. When the target is `.md`, the slug matches an HIL pattern (`plan | review | audit | architecture | -arch- | -arch.md | explainer | understanding | research | decision | prototype | status | report | incident | postmortem | post-mortem`), AND the path is outside the Markdown-OK allowlist, the hook prints a suggestion to stderr pointing at this script. Exits 0 regardless. Cursor uses the thin wrapper `hooks/human-html-advisory-cursor.sh`, which forwards stderr as JSON `agent_message` on stdout.

**Autoindex hook** (`hooks/human-html-autoindex.sh`, PostToolUse). Fires on `Edit | Write | MultiEdit | StrReplace` to any file under `<workspace>/docs/human-html/` with an `.html` extension, except the root gallery `index.html` itself. Also handles Codex `apply_patch` events by conservatively regenerating the gallery whenever `docs/human-html/` exists, because Codex patch events do not always expose a single target path. Shell-tool events (`Bash | Shell | exec_command | functions.exec_command`) are indexed only when the command references `human_html_artifacts.py` or `docs/human-html`. Runs the script's `index` subcommand to keep the gallery current. Exits 0 regardless.

### Wiring

Claude Code: add to `<workspace>/.claude/settings.json` `hooks` section:

```json
{
  "PreToolUse": [{
    "matcher": "Edit|Write|MultiEdit|NotebookEdit",
    "hooks": [{"type": "command", "command": "<skill-dir>/hooks/human-html-advisory.sh", "timeout": 5}]
  }],
  "PostToolUse": [{
    "matcher": "Edit|Write|MultiEdit|Bash",
    "hooks": [{"type": "command", "command": "<skill-dir>/hooks/human-html-autoindex.sh", "timeout": 10}]
  }]
}
```

Codex: enable hooks in `<workspace>/.codex/config.toml`, then wire the commands in `<workspace>/.codex/hooks.json` or the equivalent Codex hook config. The PreToolUse advisory matcher should include `Edit|Write|MultiEdit|NotebookEdit|StrReplace`; the PostToolUse autoindex matcher should include `Edit|Write|MultiEdit|StrReplace|apply_patch|Bash|Shell|exec_command|functions\.exec_command` when the hook system exposes shell events. The hook scripts are agent-neutral; they read JSON from stdin in the same shape that Claude Code, Codex, and Cursor emit (`tool_name`, `tool_input`, optional `.cwd`).

Cursor: add `<workspace>/.cursor/hooks.json` (schema `version: 1`) and symlink the hook scripts into `<workspace>/.cursor/hooks/`:

```json
{
  "version": 1,
  "hooks": {
    "preToolUse": [{
      "command": ".cursor/hooks/human-html-advisory-cursor.sh",
      "matcher": "Edit|Write|MultiEdit|NotebookEdit|StrReplace",
      "timeout": 5
    }],
    "postToolUse": [{
      "command": ".cursor/hooks/human-html-autoindex.sh",
      "matcher": "Edit|Write|MultiEdit|StrReplace|Shell",
      "timeout": 10
    }]
  }
}
```

Symlink `~/.cursor/skills/human-html` to the canonical skill (typically via `~/.claude/skills/human-html`). The symlink makes the skill available to Cursor setups and universal installers that read `~/.cursor/skills/` (Cursor's native skill discovery varies by version); the hook wiring above works regardless. The advisory wrapper is required because Cursor surfaces hook nudges via JSON stdout, not stderr.

### Workspace customization

Each workspace MAY ship a `.human-html-allowlist` file at the workspace root with one path pattern per line. The advisory hook reads it and appends entries to its baseline allowlist, so a workspace with custom Markdown lanes (e.g. `myproject/notes/`) can carve them out without editing the global hook.

Example `.human-html-allowlist`:

```
# Workspace-specific Markdown lanes that should NEVER trigger the HTML advisory.
# One glob-style pattern per line (matched against path relative to workspace root).
# Lines starting with # are comments. Blank lines ignored.
myproject/notes/*
internal/runbooks/*
```

Built-in baseline allowlist (applies to every workspace, no customization needed):

- Protocol files at any depth: `AGENTS.md`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `MEMORY.md`
- Workspace-root Markdown lanes: `docs/drafts/`, `docs/tickets/`, `docs/references/`, `docs/contracts/`, `docs/architecture/`, `docs/adr/`, `docs/agents/`, `docs/reports/`, `docs/presentations/`, `meetings/`, `archive/`
- Hidden/build/agent dirs at any depth: `.git/`, `.venv/`, `.pytest_cache/`, `.codex/`, `.claude/`, `.cursor/`, `.worktrees/`, `node_modules/`, `reviews/`, `tests/results/`

### Per-workspace adoption

To opt a new workspace into the harness:

```bash
cd <workspace>
python3 <skill-dir>/human_html_artifacts.py init
python3 <skill-dir>/human_html_artifacts.py deps   # report optional companions + how to get them
# wire the two hooks into .claude/settings.json, .codex/hooks.json, and .cursor/hooks.json
# optionally seed .human-html-allowlist with workspace-specific MD lanes
# edit docs/human-html/GLOSSARY.md to add domain terms specific to this workspace
```

### Requirements & companions

Install the skill with `npx skills add rhnfzl/human-html`, or clone the repo and symlink it into your agent's skill directory (`<skill-dir>`). Either way, nothing beyond the skill's own files is auto-installed. The good news: human-html needs almost nothing.

- **Hard requirement: none beyond Python 3 stdlib.** `human_html_artifacts.py` uses Python 3 stdlib only, no `pip install`.
- **Optional companion - `excalidraw-mcp` skill** (+ the Excalidraw MCP server in your client). Only needed for hand-drawn `<dfn>` flow diagrams (Rule 10 / `references/diagram-types.md`). Without it, the diagram menu's mermaid / inline-SVG / table / img options cover every content-contract need. Add it by symlinking the canonical skill into `~/.claude/skills/excalidraw-mcp`.
- **Optional - `mmdc` (mermaid CLI)** for rendering mermaid to inline SVG in shipped artifacts. Live-CDN mermaid is fine for drafts. `npm i -g @mermaid-js/mermaid-cli`.

`human_html_artifacts.py deps` reports which of these are present and how to get the rest. `deps --fix` does the one safe automation available: it symlinks an already-on-disk `excalidraw-mcp` into any client skill dir (`~/.claude/skills`, `~/.codex/skills`, `~/.cursor/skills`) that exists but lacks it - never clobbering an existing entry, never creating a client dir that isn't set up, and never touching the Excalidraw MCP server config (that lives in client config and is out of a script's reach). Without `--fix` it only reports.

After init: every `new <kind> "<title>"` writes a scaffold (PM-summary block + nav + per-kind section skeleton, all passing the content contract) and refreshes `index.html`; the autoindex hook catches later direct artifact edits, and the advisory hook nudges if an HIL-shaped MD slips through.

### Rollback

A workspace that does not benefit from HTML artifacts can simply omit `docs/human-html/`. The autoindex hook is silent when no artifact write occurs; the advisory hook nudges only on HIL-shaped MD writes; neither hook fails if the script is missing. There is no global state to undo.

To opt out of the content contract for one artifact, the cleanest path is to back-date its `artifact-created` metadata to before `2026-05-25` (and the filename to match), which moves it into the grandfathered set. Use this rarely; the content contract is there to make the artifact better.

### Standards context (2026)

- **AI-content disclosure (EU AI Act Art. 50, in force 2 Aug 2026)** applies to AI-generated text *published to inform the public on matters of public interest* - internal planning / handover artifacts are out of scope, so the provenance footer is good practice, not a compliance requirement here. Do not over-build it.
- **Agent interoperability (A2A v1.0, 2026)** models an agent's output as an "Artifact" object; these HTML artifacts are the human-facing cousin. No integration is needed today - the alignment is just why keeping the decisions-captured and handoff blocks structured pays off later.

Documented drifts from the single-file ideal live in the "Single-file is the default; cross-links are the exception" subsection of `references/patterns.md`.
