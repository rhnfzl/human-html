# Adoptable patterns

> On-demand reference for the human-html skill (kept out of SKILL.md to stay lean).

The patterns below go beyond the file-format switch. Adopt them selectively when the artifact's kind invites them.

## Collapsible `<details>` sections for deep dives

For artifacts where the main argument fits on one screen but supporting evidence is voluminous (review concerns with the full failing log; understanding docs with the deep-dive into one component; research syntheses with the underlying data), wrap the deep content in `<details>` so a skimmer sees the headline and a deep reader can expand:

```html
<details>
  <summary>Show the failing log (47 lines)</summary>
  <pre><code>...</code></pre>
</details>
```

Use sparingly. A heavily-collapsed artifact hides what the reader needs; a flat artifact buries it. The right call is to keep the load-bearing argument always visible and collapse only the *evidence* a reader might want to verify.

## Interactivity: explanation in any kind, product simulation only in `prototype`

Interactivity that *simulates the product* (a wizard, a stateful form, an app mockup) is the `prototype` kind's specialty: feeling the proposed thing IS the point there, and that same chrome would be noise in a status report or decision aid. A prototype that *demonstrates* (a slider that tunes a duration, a button that mutates state and shows the result, a copy-to-clipboard for the parameters that worked) lets the reader feel the proposed change instead of just reading about it. The `examples/prototype-canonical.html` reference includes a worked interactive slider + copy button demonstrating this pattern. Interactivity that *explains the content*, by contrast, is welcome in **any** kind - the distinction is drawn just below.

The distinction that matters is **not** chart-vs-chrome - it is what the interaction is *for*:

- **Interaction that EXPLAINS the content is welcome in any kind**, because it serves understanding (the whole point of an artifact): a chart's hover/crosshair/tooltip, a slider that tunes a parameter (e.g. `k` in a logistic curve) and redraws the concept live, a **reactive inline value** the reader scrubs to see the consequence (see `references/diagram-types.md` - "Interactive charts" and "Reactive inline values"). Always keep a **Rule-9 static floor** so a no-JS view still shows the concept.
- **Interaction that SIMULATES the product stays `prototype`-only**: a wizard, a stateful form, an app mockup. Feeling the product IS the point there; in a status report or decision aid that same chrome is noise.

So a slider is not banned because it is "chrome" - it is welcome when it drives *understanding of the idea*, and reserved when it is *product simulation*.

## Tabbed code samples

When the same operation is worth showing in multiple representations (Python / TypeScript / cURL, or current-vs-proposed config, or before/after JSON), tabs let the reader pick the view they care about without scrolling past three alternative versions. Follow the W3C ARIA Authoring Practices tabs pattern so the widget is accessible to screen readers and keyboard-only users:

```html
<div role="tablist" aria-label="Auth extraction by language">
  <button role="tab" id="tab-py"   aria-controls="panel-py"   aria-selected="true"  tabindex="0">Python</button>
  <button role="tab" id="tab-ts"   aria-controls="panel-ts"   aria-selected="false" tabindex="-1">TypeScript</button>
  <button role="tab" id="tab-curl" aria-controls="panel-curl" aria-selected="false" tabindex="-1">cURL</button>
</div>
<div id="panel-py"   role="tabpanel" aria-labelledby="tab-py"><pre><code>...</code></pre></div>
<div id="panel-ts"   role="tabpanel" aria-labelledby="tab-ts"   hidden><pre><code>...</code></pre></div>
<div id="panel-curl" role="tabpanel" aria-labelledby="tab-curl" hidden><pre><code>...</code></pre></div>
```

Keyboard behavior per the W3C pattern: only one tab in the tab order at a time (`tabindex="0"` on the active tab; `-1` on the others); `Tab` enters and leaves the tablist; left / right arrows cycle between tabs once inside; `Enter` or `Space` activates the focused tab (manual activation is preferred over automatic so screen-reader users do not get bombarded with panel-content reads as they arrow through).

`examples/understanding-canonical.html` includes a worked example showing the JWT extraction in Python, TypeScript, and cURL, with the full keyboard contract implemented.

Best for: `understanding` artifacts (alternative client implementations), `review` artifacts (before/after of the same function in multiple files), `architecture` artifacts (the same change expressed at API / config / data-flow levels).

## Copy button on code blocks (opt-in)

For `review` / `understanding` artifacts with runnable commands, add a copy-to-clipboard button - but **inject it with JS** so surfaces that run no JavaScript never show a dead control (graceful degradation by construction). It uses `createElement` / `textContent`, so the `js-content-fallback` (`.innerHTML`) check never fires. Requires a secure context (https / localhost); the `navigator.clipboard` guard makes it vanish elsewhere.

