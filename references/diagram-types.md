# Diagram types - when to pick which

Every comparison section in a `human-html` artifact must ship a visual (the validator blocks if not). This reference is the decision tree for which kind of visual fits which kind of comparison.

The options the validator accepts as "a visual":

1. **Mermaid diagram** (`<div class="mermaid">...</div>`) - structural or flow comparison
2. **Side-by-side code panels** (a `grid-cols-2` div with two `<pre>` children) - signature or text shape change
3. **Comparison table** (`<table>`) - enumeration with attributes
4. **SVG or `<img>`** - anything custom that the three above cannot express
5. **`<pre class="diagram">`** (ASCII / CSS-box sketch, e.g. a C4-L1 diagram), or any element carrying **`data-visual="true"`** as an explicit escape hatch

Pick the smallest of these that does the job. A four-row table is better than a mermaid graph with four nodes; a side-by-side `<pre>` is better than a screenshot of a code editor.

---

## When to use mermaid

Use mermaid when the change is **structural** - the shape of the system, the modules, the arrows between them, or the flow of data.

Signals you want mermaid:

- The comparison is between two architectures, two module graphs, two flowcharts, two state machines.
- Reader needs to follow arrows or see "this connects to that".
- Boxes-and-lines convey the change better than prose.
- You would otherwise draw it on a whiteboard.

Pattern (architecture before / after):

```html
<div class="grid-cols-2">
  <div class="compare-before">
    <strong>Before</strong>
    <div class="mermaid">
flowchart TB
  A[server.py 3,216 LOC] --> W1[wrapper 1]
  A --> W2[wrapper 2]
  A --> Wn[wrapper N]
    </div>
  </div>
  <div class="compare-after">
    <strong>After</strong>
    <div class="mermaid">
flowchart TB
  A[server.py ~600 LOC] --> R[register_composite_tool]
  R --> I1[impl 1]
  R --> I2[impl 2]
    </div>
  </div>
</div>
```

**Label placement:** the `Before` / `After` label must be the panel's **first child** (`<div class="compare-before"><strong>Before</strong> …`). The scaffold styles only `> strong:first-child` as the uppercase mono kicker, so a `<strong>` deeper in the panel prose stays inline - put the label first or it won't render as a kicker.

Avoid mermaid when:
- The comparison is purely text or values (use a table).
- The graph has 15+ nodes (consider splitting into multiple diagrams, or moving to SVG).
- You need pixel-perfect layout (mermaid auto-lays-out; use SVG or `<img>` for control).

**Shipping vs drafting:** author diagrams in mermaid, but for the *shipped* artifact prefer rendering to inline SVG (via the Mermaid render tool or `mmdc`) with the mermaid source kept in an adjacent `<details><pre>` for editability. Live CDN mermaid is fine while iterating, but the shipped state should not depend on jsdelivr being reachable or JS running - iOS Quick Look, email previews, and offline archives render neither. The scaffold's `.mermaid:not([data-processed])` styling is the no-JS face of a diagram you chose to leave live: legible source, not breakage. The scaffold's Mermaid loader is self-gating (it only fetches the CDN when a `.mermaid` element is present), so a diagram-free artifact already makes no CDN request; rendering to inline SVG goes one step further and drops the CDN **and** the JS dependency for the diagram-bearing artifact too (SVG cost is ~10 - 40 KB per diagram, paid only by artifacts that have one).

---

## When to use side-by-side code panels

Use side-by-side `<pre>` panels when the change is in the **shape of a piece of code or text** - a function signature, a config block, a JSON envelope, an error message.

Signals you want side-by-side code:

- The reader's eye should land on a specific line, character, or argument.
- The before / after fits in ~10-15 lines per side.
- Whitespace and exact characters matter (function signatures, JSON shapes, CLI flags).

Pattern (signature change):

```html
<div class="grid-cols-2">
  <div class="compare-before">
    <strong>Before - 22 params</strong>
    <pre><code>def create_complete_job_impl(
  title,
  base_url, auth_manager, http_session,
  max_retries, retry_delay_ms,
  inter_call_delay_ms, logging_mode,
  ... 14 business params
):</code></pre>
  </div>
  <div class="compare-after">
    <strong>After - 16 params</strong>
    <pre><code>def create_complete_job_impl(
  ctx: ApiContext,
  title,
  ... 14 business params
):</code></pre>
  </div>
</div>
```

Avoid side-by-side code when:
- The change is structural rather than textual (use mermaid).
- The code blocks are more than ~15 lines each (the reader cannot diff them visually; use a table summarizing the change instead, with line references).
- You're enumerating N items (use a table).

---

## When to use a comparison table

Use a `<table>` when the change is an **enumeration of N items with attributes** - N rows of "thing X used to do A, now does B".

Signals you want a table:

- The reader needs to compare N items, where N is more than 2.
- Each item has the same attributes (status, owner, file location, before-value, after-value).
- The "before" and "after" can each be a one-line cell.