```html
<script>
(function () {
  if (!navigator.clipboard) return;
  document.querySelectorAll("pre").forEach(function (pre) {
    var code = pre.textContent;   // capture BEFORE appending the button, or the copy includes the "Copy"/"Copied" label
    var btn = document.createElement("button");
    btn.className = "copy-btn"; btn.type = "button"; btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      navigator.clipboard.writeText(code).then(function () {
        btn.textContent = "Copied";
        setTimeout(function () { btn.textContent = "Copy"; }, 1500);
      });
    });
    pre.style.position = "relative"; pre.appendChild(btn);
  });
})();
</script>
```

CSS: `.copy-btn { position: absolute; top: 8px; right: 8px; font-family: var(--mono); font-size: var(--fs-cap); padding: 2px 8px; border: 1px solid var(--line-strong); border-radius: var(--radius-sm); background: var(--surface); color: var(--muted); cursor: pointer; } @media print { .copy-btn { display: none; } }`

Keep it visually quiet - this must not out-shout the content. Not a scaffold default: it would be the first always-on control in every artifact. (Label discipline: a control says what it does and confirms the result - `Copy` → `Copied`; see SKILL.md, "Words are design material".)

## Design system integration (swatches and component contact sheets)

When the artifact documents a visual system (tokens, components, brand colors, typography scales), render the values as the rendered things they are, not as text descriptions. A design token is a named value; the artifact should show all three parts together - **token name, raw value, and a rendered sample** - so the reader sees what the token *is* at the same time as what it *means*. Render the token name, its value, and a live sample together:

```html
<div class="token-grid">
  <div class="token">
    <div class="sample" style="background:#226fb2;"></div>
    <div class="meta">
      <strong>--blue</strong>
      <code>#226fb2</code>
      <span>Primary action, links, focused PM-summary border</span>
    </div>
  </div>
  <div class="token">
    <div class="sample" style="background:#c5542d;"></div>
    <div class="meta">
      <strong>--orange</strong>
      <code>#c5542d</code>
      <span>Before-state highlight, warning accents</span>
    </div>
  </div>
</div>
```

For components, render a live contact sheet of each variant (button default, hover, disabled, primary, danger) inside a bordered container so the reader sees the shape they're about to ship next to the code that produces it. Keep token usage and component samples together: the swatch shows the value, the component sample shows how the value lands.

`examples/prototype-canonical.html` includes a worked swatch + component contact-sheet demo for a brand-system proposal.

Best for: `prototype` artifacts that propose a visual system, `decision` artifacts where the choice is between two visual treatments, `understanding` artifacts that orient a new hire to the brand. If your workspace ships a brand-locked presentation or deck skill, use that for formal decks; the human-html design-system pattern is the right fit for ad-hoc design documentation that does not need the full deck format.

Before adopting or overriding tokens, honor what's already there - the user's words, then the workspace's existing design system, then scaffold defaults; see SKILL.md, "Honor what's already there", for the precedence order and the brand-override `:root` recipe.

## Arrow-key deck navigation

For long artifacts with many `<h2>` sections (architecture reviews with 8+ candidates, plans with 10+ stages, status reports with many workstreams), a small script that maps left / right arrow keys to anchor jumps gives the reader a slideshow-style walkthrough without leaving the page. The implementation needs accessibility guards so it never steals keystrokes from text inputs, tab widgets, or other interactive elements:

```html
<aside class="kbd-hint" aria-label="Keyboard hint">
  Use <kbd>&larr;</kbd> / <kbd>&rarr;</kbd> to jump between sections.
</aside>
<script>
  (() => {
    const sections = Array.from(document.querySelectorAll("section[id]"));
    if (sections.length < 4) return;
    // Derive the current section from scroll position AT PRESS TIME, so free-scrolling and
    // then pressing an arrow advances from where the reader actually is (not a stale index).
    const currentIndex = () => {
      let best = 0, bestDist = Infinity;
      sections.forEach((s, i) => {
        const d = Math.abs(s.getBoundingClientRect().top);
        if (d < bestDist) { bestDist = d; best = i; }
      });
      return best;
    };
    const isTypingTarget = (el) => {
      if (!el) return false;
      const tag = el.tagName;
      return (
        tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || tag === "BUTTON" ||
        el.isContentEditable === true ||
        el.getAttribute("role") === "tab" ||
        el.getAttribute("role") === "spinbutton" ||   // a reactive inline value (diagram-types.md) owns Arrow keys - don't also jump sections
        (el.closest && el.closest("svg")) !== null   // don't hijack arrows while a chart's focusable mark / a stepper or legend button has focus
      );
    };
    document.addEventListener("keydown", (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      if (isTypingTarget(e.target)) return;
      const cur = currentIndex();
      let next = cur;
      if (e.key === "ArrowRight" && cur < sections.length - 1) next = cur + 1;
      else if (e.key === "ArrowLeft" && cur > 0) next = cur - 1;
      else return;
      e.preventDefault();
      sections[next].scrollIntoView({ behavior: "smooth", block: "start" });
    });
  })();
</script>
```

Accessibility guards: the script returns early if the reader is typing in a form field or interacting with a tab widget (preventing it from hijacking left/right arrows inside `<input>` / tablist navigation); it ignores modified keys so browser shortcuts like Alt+Left (back) still work; the visible `<aside class="kbd-hint">` tells the reader the keys exist without forcing discovery.

`examples/architecture-canonical.html` includes a worked example. The script self-disables for short artifacts (fewer than 4 sections) so it never gets in the way for the common case.

Best for: artifacts long enough that scrolling becomes the reader's main UX (review walkthroughs, multi-candidate architecture deep dives, status reports with many workstreams). Skip for short artifacts (3 sections or fewer) - the nav is enough.

## Rail scroll-spy (opt-in, `.railed` artifacts only, 4+ sections)

An `IntersectionObserver` toggles `aria-current` on the rail links; the artifact gains no JS by default. Create the observer **once**, then observe each section:

```html
<script>
(function () {
  var links = document.querySelectorAll(".railed nav.toc a[href^='#']");
  if (!links.length || !("IntersectionObserver" in window)) return;
  var map = new Map();
  links.forEach(function (a) {
    var s = document.querySelector(a.getAttribute("href"));
    if (s) map.set(s, a);
  });
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      links.forEach(function (a) { a.removeAttribute("aria-current"); });
      map.get(e.target).setAttribute("aria-current", "true");
    });
  }, { rootMargin: "-20% 0px -70% 0px" });
  map.forEach(function (_, s) { io.observe(s); });
})();
</script>
```

CSS: `nav.toc a[aria-current] { font-weight: 700; color: var(--accent-2); }`

## Skip link (recommended when 8+ links precede content)

For artifacts where the ribbon + read-map + TOC put 8+ links before content, make the first child of `<body>`:

```html
<a class="skip" href="#first-section-id">Skip to content</a>
```

CSS: `.skip { position: absolute; left: -999px; } .skip:focus { position: fixed; top: 8px; left: 8px; z-index: 10000; background: var(--surface); padding: 8px 12px; border: 2px solid var(--accent); border-radius: var(--radius-sm); }`

Degrades to an invisible link; pure HTML/CSS. Kept out of the scaffold shell for now - body-markup changes to `render_artifact` are deliberately rare.

## Single-file is the default; cross-links are the exception

The source argues for "single-file architecture: one HTML file, zero external dependencies, autonomous forever." This skill keeps that as the **default posture**: most artifacts you ship are one self-contained HTML file that opens in any browser, prints to PDF cleanly, and survives being emailed around as an attachment. We bake that posture in by preferring `<abbr title="...">term</abbr>` inline tooltips over `<a href="GLOSSARY.md#term">` cross-links whenever a definition fits in a tooltip. The hover tooltip preserves single-file independence; the cross-link does not.

Three places where we accept controlled cross-links because the trade-off pays off:

- **GLOSSARY.md cross-link**, reserved for terms whose full definition is too long for an `<abbr title>` tooltip (3+ sentences, code snippets, links to internal docs) or where the reader benefits from landing on the canonical entry. For shorter glosses, inline `<abbr title>` wins.
- **Mermaid CDN script**, because shipping mermaid inline would 200kb-bloat every artifact, and the CDN dependency is bounded, well-known, and cached across artifacts. The scaffold's loader is **self-gating**: it fetches Mermaid from the CDN only if the page actually contains a `<div class="mermaid">`, so a diagram-free artifact makes **zero** network calls and renders fully offline - you pay the CDN request only for artifacts that have a diagram. Self-inlined SVG is the alternative when the diagram is one-off enough not to warrant the CDN. For the *shipped* state, prefer rendering the diagram to inline SVG (source kept in an adjacent `<details><pre>`); the CDN is fine while iterating, but Quick Look / email / offline archives run no JS. See `references/diagram-types.md`, "When to use mermaid".
- **Tailwind CDN** in canonical examples that use it (`architecture-canonical.html`), because the Tailwind utility classes carry the visual grammar in those examples; for new artifacts the lean built-in CSS palette is preferred.