Pattern (enumeration of helpers being relocated):

```html
<table>
  <thead>
    <tr><th>Concern</th><th>Helpers</th><th>Currently in</th><th>Belongs in</th></tr>
  </thead>
  <tbody>
    <tr>
      <td>Composite lifecycle</td>
      <td><code>_start_composite</code>, <code>_end_composite</code>, <code>_phase</code></td>
      <td><code>_helpers.py</code></td>
      <td>a <em>CompositeSpan</em> context manager</td>
    </tr>
    <tr>
      <td>Company resolution</td>
      <td><code>_autodiscover_company_id</code>, <code>_resolve_company_scope</code></td>
      <td><code>_helpers.py</code></td>
      <td>a <em>CompanyScope</em> resolver module</td>
    </tr>
  </tbody>
</table>
```

Avoid tables when:
- N = 2 (use a side-by-side panel; the table is overkill).
- The attributes are different per row (the table will be ragged; use prose with sub-headings).
- The comparison is structural (use mermaid).

---

## When to use SVG or `<img>`

Fall back to SVG or `<img>` when none of the above fit. Examples:

- A timeline view with annotated stages.
- A radar chart, sequence diagram with custom layout, or any chart Chart.js / D3 produces.
- A screenshot of an existing UI for a "current vs proposed UX" comparison.
- A diagram from an external tool (draw.io, Excalidraw, Lucidchart) where redrawing in mermaid would lose nuance.

Inline SVG is preferred over `<img>` because it stays self-contained (no external image fetch, no broken-image risk when the artifact is moved). Embed Excalidraw SVG exports directly.

```html
<svg viewBox="0 0 600 200" xmlns="http://www.w3.org/2000/svg">
  <!-- custom timeline / chart / annotated diagram -->
</svg>
```