When you author an artifact that genuinely needs 100% standalone delivery (a stakeholder deck mailed as a single attachment, a security-sensitive artifact that cannot reach external assets, a reference doc that needs to survive offline archival), drop the GLOSSARY cross-links in favor of inline `<abbr title>` tooltips and inline-vendor any rendering library you depend on. The default scaffolds make the right trade-off for the common case (artifact stays in the workspace, glossary edits propagate, mermaid renders); standalone artifacts make the trade-off for the extreme case.

The skill's posture in one line: **one self-contained HTML file per artifact by default; deviations are explicit and motivated, not accidental.**

## Hosting & sharing interactive artifacts (serve a URL, don't attach the file)

**An interactive artifact (one with JavaScript: filters, sliders, sortable tables, charts) must be SERVED over a URL - never shared as a file attachment.** Chat and preview surfaces render HTML+CSS but run **no JavaScript**: Slack / Teams / email attachments don't render it, file-manager and in-app previews don't, and **iOS Quick Look disables JS entirely**. Worse, iOS Safari can't reliably run the JS of a *local* `file://` HTML at all (security sandbox) - so "just open the .html on your phone" fails even outside Quick Look. The artifact isn't broken; the *delivery* is. (Verified the hard way: an interactive artifact passed 28/28 Playwright interaction checks in WebKit + Chromium, yet showed blank as a file on a phone - purely because no JS ran. See Rule 9.)

The fix is to host it and share the **link**:

- **Quickest:** GitHub Pages (push the file as `index.html`, enable Pages → `https://<user>.github.io/<repo>/`). Free, public, works on every device.
- **Self-hosted (homelab / internal AWS), so colleagues open a URL behind your own infra:** a static web server (**Caddy** - auto-HTTPS + one-line `basic_auth`, the easiest homelab pick - or **Nginx**) for the simplest case, or a self-hosted PaaS (**Coolify**, **CapRover**, **Dokku**) for git-push deploys. At work/AWS, run the same Caddy/Nginx container on **ECS Fargate behind an ALB** and do auth **at the ALB** (OIDC/Cognito → corporate SSO), or go AWS-native with **private S3 + CloudFront** (Cognito + Lambda@Edge for SSO).
- **Crucial distinction:** use a static web *server*, **not a file-sharing app.** File-share/paste tools (Filebrowser, Pingvin Share, MicroBin, SFTPGo) serve uploads as `Content-Disposition: attachment` (and/or a sandboxed CSP) for security, so a shared `.html` **downloads or renders inert** - the same failure as Slack. Pick a tool whose job is serving web pages with `Content-Type: text/html` inline.
- **Always pair with Rule 9 progressive enhancement** so that *if* someone still opens the file in a no-JS preview, they see a static fallback + a "open in a browser" `<noscript>` banner instead of a blank screen.

When you hand a human an interactive artifact, hand them a **URL**, not a `.html`.

## Sharing & hosting

A menu, in priority order. The skill never publishes anything on its own: nothing leaves the machine unless the human runs the publish script.

1. **Keep it local (the default).** Artifacts are single self-contained HTML files; nothing uploads, there is no setup. Open the file in a browser, print it to PDF, or walk it in a screen share.
2. **GitHub Pages (the OSS-native way).** Commit artifacts to a repo, enable Pages, share the URL. Artifacts are already static HTML, so there is no build step.
3. **Optional S3 via `../scripts/publish-s3.sh`.** No defaults ship; the env contract is:
   - `HUMAN_HTML_S3_BUCKET` (required): the target bucket. The script never creates the bucket and never uploads without an authenticated AWS session.
   - `HUMAN_HTML_S3_REGION`: bucket region.
   - `HUMAN_HTML_S3_PREFIX`: optional key prefix, e.g. `reviews/`.
   - `HUMAN_HTML_S3_EXPIRES`: presigned-URL lifetime in seconds.
   Objects upload with `Content-Type: text/html` so the browser renders them inline. Public buckets get the clean direct URL; private buckets get a **presigned URL** for private sharing (caveat: a presigned URL made from a temporary SSO/STS session is valid only until that session token expires, not the requested lifetime; a durable public link needs static-website hosting or CloudFront).
4. **Any static host or plain file share.** Anything that serves the file inline as `text/html` works; see the static-server-vs-file-share distinction in the previous section.

Whatever the host, still pair with Rule 9 progressive enhancement so a no-JS preview degrades gracefully.

## Sortable tables (opt-in)

Ship the full static `<table>` pre-rendered in the author's deliberate default order; a small script upgrades `<th data-sortable>` headers to buttons with `aria-sort` cycling (none → ascending → descending) and a comparator that tries `Number(cell)` before `localeCompare`. Headers only become buttons when JS runs, so no-JS readers see a normal, correctly-ordered table. Worth it above ~10 rows in research / status / incident action tables; below that, sort the rows yourself and ship them static. Any artifact relying on this interactivity must be **served over a URL**, not opened as a file preview.

---

## Metadata ribbon

A visible top-of-artifact strip showing the load-bearing metadata (author / owner / status / date / read-time / tags) lets a skimmer immediately know who-owns and how-fresh without reading further. Mark with `data-meta-ribbon="true"` so the validator can detect it; the validator WARNs if it is missing (does not block).

```html
<div class="meta-ribbon" data-meta-ribbon="true" aria-label="Artifact metadata">
  <span><strong>Kind</strong> architecture</span>
  <span><strong>Created</strong> 2026-05-25</span>
  <span><strong>Owner</strong> Jordan Ellis</span>
  <span><strong>Status</strong> Draft</span>
  <span><strong>Read time</strong> ~6 min</span>
  <span><strong>Source</strong> /improve-codebase-architecture</span>
</div>
```

The `<meta name="artifact-read-time" content="6 min">` HTML metadata field is the machine-readable companion; surface the same value in the ribbon so the reader sees it without inspecting the DOM.

For `incident` artifacts, the ribbon follows the postmortem shape from `examples/incident-canonical.html`: severity pill (`SEV-1`..`SEV-4`), incident date, resolved time, owner, status, and read time. Other kinds keep the generic created / source ribbon.

## Reading guide

A compact strip offering a **Quick read** (the summary + the recommendation/outcome) versus a **Full read** (all sections), so a reader can pick depth without guessing. Keep it depth-based, not role-based - do not label sections by job title (PM / engineer / exec).

```html
<aside class="read-map" aria-label="Reading map">
  <div><strong>Quick read:</strong> <a href="#pm-summary">Plain terms</a> &middot; <a href="#recommendation">Recommendation</a></div>
  <div><strong>Full read:</strong> All sections</div>
</aside>
```

Best for `architecture`, `decision`, `review`, `plan`, `incident` artifacts long enough that a reader needs a starting point. Rule 6 WARNs when those kinds have more than 3 `<h2>` sections and no reading-guide block.

## Provenance footer

Every artifact is AI-generated to some degree. A provenance footer captures the prompt, model, date, and human reviewer so the artifact is auditable six months later. Mark with `data-provenance="true"` and embed a `<script type="application/ld+json" id="provenance">`; the validator WARNs if either the footer or the documented JSON-LD fields are missing.

```html
<footer class="provenance" data-provenance="true">
  <p>Generated by <code>claude-opus-4-7</code> on 2026-05-25 &middot; reviewed by <code>Jordan Ellis</code> &middot; source: <code>/improve-codebase-architecture</code>.</p>
  <script type="application/ld+json" id="provenance">
    {
      "@context": "https://schema.org/",
      "@type": "CreativeWork",
      "@id": "urn:human-html:2026-05-25:architecture:improve-codebase-architecture",
      "additionalType": "ai-generated-artifact",
      "artifactKind": "architecture",
      "dateCreated": "2026-05-25",
      "creator": { "@type": "SoftwareApplication", "name": "claude-opus-4-7" },
      "promptHash": "<sha256 of prompt; or replace with full prompt if non-sensitive>",
      "reviewer": "Jordan Ellis",
      "source": "/improve-codebase-architecture"
    }
  </script>
</footer>
```

Required fields per the AI-BOM / model-card synthesis: `@id` or `id`, `creator` (model + version), `promptHash` or `prompt`, `dateCreated`, `reviewer`. Prompts containing PII should be hashed and archived externally rather than embedded.

## BLUF compact opener mode (alternative to the 3-bullet PM-summary)

The 3-bullet PM-summary (Rule 1) is the default. For time-critical artifacts where 3 bullets is too much (an incident artifact emailed to a CTO; a yes/no decision needing a 30-second read), BLUF (Bottom Line Up Front) is the alternative. Same `data-audience="pm"` marker, different body shape: one short sentence stating the decision or ask, then a one-sentence rationale.