If you must use `<img>`, keep the image inside `docs/human-html/` (the validator's link checker requires assets be in-tree) and prefer SVG over PNG so the artifact remains crisp at any zoom level.

### Hand-drawn conceptual / flow diagrams → Excalidraw (default)

When the diagram is a *conceptual* flow, architecture-for-humans, or annotated whiteboard sketch (the kind you'd draw on a whiteboard in a refinement) - and mermaid's auto-layout would fight you - author it in Excalidraw via the `excalidraw-mcp` skill, then embed it as **inline SVG** in the artifact. This is the standing default for these diagrams; do not paste an `excalidraw.com` link as the only copy (external, rot-prone).

Three artifacts, three roles:

1. **Inline `<svg>` in the HTML** - the **canonical, durable copy**. Self-contained, always renders, prints, diffs in git, survives a strict CSP. This is the one that must never be lost; everything else is a convenience.
2. **`docs/human-html/diagrams/<date>-<slug>.excalidraw.json`** - the regeneration source, saved in the **`diagrams/` subdir** (keeps the artifact root uncluttered). **Reference it from a caption with a relative `<a href="diagrams/<date>-<slug>.excalidraw.json">`** - the built-in link checker validates any in-tree `href` target exists, so linking the sidecar makes "the source is really saved" a mechanically-guarded fact for free. This is MCP-source (excalidraw-mcp `create_view` / export format), for regeneration - not a native `.excalidraw` scene, so it does not drag-drop into excalidraw.com.
3. **(optional) an `excalidraw.com` share link** - a *may-expire* convenience for one-click editing, never the durable copy (that's the SVG). If you include it, say it can expire.

**Export gotcha (load-bearing, and the #1 cause of a blank share link):** `excalidraw.com`'s importer silently drops the excalidraw-mcp `label:{}` shorthand on shapes - it keeps only real `text` elements. So a sidecar authored with `label:` shorthand exports to a **blank** excalidraw.com canvas. When exporting a share link, first **convert every `label` into a standalone `text` element** (centered on its shape, with explicit `width`, `height`, `fontFamily:1`), then export. Verify a fresh render before shipping the link (`qlmanage -t` on the extracted SVG works headless on macOS when Playwright/Chrome is unavailable).

Mermaid stays the default for *mechanical* structure (flowchart / sequence / state / ER) where auto-layout is a feature; reach for Excalidraw when the diagram wants deliberate hand placement, callouts, and a human, sketchy feel.

---

## Quick decision tree

```text
What is changing in this comparison?

  -> System shape / module graph / flow         → mermaid
  -> Function signature / JSON envelope / text  → side-by-side <pre>
  -> N items with shared attributes (N > 2)     → comparison <table>
  -> N = 2 with different per-item attributes   → side-by-side panels with prose
  -> None of the above (chart, timeline, UX)    → inline <svg> (or <img> as fallback)
```

When in doubt, pick the smallest visual that does the job. A reader who scans your before / after section for three seconds and walks away with the right mental model is the test.

## Mermaid traps (read before hand-authoring)

These fail *silently* (the diagram renders as raw text or mislays itself) and are only learnable by hitting them:

- **Never define `.node` or `.card` at page scope.** Mermaid puts `.node` on its own SVG `<g>` elements; a page-level `.node`/`.card` rule leaks in and breaks diagram layout. Scope your CSS or rename the class.
- **Never set `color:` in a Mermaid `classDef`** - it hard-codes a text colour that becomes invisible in the opposite theme. Use 8-digit-hex fills and a `.nodeLabel` CSS override instead.
- **`sequenceDiagram` / `stateDiagram-v2` forbid `{}[]<>&` and colons in labels** - one stray character makes the *whole* diagram render as raw text. Use `flowchart TD` with quoted labels for anything with punctuation.
- **Prefer `flowchart TD` over `LR`** once you pass ~4 nodes or any branching - LR overflows horizontally on phones (and trips the layout-audit banner).
- **Native `C4Context` ignores the theme** - render C4 as `graph TD` + `subgraph` (or CSS boxes) so it inherits your colours.
- **Arrow vocabulary carries meaning:** `-->` dependency, `-.->`  optional/async, `==>` emphasis, `--x` blocked.
- **15+ elements** → don't cram one Mermaid graph; show a Mermaid overview + a CSS-grid of detail cards.
- **Keep the generator's `themeVariables` block when hand-editing `_MERMAID_SCRIPT`.** It pins a `theme:"base"` palette to the `:root` tokens; delete it and nodes revert to stock lavender `#ECECFF` - off-palette and adjacent to the violet ramp the anti-slop checklist bans.

## Inline-SVG craftsmanship (when SVG beats Mermaid)

- Set `viewBox`, not fixed `width`/`height`; use `currentColor` for ink so it's dark-mode-free.
- Box text needs `dominant-baseline:central` or it sits ~4px high; arrow markers need `fill` set or they render as black blobs.
- Use real `<text>` (not paths), round your coordinates, and pre-compute column/tier widths before layout. Keep to ~4-5 nodes - past that, reach for Mermaid.
- Micro-charts without a library: a `<polyline>` sparkline, CSS/SVG horizontal bars, or a pure-CSS progress bar cover most status/incident metric needs.

## Micro-chart recipes (no library)

Copy-paste and theme-aware (via `currentColor`). Note: these lean on the scaffold's built-in component CSS (`.spark` / `.bars` / `.progress` / `.fill`), so inside a human-html artifact they render as-is; pasted into a non-scaffold page, inline the matching ~10 lines of CSS or the marks fall back to SVG defaults (black fills). For status/incident metric sections.

**Sparkline** (trend in a line) - fill the area faintly and emphasize the endpoint; the endpoint is the number the reader came for:

```html
<svg class="spark" viewBox="0 0 100 28" width="120" height="28" role="img" aria-label="trend: 12 to 31">
  <line class="grid" x1="0" y1="14" x2="100" y2="14"/>
  <path class="fill" d="M0,22 L20,16 L40,18 L60,10 L80,12 L100,5 V28 H0 Z"/>
  <polyline class="line" points="0,22 20,16 40,18 60,10 80,12 100,5"/>
  <circle class="dot" cx="100" cy="5" r="2.5"/>
</svg>
```

The `.spark` class (and `.spark.good` / `.warn` / `.crit`) is built into the scaffold - it strokes the line, fills the area at ~12% opacity, draws the baseline grid, and fills the endpoint dot in `currentColor`. `overflow: visible` keeps the edge dot from clipping.

**Pure-CSS progress bar** - the scaffold's `.progress` is the track, its `.fill` is the bar; set the width with the `--w` custom property and pick a colour with a severity class:

```html
<div class="progress"><span class="fill warn" style="--w:72%"></span></div>
```

**Horizontal bars** (compare a few values) - `.bars` is a `<dl>` grid (label / track / value), no SVG. Each bar is `<dd class="track"><span class="fill warn" style="--w:85%"></span></dd>`; the value cell gets `tabular-nums` via `.val`:

```html
<dl class="bars">
  <dt>p50</dt><dd class="track"><span class="fill good" style="--w:40%"></span></dd><dd class="val">120ms</dd>
  <dt>p99</dt><dd class="track"><span class="fill warn" style="--w:85%"></span></dd><dd class="val">840ms</dd>
</dl>
```

The `.fill` severity classes are `crit` / `high` / `warn` / `good` (default is `--accent`). Both `.progress` and `.bars` print correctly (the scaffold's `@media print` keeps their fills) - the old inline-`style` bars vanished in print-to-PDF.

Reach for these before a charting library - they cost no CDN and survive offline / strict-CSP / print.

## Interactive charts (progressive enhancement) - the default for explanatory data

The micro-charts above are for status tiles. When a chart's *job is to explain a concept* (an S-curve, a scoring function, a trend the reader must reason about), make it **interactive** - hover tooltips, a crosshair, legend toggles. Understanding is human-html's whole point (see SKILL.md "Words are design material"), and an HTML/SVG chart *is* interactive by default: the hover layer is part of the deliverable, not an upgrade.

**The rule that keeps this Rule-9-safe: static SVG is the chart, JS only enhances it.** The marks (lines, bars, dots, axes, tick labels, legend) live in the static inline SVG, so the full chart renders with **zero JS** (Quick Look, email, offline archive all show it). A small dependency-free `<script>` then layers on the interaction. Because the chart is already complete without JS, there is **no blank-screen risk and no `<noscript>` banner needed** - this is the cleanest form of progressive enhancement. Never build the marks in JS (`el.innerHTML = "<svg…"`): that is the `js-content-fallback` violation and it *does* go blank.

**Interaction spec:** (the `dataviz` cross-refs here - `interaction.md` / `choosing-a-form.md` / `color-formula.md` / `palette.md` - live in the **separate `dataviz` skill**; if it isn't installed, the human-html scaffold's own tokens/palette are the fallback and these recipes still stand alone.)
- **Line/area:** a crosshair hairline tracks the pointer and snaps to the nearest x; **one tooltip lists every series** at that x (the reader never has to land on a line).
- **Bar/dot/cell:** the mark is the hit target and lifts on hover; its own tooltip shows category + value.
- **Keyboard parity:** the same tooltip appears on `focus` as on hover; hit areas are focusable (`tabindex="0"`).
- **Hit target ≥ 24px**, bigger than the painted mark (an 8px dot is unhittable); for dense scatter use a nearest-point layer.
- **Untrusted labels** (series/category names from data/CSV/tools) go into the DOM via `textContent`, **never** `innerHTML` string-building.
- **Values lead, labels follow;** key a tooltip row with a short stroke of the series colour, not a filled box.
- Ship a **table-view fallback** (`<details><table>`) so every value is reachable without hovering, and stay theme-aware via tokens / `currentColor`.
- **Caption the chart with its finding (an "action title"), not a description** - "Revenue overtook target in April", not "Revenue vs target by month". The reader gets the point before parsing the marks; the chart then supplies the detail.
- **Annotation often beats the tooltip layer for explanation.** For a chart making a point, draw the point *on* the marks - a threshold/reference line, an event marker, a direct label on the key data point - rather than hiding it behind hover. Reserve interactivity for exploration the reader initiates.
- **Dense data (roughly 100+ points, any form):** per-x hit columns and per-mark hit areas stop scaling - replace them with one full-width transparent overlay `<rect>` that maps pointer-x to the nearest data index (a nearest-x layer, the line/bar analog of scatter's nearest-point), or bin/aggregate the data before plotting.

**This is a mechanism, not a template - do not ship this exact chart.** The form should follow the *data's job*, not this example: magnitude → bars, correlation → scatter, composition → stacked/donut, density → heatmap, a function or series over a range → line/curve (pick it with dataviz `references/choosing-a-form.md`). What you reuse across every form is the invariant: **(1)** the static marks live in SVG, **(2)** the scaling helper below turns data → pixels, **(3)** the same interaction layer (crosshair/hit-target + one tooltip + legend toggle + keyboard) enhances them. Read the example for that pattern, then build the chart your data needs. What stays invariant is the value→pixel scaling helper; what you regenerate per form is **both** the static marks **and** the interaction layer (a bar chart drops the crosshair for per-mark tooltips; a dense scatter needs a nearest-point layer).

**Regenerate the coordinates; never reuse the numbers below.** The pixel values in the example are specific to 5 categories on a 0 - 100 domain. Run the scaling helper at authoring time over YOUR data and domain and paste its output as the static marks (a ~15-line `{labels, series, domain} → marks` step at author time is worth writing). Two more adaptation rules the example bakes in and you must redo: **(a)** derive the axis from the data, not 0 - 100 - pick a domain that frames the values (round to nice min/max), choose 4 - 6 "nice" tick values, and handle negatives (baseline at `scaleY(0)`, not the bottom) and time axes (dates → evenly spaced x or true time scale); **(b)** the recipe is **per-instance scoped** (`class="hh-chart"` + `currentScript.closest`, like the reactive-value and stepper recipes), so a second chart in the same artifact is just a second copy of the whole `<figure>` - no id surgery; regenerate its marks and pick the interaction layer that fits its form.

Worked example (the pattern shown once, on a two-series line chart) - fully readable statically, enhanced with crosshair + one-tooltip-all-series + legend toggle + keyboard focus. Self-contained, no CDN, no library:

```html
<figure class="hh-chart" style="margin:var(--s-8) 0;position:relative;">
  <style>
    /* Series colours are CATEGORICAL, NOT the reserved status tokens (--good/--crit/--warn - those mean state, per dataviz). Series 1 uses the brand accent; series 2 uses a distinct categorical hue. For 3+ series pull a validated categorical palette from dataviz references/palette.md. */
    .hh-chart{--cd-b:#0d7a86}
    .hh-chart .cd-axis{stroke:var(--line-strong);stroke-width:1}
    .hh-chart .cd-grid{stroke:var(--line);stroke-width:1}
    .hh-chart .cd-tick{fill:var(--muted);font:11px var(--mono);}
    .hh-chart .cd-s1{stroke:var(--accent);stroke-width:2;fill:none}
    .hh-chart .cd-s2{stroke:var(--cd-b);stroke-width:2;fill:none}
    .hh-chart .cd-dot1{fill:var(--accent)} .hh-chart .cd-dot2{fill:var(--cd-b)}
    .hh-chart .cd-series.hidden{opacity:.12}
    .hh-chart .cd-cross{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3;opacity:0}
    .hh-chart .cd-legend{display:flex;gap:16px;margin:8px 0 0 44px;font-size:var(--fs-sm)}
    .hh-chart .cd-legend button{display:inline-flex;align-items:center;gap:6px;background:none;border:0;color:var(--ink-2);cursor:pointer;font:inherit;padding:2px 4px}
    .hh-chart .cd-legend button[aria-pressed="false"]{color:var(--faint);text-decoration:line-through}
    .hh-chart .cd-key{width:14px;height:2px;display:inline-block}
    .hh-chart .cd-tip{position:absolute;pointer-events:none;opacity:0;transform:translate(-50%,-100%);background:var(--surface);border:1px solid var(--line-strong);border-radius:var(--radius-sm);box-shadow:var(--shadow);padding:6px 9px;font-size:var(--fs-sm);white-space:nowrap}
    .hh-chart .cd-tip b{font-variant-numeric:tabular-nums}
    .hh-chart .cd-tip .r{display:flex;align-items:center;gap:6px;color:var(--muted)}
    .hh-chart .cd-hit{fill:transparent}
    .hh-chart .cd-hit:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
  </style>
  <svg viewBox="0 0 620 320" width="620" height="320" role="group" aria-label="Two series, Jan to May" style="max-width:100%;height:auto;font-family:var(--sans)">
    <!-- y grid + ticks (0,25,50,75,100) -->
    <line class="cd-grid" x1="44" y1="20"  x2="596" y2="20"/>
    <line class="cd-grid" x1="44" y1="90"  x2="596" y2="90"/>
    <line class="cd-grid" x1="44" y1="160" x2="596" y2="160"/>
    <line class="cd-grid" x1="44" y1="230" x2="596" y2="230"/>
    <line class="cd-axis" x1="44" y1="300" x2="596" y2="300"/>
    <line class="cd-axis" x1="44" y1="20"  x2="44"  y2="300"/>
    <g text-anchor="end">
      <text class="cd-tick" x="38" y="304">0</text><text class="cd-tick" x="38" y="234">25</text>
      <text class="cd-tick" x="38" y="164">50</text><text class="cd-tick" x="38" y="94">75</text>
      <text class="cd-tick" x="38" y="24">100</text>
    </g>
    <g text-anchor="middle">
      <text class="cd-tick" x="44"  y="316">Jan</text><text class="cd-tick" x="182" y="316">Feb</text>
      <text class="cd-tick" x="320" y="316">Mar</text><text class="cd-tick" x="458" y="316">Apr</text>
      <text class="cd-tick" x="596" y="316">May</text>
    </g>
    <!-- STATIC marks (render with no JS) -->
    <g class="cd-series" data-series="0">
      <polyline class="cd-s1" points="44,244 182,174 320,188 458,104 596,48"/>
      <circle class="cd-dot1" cx="44" cy="244" r="3"/><circle class="cd-dot1" cx="182" cy="174" r="3"/><circle class="cd-dot1" cx="320" cy="188" r="3"/><circle class="cd-dot1" cx="458" cy="104" r="3"/><circle class="cd-dot1" cx="596" cy="48" r="3"/>
    </g>
    <g class="cd-series" data-series="1">
      <polyline class="cd-s2" points="44,272 182,216 320,146 458,160 596,76"/>
      <circle class="cd-dot2" cx="44" cy="272" r="3"/><circle class="cd-dot2" cx="182" cy="216" r="3"/><circle class="cd-dot2" cx="320" cy="146" r="3"/><circle class="cd-dot2" cx="458" cy="160" r="3"/><circle class="cd-dot2" cx="596" cy="76" r="3"/>
    </g>
    <line class="cd-cross" x1="0" y1="20" x2="0" y2="300"/>
    <!-- per-x focusable hit columns (>=24px, keyboard + pointer) -->
    <g>
      <rect class="cd-hit" x="0"   y="20" width="113" height="280" tabindex="0" data-i="0" aria-label="Jan"/>
      <rect class="cd-hit" x="113" y="20" width="138" height="280" tabindex="0" data-i="1" aria-label="Feb"/>
      <rect class="cd-hit" x="251" y="20" width="138" height="280" tabindex="0" data-i="2" aria-label="Mar"/>
      <rect class="cd-hit" x="389" y="20" width="138" height="280" tabindex="0" data-i="3" aria-label="Apr"/>
      <rect class="cd-hit" x="527" y="20" width="93"  height="280" tabindex="0" data-i="4" aria-label="May"/>
    </g>
  </svg>
  <div class="cd-legend" role="group" aria-label="Toggle series">
    <button type="button" aria-pressed="true" data-series="0"><span class="cd-key" style="background:var(--accent)"></span>Revenue</button>
    <button type="button" aria-pressed="true" data-series="1"><span class="cd-key" style="background:var(--cd-b)"></span>Target</button>
  </div>
  <div class="cd-tip" role="status" aria-live="polite"></div>
  <details style="margin-top:12px">
    <summary>Data table</summary>
    <table><thead><tr><th>Month</th><th>Revenue</th><th>Target</th></tr></thead>
      <tbody>
        <tr><td>Jan</td><td>20</td><td>10</td></tr><tr><td>Feb</td><td>45</td><td>30</td></tr>
        <tr><td>Mar</td><td>40</td><td>55</td></tr><tr><td>Apr</td><td>70</td><td>50</td></tr><tr><td>May</td><td>90</td><td>80</td></tr>
      </tbody></table>
  </details>
  <script>
  (function(){
    var fig=document.currentScript.closest('.hh-chart'); if(!fig) return;   // per-instance: copy the whole <figure> twice and both charts work, no id surgery
    var XS=[44,182,320,458,596];                       // author-computed x pixels (must match the static SVG)
    var LABELS=['Jan','Feb','Mar','Apr','May'];
    var SERIES=[{name:'Revenue',vals:[20,45,40,70,90],color:'var(--accent)'},
                {name:'Target', vals:[10,30,55,50,80],color:'var(--cd-b)'}];
    var cross=fig.querySelector('.cd-cross'), tip=fig.querySelector('.cd-tip'),
        svg=fig.querySelector('svg'), groups=fig.querySelectorAll('.cd-series');
    var hidden={}, cur=null;
    function show(i){
      if(i==null || i===cur) return;      // same column: skip rebuild - no per-pointermove churn of the aria-live tooltip
      cur=i;
      cross.setAttribute('x1',XS[i]); cross.setAttribute('x2',XS[i]); cross.style.opacity='1';
      tip.textContent='';                                             // reset (textContent = untrusted-safe)
      var head=document.createElement('b'); head.textContent=LABELS[i]; tip.appendChild(head);
      SERIES.forEach(function(s,si){
        if(hidden[si]) return;
        var row=document.createElement('div'); row.className='r';
        var key=document.createElement('span'); key.className='cd-key'; key.style.background=s.color;
        var v=document.createElement('b'); v.textContent=s.vals[i];    // value leads
        var nm=document.createElement('span'); nm.textContent=s.name;  // label follows
        row.append(key,v,nm); tip.appendChild(row);
      });
      // position above the crosshair, clamped by the tooltip's OWN width so a wide multi-series
      // readout never clips at the left/right edge (offsetWidth is valid even at opacity:0)
      var r=svg.getBoundingClientRect(), sx=r.width/620, sy=r.height/320, half=(tip.offsetWidth||68)/2;
      var left=Math.max(half, Math.min(r.width-half, XS[i]*sx));
      tip.style.left=left+'px'; tip.style.top=(20*sy - 8)+'px'; tip.style.opacity='1';
    }
    function hide(){ cur=null; cross.style.opacity='0'; tip.style.opacity='0'; }
    fig.querySelectorAll('.cd-hit').forEach(function(h){
      var i=+h.dataset.i;
      h.addEventListener('pointermove',function(){show(i);});
      h.addEventListener('pointerleave',hide);
      h.addEventListener('pointercancel',hide);           // touch interrupted by a scroll/system gesture won't fire pointerleave
      h.addEventListener('focus',function(){show(i);});
      h.addEventListener('blur',hide);
    });
    fig.querySelectorAll('.cd-legend button').forEach(function(b){
      b.addEventListener('click',function(){
        var si=+b.dataset.series, on=b.getAttribute('aria-pressed')==='true';
        b.setAttribute('aria-pressed', on?'false':'true'); hidden[si]=on;
        groups[si].classList.toggle('hidden', on);
        var keep=cur; cur=null; if(keep!=null) show(keep);   // refresh a still-open (touch/keyboard-pinned) tooltip so it drops the hidden series
      });
    });
  })();
  </script>
  <figcaption style="margin-top:8px;color:var(--muted);font-size:var(--fs-sm)">Revenue overtook Target in April and pulled ahead through May.</figcaption>
</figure>
```

**The value→pixel scaling helper** (spell it out once; the static coordinates above were produced by it, and JS reuses the same numbers so hover lines up with the marks):

```js
// domain -> plot pixels. Plot box here: x 44..596, y 20..300, value 0..100.
var PX={x0:44,x1:596,y0:300,y1:20,vmin:0,vmax:100};
function scaleX(i,n){ return PX.x0 + (PX.x1-PX.x0)*i/(n-1); }      // categorical, n points
function scaleY(v){ return PX.y0 + (PX.y1-PX.y0)*(v-PX.vmin)/(PX.vmax-PX.vmin); }
// polyline points: SERIES[0].vals.map((v,i)=>scaleX(i,vals.length)+','+scaleY(v)).join(' ')
```

**Adapting the form (regenerate the marks *and* the interaction layer):**
- **Bars / columns** - swap the `<polyline>`s for `<rect>`s (`x=scaleX(i)`, `height=y0-scaleY(v)`, 4px rounded data-end, 2px surface gap between adjacent bars); the mark *is* the hit target (drop the crosshair), each `<rect>` lifts on hover and carries its own tooltip.
- **Scatter / bubble** - `<circle>` per point at `(scaleX(xv), scaleY(yv))`; give each a ≥24px transparent hit area (or a nearest-point layer for dense data) so the pointer only has to be closest, not dead-centre.
- **S-curve / scoring function** - a `<polyline>` over points sampled from the function (`scaleY(100/(1+Math.exp(-k*(x-x0))))` for a logistic), plus a dashed identity reference line (`stroke-dasharray`) and a couple of annotated points with guide lines + direct labels. This is the shape behind a scoring-function explainer.
- **Donut / stacked / heatmap** - same idea: static SVG arcs / segments / cells, then per-mark hover tooltips. A second axis is never the answer (dataviz: one axis) - use small multiples or index to a common base.

In every case the value→pixel scaling helper is unchanged; what you regenerate is the marks **and** the matching interaction layer (crosshair + one-tooltip for line/area; per-mark hover for bar/scatter/donut/heatmap; a nearest-point / nearest-x layer for dense data). Keep the dataviz palette/rules (categorical order, legend for ≥2 series, status colours reserved) regardless of form.

## When a charting library is worth it (bounded escalation)

The recipe above covers line / scatter / bar / donut with hover, crosshair, legend toggle, and keyboard - the interactivity most explanatory artifacts need, with no dependency. Reach for a real charting library only when the interaction genuinely earns it: **live zoom/pan, brushing, animated transitions, real-time streaming, or many-series dashboards** where hand-rolling the SVG+JS would be a slog. This is a `prototype`-kind (or dashboard) move, not the default.

When you do:
- **Match the Artifacts flavor.** In an HTML artifact, load **Chart.js** or **ECharts** from the CSP-allowlisted CDN (`cdnjs.cloudflare.com`); in a React artifact, **Recharts** is the Claude-Artifacts norm. Keep the dataviz palette and rules (`references/color-formula.md`, one axis, categorical order) regardless of library.
- **Serve it over a URL, never as a file.** A lib-driven chart needs JS, so it only works opened in a real browser (a static file host / S3 / GitHub Pages), not a Quick-Look/email preview. See "Sharing & hosting" in `patterns.md`.
- **Keep a no-JS floor (Rule 9).** Pre-render a static SVG snapshot or ship the `<details><table>` so a JS-less preview isn't blank; add the `<noscript>` banner from Rule 9 when the interactive canvas is the primary content.
- **Pin or self-host the library** (a versioned cdnjs URL, or vendor it into `docs/human-html/`) so the artifact doesn't rot when a CDN moves.

Default to the progressive-enhancement recipe; escalate to a library only when a specific interaction the reader needs cannot be hand-built cheaply.

## Reactive inline values ("Tangle-style") - interactive prose, the other half of explorable explanations

Interactive charts make the *picture* explorable; this makes the *prose* explorable. A reactive inline value is a number sitting in a sentence that the reader can **scrub (drag) or arrow up/down**, with dependent numbers / a formula / a chart recomputing live - "a reactive document lets the reader play with the author's assumptions and see the consequences" (the Tangle reactive-document pattern). It is the single highest-leverage explorable-explanation technique for building intuition, and it fits our model exactly.

**Rule-9 floor (non-negotiable):** the sentence must READ CORRECTLY with no JS. The input spans show their default value as plain text, and every dependent output is **pre-computed at authoring time for that default** and pasted in. JS only upgrades the inputs into controls and recomputes the outputs - so a no-JS view shows one coherent, correct default scenario, never a blank or a broken `{{expr}}`.

**No eval, ever:** the formula lives in an author-written `compute(vars)` JS function (the values are the artifact's own, but keep the habit). The engine calls it and writes named `[data-out]` spans with `textContent` (untrusted-safe). **Accessibility:** each scrubbable value is `role="spinbutton" tabindex="0"` with `aria-valuemin/max/now`, adjustable by drag **and** by Arrow keys (keyboard parity).

Worked example - "At R% for Y years, $1,000 becomes $Z" (R and Y are scrubbable; Z recomputes). Renders statically at the default 5% / 10y / $1,629:

```html
<figure class="rv-fig" style="margin:var(--s-8) 0">
  <style>
    .rv{font-weight:700;color:var(--accent);padding:0 1px;-webkit-user-select:none;user-select:none}
    /* the draggable affordance (dashed underline, resize cursor, focus ring) appears ONLY once JS upgrades the spans */
    .rv-live .rv{border-bottom:1px dashed var(--accent);cursor:ew-resize;touch-action:none}
    .rv-live .rv:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:2px}
    .rv-hint[hidden]{display:none}   /* guard: keep the hint hidden even under author display rules until JS unhides it */
  </style>
  <p style="line-height:2.1">At
    <span class="rv" data-var="rate" data-min="0" data-max="20" data-step="0.5" data-label="annual rate percent">5</span>%
    for
    <span class="rv" data-var="years" data-min="1" data-max="40" data-step="1" data-label="years">10</span>
    years, $1,000 becomes <b>$<span data-out="result" aria-live="polite">1,629</span></b>.
  </p>
  <p class="rv-hint" hidden style="font-size:var(--fs-sm);color:var(--muted)">Drag a value, or focus it and press the arrow keys.</p>
  <script>
  (function(){
    var fig=document.currentScript.closest('.rv-fig'); if(!fig) return;   // per-instance scope; works for multiple charts
    var inputs=fig.querySelectorAll('.rv'); if(!inputs.length) return;
    function compute(v){                                    // AUTHOR writes the formula here (no eval)
      return { result: Math.round(1000*Math.pow(1+v.rate/100, v.years)) };
    }
    function vars(){ var v={}; inputs.forEach(function(el){ v[el.dataset.var]=parseFloat(el.getAttribute('aria-valuenow')); }); return v; }
    function recompute(){ var o=compute(vars()); Object.keys(o).forEach(function(k){
      var el=fig.querySelector('[data-out="'+k+'"]'); if(!el) return;
      var t=o[k].toLocaleString('en-US');                    // fixed locale so readers in comma-decimal locales (de-DE, nl-NL, ...) don't see "1.629"
      if(el.textContent!==t) el.textContent=t;               // skip no-op writes so aria-live doesn't re-announce
    }); }
    inputs.forEach(function(el){
      var min=+el.dataset.min, max=+el.dataset.max, step=+el.dataset.step||1, dec=(String(step).split('.')[1]||'').length, drag=null;
      el.setAttribute('role','spinbutton'); el.tabIndex=0;   // upgrade to a control - the affordance exists only with JS
      el.setAttribute('aria-label', el.dataset.label||el.dataset.var);
      el.setAttribute('aria-valuemin', min); el.setAttribute('aria-valuemax', max);
      el.setAttribute('aria-valuenow', parseFloat(el.textContent));
      function set(val){ val=Math.max(min,Math.min(max,Math.round(val/step)*step));
        val=Number(val.toFixed(dec));                        // kill float noise from decimal steps (e.g. a 0.1 step -> 0.30000000000000004)
        if(val===+el.getAttribute('aria-valuenow')) return;  // no-op guard
        el.setAttribute('aria-valuenow',val); el.textContent=String(val); recompute(); }
      el.addEventListener('keydown',function(e){
        // stopPropagation so Arrow keys tune THIS value without ALSO triggering deck arrow-nav (patterns.md) on the same page
        if(e.key==='ArrowUp'||e.key==='ArrowRight'){ set(+el.getAttribute('aria-valuenow')+step); e.preventDefault(); e.stopPropagation(); }
        else if(e.key==='ArrowDown'||e.key==='ArrowLeft'){ set(+el.getAttribute('aria-valuenow')-step); e.preventDefault(); e.stopPropagation(); }
      });
      el.addEventListener('pointerdown',function(e){ drag={x:e.clientX,v:+el.getAttribute('aria-valuenow')}; el.setPointerCapture(e.pointerId); e.preventDefault(); });
      el.addEventListener('pointermove',function(e){ if(drag) set(drag.v + Math.round((e.clientX-drag.x)/6)*step); });
      var end=function(){ drag=null; };
      el.addEventListener('pointerup',end); el.addEventListener('pointercancel',end); el.addEventListener('lostpointercapture',end);
    });
    recompute();                                            // self-correct the pasted static default if the formula changed
    fig.classList.add('rv-live');                           // reveal the draggable affordance now JS is running
    var hint=fig.querySelector('.rv-hint'); if(hint) hint.hidden=false;   // and the how-to-use hint
  })();
  </script>
</figure>
```

The static output (`1,629`) is `compute({rate:5,years:10})` computed once at authoring time and pasted - recompute the default and paste it whenever you change the formula or defaults. Where the dependent value is a **chart**, the same `recompute()` redraws the marks (reuse the scaling helper above): a scrubbable `k` that reshapes a logistic curve is the canonical "understand the scoring function" explorable, and per `patterns.md` it is welcome in **any** kind (it explains the content), not just `prototype`. Keep it to 1 - 3 reactive values per sentence - past that the reader loses the thread (the Tangle reactive-document pattern's own caveat: some content wants static "magic ink", not interactivity).