```html
<section data-audience="pm" class="pm-summary pm-bluf">
  <p><strong>Approve the migration to district-level geocoding for the May release.</strong> Today's city-level geocoder silently fails for 40% of delivery-address lookups; the migration removes the failure mode and unblocks the mobile launch.</p>
</section>
```

The validator only checks for the `data-audience="pm"` marker, so either form satisfies the contract. Both work; pick the one that fits the reader's time budget.

## Appendix lane

For artifacts where the main argument is short but the supporting evidence is voluminous (long traces, full failing logs, raw data tables), an "Appendix" section using `<details>` collapsibles keeps the main narrative tight while shipping full evidence.

```html
<section id="appendix" class="section">
  <h2>Appendix</h2>
  <details>
    <summary>Full failing log (47 lines)</summary>
    <pre><code>...</code></pre>
  </details>
  <details>
    <summary>Raw benchmark data (CSV-style)</summary>
    <table>...</table>
  </details>
</section>
```

Best for `incident`, `architecture`, `research` artifacts where evidence depth matters. Skip for short artifacts where everything fits in the main narrative.

Print force-open of collapsed `<details>` is Chromium-only - evidence-critical content must never live *only* behind a collapsible, or it prints blank on other engines.

## Owners and deadlines on action sections

Any section that lists actions (plan / Sequence, incident / Corrective actions, review / Required changes) should make owner and deadline explicit.

```html
<table>
  <thead><tr><th>#</th><th>Action</th><th>Owner</th><th>Due</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>1</td><td>Add timeout to SSE generator</td><td>Priya</td><td>2026-05-28</td><td><span class="action-status status-progress">IN PROGRESS</span></td></tr>
  </tbody>
</table>
```

Not validated as a hard rule; documented as the convention so future scaffolds bake it in.

## Wide tables - the scroll-wrapper is the preferred pattern

Wrap any wide table in a scroll region rather than relying on the mobile `table { display: block }` fallback - `display:block` drops the implicit `role=table` in Chromium/WebKit, so AT users lose row/column navigation on phones, and the plain overflow region is not keyboard-scrollable.

```html
<div class="table-scroll" role="region" aria-label="Workstream status" tabindex="0">
  <table> … </table>
</div>
```

`.table-scroll table` keeps real `display: table` at every width (it out-specifies the 820px `display:block` fallback), so wrapped tables stay semantic because they remain real `<table>` elements; `role="region"` + `aria-label` + `tabindex="0"` do not add table semantics, they only make the scroll container keyboard-reachable and give it an accessible name. The scaffolds already wrap the tables they emit. The card-reflow pattern (per-cell `data-label`) remains the alternative when a table should reflow into stacked cards rather than scroll.

## Read-size hint

Single optional metadata field that tells the reader up front whether this is a 2-minute or 20-minute read. Surface in the metadata ribbon. Helps the reader budget time and helps a scheduler decide if it fits the next gap on a calendar.

```html
<meta name="artifact-read-time" content="6 min">
```

Suggested defaults by kind: `plan` 5 min, `review` 4 min, `architecture` 10 min, `understanding` 5 min, `research` 5 min, `decision` 5 min, `prototype` 6 min, `status` 4 min, `incident` 6 min.

## URL-state utility for interactive widgets

For artifacts with sliders / toggles / form controls (mostly the `prototype` kind), URL-state encoding lets the reader bookmark a specific state and share it via URL.

Tiny no-build implementation (~40 lines, safe against prototype pollution):

```html
<script>
  const MAX_URL = 2000;
  const STATE_VERSION = 1;
  function loadUrlState(allowKeys, defaults) {
    const h = location.hash.slice(1);
    if (!h || h.length > MAX_URL) return Object.assign({}, defaults);
    try {
      const parsed = JSON.parse(decodeURIComponent(h));
      if (typeof parsed !== "object" || parsed === null) return Object.assign({}, defaults);
      if (parsed.v !== STATE_VERSION) return Object.assign({}, defaults);
      const out = Object.create(null);
      for (const k of allowKeys) {
        if (Object.prototype.hasOwnProperty.call(parsed, k)) out[k] = parsed[k];
      }
      return Object.assign({}, defaults, out);
    } catch { return Object.assign({}, defaults); }
  }
  function saveUrlState(state) {
    const payload = Object.assign({ v: STATE_VERSION }, state);
    const s = encodeURIComponent(JSON.stringify(payload));
    if (s.length > MAX_URL) return;
    const url = location.pathname + location.search + "#" + s;
    history.replaceState ? history.replaceState(null, "", url) : (location.hash = s);
  }
</script>
```

Safety: allow-list keys (prevents `__proto__` injection); `Object.create(null)` for parsed state; `history.replaceState` to avoid back-button pollution; max 2KB URL. Worked example in `examples/prototype-canonical.html`.

## Status color tokens (WCAG-AA)

Standardize semantic colors across artifacts (info / success / warning / error) with a WCAG AA 4.5:1 contrast minimum. Never rely on color alone (also use icon or text label).

```css
:root {
  --status-info:    #226fb2;  /* blue */
  --status-success: #2d7a55;  /* green */
  --status-warning: #d97706;  /* amber */
  --status-error:   #b91c1c;  /* red */
}
```

Severity badges for `incident` kind use the same palette: SEV-1 = error red, SEV-2 = warning amber, SEV-3 = info blue, SEV-4 = neutral grey. Worked example in `examples/incident-canonical.html`.

`--info` intentionally shares the accent hue: "informational" and "brand emphasis" are the same voice in this system. When a chip must **not** read as brand emphasis (dense status surfaces where INFO would blend into links and nav), use `neutral` instead.

---

## Component classes (built into the scaffold, no extra CSS needed)

The shared scaffold ships an author-applied component library (upgraded 2026-07-07). All classes are opt-in - the default markup emits none of them, so they never affect validation. Severity modifier on every component is one of `crit high warn good info neutral`. All colors come from the layered token system in `_SCAFFOLD_STYLE` (`--accent`, the `--<sev>` / `--<sev>-bg` / `--<sev>-line` triples, `--s-*` spacing scale, `--fs-*` type scale, `--display` serif for numbers). Because every class is token-driven, it adapts to the built-in dark theme automatically.

```html
<!-- KPI tiles: serif number + mono label + optional caption. auto-fit grid. -->
<div class="tiles">
  <div class="tile crit"><span class="n">98</span><span class="k">Hotspots</span><span class="d">across 10 services</span></div>
  <div class="tile good"><span class="n">3</span><span class="k">Quick wins</span></div>
</div>

<!-- Keycard: one hero number/verdict + prose. -->
<div class="keycard crit">
  <div class="big">8<small>services at risk</small></div>
  <p><b>Headline finding</b> in one or two sentences.</p>
</div>

<!-- Severity / status chips (inline). -->
<span class="chip crit">CRITICAL</span> <span class="chip good">RESOLVED</span> <span class="chip neutral">N/A</span>

<!-- Tinted cards (use inside .grid-2 / .grid-3). -->
<div class="grid-3">
  <div class="card tint-info"><strong>Title</strong><p>Body.</p></div>
</div>

<!-- Stripe: left accent bar for inline emphasis in prose. -->
<div class="stripe high"><p><b>Note</b>: emphasised line.</p></div>

<!-- Cross-service chain caption (mono). -->
<p class="chain">service_a &rarr; service_b &rarr; store</p>
```

Layout primitives: `.grid-2` / `.grid-3` (responsive, collapse to 1 column on mobile); `code.m` for muted inline mono. Sticky nav rail is **opt-in** - wrap the `<nav class="toc">` and the body in `<div class="railed">…</div>` (a markup change; re-run `check` after, nav ids must still resolve). Existing `.callout` / `.confidence` / `.compare-before` / `.compare-after` / incident `.sev` / `.metric` / `.timeline` are unchanged in name and now consume the same token system.

More component classes and discipline:

- `.btn` - opt-in styled button, `prototype` kind mostly; never restyles a bare `<button>`, so the canonical ARIA-tabs examples keep their own look.
- `.eyebrow` - one eyebrow, in the header, carrying true metadata (kind · date). A per-section eyebrow is allowed only when it encodes real grouping the heading doesn't already say (workstream, epic, phase); never a restatement of the h2. An eyebrow that repeats its heading is decoration and gets deleted.
- `.spark` / `.bars` / `.progress` / `.delta` - dataviz primitives; recipes and severity modifiers in `references/diagram-types.md`.
- `.deflist` - a `<dl>` of label + wrapping description (risks, key terms, glossary rows, a chip plus a paragraph). Use this, never `.bars`, for label + prose: `.bars` is a progress grid whose `max-content` columns do not wrap a long `<dd>` and overflow the page. Recipe in `references/diagram-types.md`.

**Token retunes:** `--faint` is text-safe AA; the `--warn` / `--high` foreground values are contrast-locked to their `--*-bg` tints - retune the pair together, never one alone.

**Opening treatment:** a `.keycard` opens verdict-bearing kinds (`review` / `decision` / `incident` / `status`) answer-first; explanatory kinds keep the quiet header - see SKILL.md, "Opening treatment".

---

## Worked example + self-explanation (comprehension pattern; best in `understanding` / `research`)

To teach a concept, walking the reader through **one concrete instance** step-by-step (a "worked example") builds a mental model as well as, or better than, stating the rule - the catch from the research is that the reader must actually *process* it, which a **self-explanation prompt** forces. Both are pure HTML; no JS.

- **Worked example:** a titled block numbering the steps of a single real case (inputs → each transformation → result), each step one line with the "why" beside the "what". Not the general algorithm - one instance the reader can trace.
- **Self-explanation prompt:** before revealing a step's reasoning, ask the reader to predict/explain it, then let them check. A `<details>` does this natively (summary = prompt, content = answer) and degrades to plain text with no JS.

```html
<section class="worked-example">
  <h3>Worked example: suggesting tags for one bookmarked note</h3>
  <ol>
    <li>The note mentions {Python, SQL, Docker}; the model links each to its related tags.</li>
    <li>Tally how many of the three predict each related tag.</li>
    <li><details><summary>Predict: is "Kubernetes" suggested? Why / why not?</summary>Kubernetes is predicted by Docker <em>and</em> Python (2 votes) - still under the &ge;3 threshold, so it only appears if you pass <code>skip-vote-floor=true</code> (needed for &lt;3 input tags). "Excel", predicted by none, never appears.</details></li>
  </ol>
</section>
```

Default to one instance; add a second only when it *contrasts* the main misconception or a boundary case (contrasting cases genuinely aid transfer) - not as filler.

## Learner-paced stepper (segmentation - reveal a build-up one step at a time)

Breaking a continuous explanation into **learner-paced segments** improves transfer (the segmentation effect; effect size ~1.36 in Mayer & Moreno). For a build-up the reader must absorb in order (a derivation, a pipeline, an incident timeline), a stepper beats both a wall of text and scrollytelling: the reader controls the pace and never loses the thread (scrollytelling, by contrast, over-structures and fatigues readers when overused, and fights the print / self-contained posture).

**Progressive enhancement:** author all steps visible, so no-JS shows the full content as a numbered list; JS then collapses to one-at-a-time with Prev/Next, an "n / N" counter, and an `aria-live` region. The controls appear only when JS runs.

```html
<div class="stepper">
  <style>
    .stepper .steps li[hidden]{display:none}                                    /* screen: hide non-current steps while JS is stepping */
    @media print{ .stepper .steps li{display:list-item !important} .stepper-nav{display:none} }  /* print: reveal the whole build-up */
    .stepper .vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}  /* visually-hidden live region */
  </style>
  <ol class="steps">
    <li>Parse the document into raw tags.</li>
    <li>Link each tag to the vocabulary.</li>
    <li>Expand with the tag-co-occurrence model (&ge;3 votes).</li>
    <li>Merge, dedupe, rank; return the top N.</li>
  </ol>
  <div class="stepper-nav" hidden>
    <button type="button" data-step-prev>Prev</button>
    <span data-step-count>1 / 4</span>
    <button type="button" data-step-next>Next</button>
  </div>
  <span class="vh" data-step-say aria-live="polite"></span>
  <script>
  (function(){
    var w=document.currentScript.closest('.stepper');                           // per-instance scope
    var items=Array.prototype.slice.call(w.querySelectorAll('.steps > li'));
    if(items.length<2) return;
    var count=w.querySelector('[data-step-count]'), say=w.querySelector('[data-step-say]'),
        prev=w.querySelector('[data-step-prev]'), next=w.querySelector('[data-step-next]'), i=0;
    w.querySelector('.stepper-nav').hidden=false;                               // controls exist only when JS runs
    function render(announce){
      items.forEach(function(li,n){ li.hidden = n!==i; });
      count.textContent=(i+1)+' / '+items.length;
      if(say && announce) say.textContent='Step '+(i+1)+' of '+items.length+': '+items[i].textContent.trim();  // announce only on a user step, not at page load
      prev.disabled = i===0; next.disabled = i===items.length-1;                // disable at the bounds
    }
    prev.addEventListener('click',function(){ if(i>0){ i--; render(true); } });
    next.addEventListener('click',function(){ if(i<items.length-1){ i++; render(true); } });
    render(false);
  })();
  </script>
</div>
```

No-JS view: all steps show as a normal ordered list (`render()` never runs, so nothing is hidden and the `hidden` nav stays hidden). Reserve for a genuine ordered build-up; for reference material a plain list or `<details>` is enough.

---
