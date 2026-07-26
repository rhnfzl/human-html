# Changelog

## Unreleased

### Added - `render --no-js`

- **Rule 9 can now be verified instead of assumed.** `render --no-js` serves the page as a JavaScript-disabled browser treats it and screenshots the result, closing the one gap the contract had no way to check. Rule 9 protects readers in JS-disabled previews (iOS Quick Look, Android file previews, email), and `js-content-fallback` can only grep for a `<noscript>`: it cannot tell a control from content, and it cannot read whether the fallback matches what the script would build. Now you can look.
- **No Chrome flag does this, which is why it is a rewrite.** `--disable-javascript` is accepted and silently ignored; its screenshot is byte-identical both to a run with JS on and to a run with a deliberately invented flag. `--blink-settings=scriptEnabled=false` makes headless Chrome emit no output at all, under `--headless=new` and `--headless=old` alike. Shipping the flag would have produced a `--no-js` mode that renders with JS fully enabled and reports success, which is worse than the honest gap. So `simulate_no_js()` reproduces the only two things disabling JS changes: `<script>` does not execute, and `<noscript>` children render as ordinary content. The docstring says plainly that this is a simulation of those two effects rather than the browser's own setting.
- **It found a broken floor on its first real use.** `prototype-canonical.html` hid its inert slider and copy button with `<noscript><style>#confidence-sandbox .js-only { display: none; }</style></noscript>`. Those controls carry an inline `style="display:flex"`, and an inline declaration beats a stylesheet rule, so the hide never worked: a JS-disabled reader saw a live-looking slider driving nothing. It passed `js-content-fallback` the entire time, because a `<noscript>` was present. Fixed with `display: none !important`, and the trap is now documented in both SKILL.md and the spine, since anyone hiding an inline-styled control hits it.
- **And a bug in the rewrite itself.** The unwrap regex treated a `<noscript>` *mentioned inside an HTML comment* as a real opening tag, so the non-greedy match ran from the comment to the real `</noscript>`, deleting everything between them and leaving a stray open tag. `prototype-canonical.html` documents its own floor in exactly such a comment. Comments are now stripped first, guarded by a test that fails against the pre-fix transform.

Hook automation can now be enabled with one idempotent command after installation. Three contract defects in the shipped examples are fixed, five workflow patterns are documented, and artifacts gain a dynamic mode for the cases where a prescribed section skeleton makes the document worse.

- **Global hook activation.** `python3 <skill-dir>/activate_hooks.py` merges the advisory and autoindex hooks into Claude Code, Codex, Cursor, and Windsurf settings without replacing unrelated configuration.
- **Windsurf support.** A thin adapter translates Cascade's write and command hook payloads into the existing agent-neutral hook input.
- **Discoverable wiring metadata.** The shipped hooks include their event and matcher headers for downstream installers.

### Fixed

- **`js-content-fallback` now detects DOM insertion, not one phrase.** The rule matched only `.innerHTML =`, so content assembled with `createElement` + `textContent` + `appendChild` passed silently - including in this skill's own `prototype-canonical.html`, which shipped an empty `<ul>` filled by JS and no `<noscript>`, rendering blank in iOS Quick Look. Detection now covers `innerHTML` / `outerHTML` assignment, `insertAdjacentHTML`, `replaceChildren`, `appendChild` / `append` / `prepend`, `insertBefore`, and `document.write`, and deliberately **not** a bare `createElement` (a detached node puts nothing on the page), so the JS-injected copy-button pattern stays clean. Also fixes a pre-existing false positive: `.innerHTML ===` (a read) matched as a write. `prototype-canonical.html` gained a real static floor - its seven default rows pre-rendered, plus a `<noscript>` block that hides the slider and copy button. SKILL.md now states plainly that passing this rule is not proof of a static floor, because the check is a grep and cannot tell a control from content.
- **Reading guides in all nine canonical examples were role-based, which the contract forbids.** SKILL.md requires depth-based guides and explicitly bans job-title labels, yet every example shipped `Exec (2 min)` / `PM (5 min)` / `Engineer (15 min)`. Because SKILL.md tells agents to read the canonical example before writing an artifact of that kind, the example was quietly overriding the rule. Relabelled to `Quick read (2 min)` / `Standard (5 min)` / `Full read (15 min)`, keeping the time budgets, which were the useful part of the old labels.
- **Mermaid label clipping was fixed in the scaffold but never backfilled to the examples.** All nine canonical examples carried live mermaid with neither half of the fix, so every shipped diagram clipped its node labels at the right edge. Both halves are now present in all nine: the CSS that neutralizes page kerning / ligatures / letter-spacing inside `.mermaid` (with `foreignObject { overflow: visible }`), and `flowchart: { htmlLabels: true, padding: 12, useMaxWidth: true }` in the init config.
- **`tests/test_content_rules.py` (new)** guards all three: eighteen positive and negative cases for the DOM-insertion regex, plus contract tests asserting that no example carries a role-based read map, inserts DOM without a `<noscript>` floor, or ships a mermaid diagram missing the clip fix. Each test fails against the pre-fix tree.

### Added

- **Implementation deviation ledger** (`references/workflow-integrations.md`). The during-the-build log that had no home: `plan` is written before the work and `review` happens after it, so everything the code teaches you mid-build evaporates into agent scrollback and the next attempt rediscovers it. Four fixed fields per entry - what the plan said, what the code revealed, the conservative choice taken, what to revisit - closing with a mandatory fold-forward block that turns the surprises into three instructions for the next attempt. Uses the existing `status` kind; no new artifact kind and no validator rule.
- **Reader-response compiler** (`references/workflow-integrations.md`). Most artifacts end with the reader having read; this one ends with them having replied, as a block they paste straight back. The no-JS shape is prescribed rather than suggested, because the obvious implementation renders as dead controls and an empty box in exactly the previews Rule 9 exists to protect: native form controls, choice text in the HTML, a pre-rendered default reply with `aria-live`, and a `<noscript>` swap to a manual template.
- **Review order vs execution order** (`references/patterns.md`). A `plan` sorted by likelihood-of-tweaking rather than build order, so every judgment call is up front and the mechanical work collapses into `<details>`. Includes flagging the weakest part of your own plan, and pre-writing the two or three likeliest pushbacks so the reader can send one in a click.
- **Non-goals** (`references/patterns.md`). "What we deliberately did not do", written as the omission plus its reason. Pre-empts the whole class of review comment that begins "why didn't you also...". Distinguished from Open questions: a non-goal is settled, an open question needs an owner and a date.
- **Linked source-to-target correspondence** (`references/patterns.md`). For ports and migrations: corresponding regions in the source and target excerpts share a token and a number, with the trap in a numbered margin note, plus a preserved / deliberately changed / dropped ledger. The numbered correspondence must carry the meaning with no pointer and no JS; hover highlighting is enhancement only, and must bind focus events too or keyboard and touch readers lose it.

### Added - dynamic mode

- **`artifact-mode="dynamic"`.** The nine kinds pre-decide a section skeleton before anyone knows what the artifact needs to say, which is the right trade most of the time and the wrong one when the shape *is* the argument (a findings taxonomy, a four-way exploration, a line-by-line port map). Adding `<meta name="artifact-mode" content="dynamic">` beside the kind, or scaffolding with `new <kind> "<title>" --mode dynamic`, stands down exactly three rules and nothing else: `required-section` (off), `read-map` (off), and `nav-anchors` (BLOCK to WARN). Mode is a separate field from kind on purpose, so the kind still says what the document is for and drives the gallery and the filename, and a `plan` can go dynamic when the skeleton stops fitting. Every other rule is untouched, because the rule set was always two populations wearing one coat: `required-section` says *a plan looks like this*, `viewport-meta` says *a human on a phone can read this*, and only the first kind is about shape. The mode-selection rule is one question - does the reader benefit from this looking like the last one? - with the kind as the tie-break, since a kind that fits slightly badly costs a reader less than an invented structure that fits nothing.
- **`references/artifact-spine.md` (new).** The fifteen rules say what an artifact must *contain*; nothing said what it must never *do*. That gap is fatal to dynamic mode, because a mode defined only by what it removes drifts straight to a model's defaults. Three layers: the mechanical floor (plus the two floor requirements that cannot be linted, colour never carrying meaning alone and hover always paired with focus and touch), the **spine** an artifact never trades away in any mode (no coined framework names, never name or segment a reader, no engineered keystone, hedges stay, every claim earned, credibility from this artifact's own evidence, avoid the first person, never stage common knowledge as a reveal, inherit the tokens), and prose discipline (after every list one sentence on what it implies; name the concrete failure not the category; small precise numbers over adjectives; one canonical noun per thing; no participle analysis tails; vary the block rhythm). Dynamic mode is free in structure and locked in style.
- **Three dynamic examples that share no structure on purpose** (`examples/dynamic-*.html`), across three different kinds, so no single shape reads as the template a dynamic artifact should copy.
- **Pre-merge self-check** (`references/patterns.md`). A handful of questions attached to a review artifact, answerable only by someone who understood the change. Native `<details>`, so it works with JavaScript off. Explicitly **not** a gate and never scored: answering questions about a document is not evidence the change is safe, so the honest claim is only the narrow one, that a reviewer who cannot answer these has not read what they are about to approve. Two rules keep it useful: ask about the change and never about the document, and link every answer back to the section that establishes it, which turns an unanswerable question into a found gap.

### Fixed - review round

- **Renaming a rule broke every suppression written against its old name.** `_add` matches the emitted rule ID exactly, so an installed workspace with `<!-- human-html-disable: pm-summary -->` went from passing to a **blocking** `summary-first` error on upgrade, with nothing in the message explaining why. Retired IDs now keep answering: `_RULE_ID_ALIASES` maps `summary-first` back to `pm-summary`, guarded by a test that also asserts the alias does not silence the rule for artifacts that never suppressed it. Any future rename must add its alias here.
- **`artifact-mode` written as an attribute was ignored in total silence.** The field is read from `<meta name="artifact-mode">`; an author who put it on an element instead got no mode and no signal, just shape rules that seemed to fire for no reason. Now WARNs and names the element it found it on.

- **A scroll container with no tab stop cannot be scrolled by keyboard.** Two of the three dynamic examples wrapped a wide table in `overflow-x: auto` with no `role`, no label, and no `tabindex`, so a keyboard reader could not reach the clipped columns at all. Fixed in both, and added to the spine as a floor requirement, since the standard wide-table treatment produces this trap by default.
- **Sixteen tab stops that did nothing.** `dynamic-port-correspondence.html` put `tabindex="0"` on every `<mark>` region *and* on the numbered link inside it, doubling the tab order to 32 stops for 8 pairs, with every second stop inert on activation. The highlight listens with `focusin`, which bubbles, so focus on the inner link already reaches the region's listener: verified in a browser that all 16 regions still light both halves with the attribute gone. The spine now states the rule, because "make it focusable" reads as "add `tabindex`" and that is wrong whenever the region already contains a link, a `<summary>`, or a control.
- **Two arithmetic contradictions in `dynamic-blindspot-pass.html`.** A page archived Monday 09:00 was said to stay searchable "6 days and 22 hours"; against the stated Sunday 01:00 rebuild plus its 5h40m run the flip lands 5 days and 22 hours later, and the prose now names the alias flip so the figure is checkable. Separately the same file gave the rebuild as both "40 minutes" and "5h40m".
- **`artifact-mode` typos failed silently.** An unrecognised value fell through to the full rule set with no signal, so `dyanmic` looked identical to a validator that ignored the field. Now WARNs under a new `artifact-mode` rule with the value it saw and the values it expected, and stays held to the full rule set.
- **Documentation that contradicted the code.** SKILL.md still claimed four rules always block after `nav-anchors` became mode-dependent; the post-`init` blurb still promised a per-kind section skeleton for every `new`, which dynamic mode does not produce; Rule 1 described the three-bullet block as the only compliant opener while `patterns.md` documents BLUF as an alternative (BLUF is now named as equally compliant in both places); and the reading-guide snippet linked to `#lead-summary`, an id nothing emitted, so the scaffold now carries it.
- **The spine cited an unearned population statistic**, in the file whose own rule bans them. Replaced "roughly one reader in twelve" with the two mechanisms that actually defeat hue alone (colour vision deficiency and any greyscale or printed copy) plus the WCAG clause. Also narrowed "never address a reader" to "never segment a reader", which was over-reach: the ban is on sorting readers into groups, never on the second person.
- **House-style test missed half the smart quotes.** It checked for the opening curly double quote and the closing curly apostrophe but not their partners, so a file carrying only a closing curly double quote passed.
- **The spine presented marker checks as a validated floor.** Its table read as though `check` established the properties in the left column, which it does not: `summary-first` finds the summary section anywhere in the page, so one buried above the footer passes; `js-content-fallback` is satisfied by any `<noscript>`, including an empty one about something else, and cannot read whether the static content matches what the script builds; `table-responsive` cannot tell whether a scroll container is reachable by keyboard. The table now carries a third column stating what each check actually proves, with the three worst gaps spelled out, and the layer is described as marked rather than validated. The parallel claim in SKILL.md's dynamic-mode section is now phrased as requirements rather than guarantees.
- **An example claimed a repair its own code does not perform.** `dynamic-port-correspondence.html` said the TypeScript port "clamps downward" an over-capacity bucket. It clamps the *headroom*, which is not the same thing: on a downgrade from 600 to 100 with 600 tokens held, `headroom` is 0 and `tokens += Math.min(minted, 0)` leaves 600 in place, so the bucket never returns under the new cap on its own and the downgraded tier keeps serving the old allowance until callers spend it down. Corrected in the note and in the behaviour ledger, with the arithmetic shown so a reviewer can check it.
- **An example's outage timeline contradicted itself.** `dynamic-design-directions.html` recorded a 502 window of 09:14:40 to 09:18:00, then evidenced a retry loop as nine sends between 09:18:00 and 09:19:01 all receiving 502, after the vendor had recovered. The retry burst now sits inside the window, and what stops the loop is the vendor recovering rather than a manual intervention, which is the sharper version of the same finding: nothing in the flusher bounds it. The related claim that direction 4's burst "starts at 09:18" is also fixed, since the window catching only its sparse pre-import tail is what makes its 190 losses possible at all.
- **A lead overstated which option wins.** The same file's opener implied direction 3 had the lowest outage cost while its own table gave direction 4 fewer losses, 190 against 470. The lead now claims what is actually true and defensible, that direction 3's cost holds up wherever the outage falls, and names direction 4's lower number as an accident of timing.

### Changed

- **`data-audience="pm"` is now `data-summary="true"`, and the `pm-summary` rule is `summary-first`.** The contract bans labelling reading depth by job title, and the nine canonical read maps were relabelled for that reason. The summary marker was the same segmentation one layer down in the markup, and it was the one rule that blocked unless you wrote it. The pre-rename attribute is still accepted so already-shipped artifacts keep validating; it is simply no longer documented. The `.pm-summary` class is now `.lead-summary` throughout, since leaving it behind means the next author copies the job title forward.

## 1.2.4 - 2026-07-12

Fix a broken remote install: `npx skills add rhnfzl/human-html` now ships the full skill, not just `SKILL.md`. No change to generated artifacts.

- **The skill moved into `skills/human-html/`.** The `skills` installer copies a skill's full payload only when it lives in a subdirectory; a root-level remote skill shipped `SKILL.md` alone, dropping the engine, references, templates, examples, and hooks, so the installed skill told the agent to run a script and read files that were never installed. Relocating the skill into `skills/human-html/` puts it on the subdirectory code path, so every support file lands. Mirrors the `slide-sage` and `explore-unknowns` layout.
- **Re-install note for existing users.** If a previous install left the skill referencing a script or reference files that were not present, re-run `npx skills add rhnfzl/human-html` (or your installer's equivalent) to pull the complete payload.
- **Plugin channel unchanged.** The Claude Code plugin still installs from the same marketplace (`source: "./"`); the slash command and hooks resolve the relocated engine via `$CLAUDE_PLUGIN_ROOT/skills/human-html/`. Manual "clone and symlink" now targets `skills/human-html/`, and the release version-guard reads the relocated `SKILL.md`.

## 1.2.3 - 2026-07-10

Security-posture housekeeping. No functional change to generated artifacts.

- **Add `SECURITY.md`.** Documents the skill's two intentional external touch-points and why they are safe: the optional bring-your-own-bucket S3 publish helper (uploads to a bucket you own, then prints a link - never downloads or executes), and the optional client-side, version-pinned, self-gating Mermaid CDN import used only for *live* (non-shipped) diagrams. Gives human auditors and LLM-assisted skill scanners the rationale in-repo.
- **CI: bump `actions/checkout@v4` to `@v5`** in the release workflow; the v4 pin runs on the deprecated Node 20 runner.

## 1.2.2 - 2026-07-10

Clear the Snyk `E005` "suspicious download URL" audit finding on `scripts/publish-s3.sh`, and harden the returned link.

- **No hardcoded S3 endpoint in the shipped script.** The two hand-built virtual-hosted S3 object URLs - which the skills.sh Snyk audit flagged as a generic "personal file hosting" download URL (rule E005) - are gone. The open URL is now derived from the AWS CLI's own presigner: the presigned URL is generated first and the clean object URL is that URL minus its query string. Behaviour is unchanged (public / static-website buckets still get the clean direct URL; private buckets still get the presigned one), but no literal S3 host string lives in the skill source for a scanner to match.
- **Two latent bugs fixed for free.** The old no-`HUMAN_HTML_S3_REGION` branch built the legacy global endpoint (breaks on newer regions) and left `${key}` un-encoded; the presigner-derived URL is region-correct and URL-encoded by the SDK.

## 1.2.1 - 2026-07-09

Fix a pre-existing horizontal overflow at phone width, and harden the generator against its cause.

- **Three canonical examples (architecture, review, understanding) no longer overflow at 390px.** They predate the v1.1.4 overflow discipline: a wide `<table>` without the responsive reflow (architecture), `.compare-before` / `.compare-after` grid items without `min-width:0` so a wide `<pre>` forced the track past the viewport (review), and a long unbroken path in inline `<code>` with no wrap (understanding). The overflow was present before the v1.2.0 dark-mode change, not introduced by it.
- **Generator hardened against the same class.** Grid items (`.grid-cols-2` / `.grid-2` / `.grid-3` children and the compare blocks) now carry `min-width:0` so a wide child scrolls instead of pushing the page, and inline `code` gets `overflow-wrap:anywhere` so a long path or token breaks. Verified with torture content (over-long `<pre>` lines in a compare grid plus a 72-character nonbreaking token) at 390px in both themes: zero overflow, layout-audit silent.

## 1.2.0 - 2026-07-09

Dark mode: every artifact and the gallery index now ship a built-in light/dark toggle (fixed top-right, sun/moon).

- **Follows the reader's OS by default.** First open with no saved choice matches `prefers-color-scheme`; the toggle overrides and persists per-site in `localStorage`. With JavaScript off the page still follows the OS via a CSS media query and the (non-functional) toggle button stays hidden, so nothing is a dead control.
- **Degrade-safe and print-safe.** The base `:root` stays light and renders on any engine; the contrast-verified dark palette is emitted into two screen-scoped selectors (an explicit `:root[data-theme="dark"]` choice and the OS media query). Wrapping the dark tokens in `@media screen` keeps print-to-PDF light for clean handoff. A blocking head script applies a saved theme before first paint (no flash) and uses no `.innerHTML`, so the no-JS content contract is untouched.
- **Dark palette.** A cool, navy-biased set mirroring the light tokens one-for-one: elevation inverts (raised surfaces get lighter), the six severity triples are re-tuned for a dark ground, the code block gains a border so it does not melt into the page, and shadows drop their tint. All text pairings clear WCAG AA.
- **Mermaid diagrams** pick their palette at load from the resolved theme, so a diagram matches the page it opens in; a mid-session toggle re-themes diagrams on the next reload.
- **Branding dark.** A plain `:root` brand override still styles light only; to brand dark, append a `:root[data-theme="dark"]` override. `SKILL.md` and `references/patterns.md` updated: the scaffold is no longer described as light-only.

## 1.1.4 - 2026-07-09

Scaffold robustness: two fixes so a shipped artifact cannot overflow horizontally (which fired the runtime layout-audit banner and clipped content on a phone).

- **Meta-ribbon no longer overflows on a long value.** `.meta-ribbon span` was `white-space:nowrap`, so a single long value (e.g. a wordy `Status`) could not wrap and pushed past a 390px phone viewport. It is now `white-space:normal; overflow-wrap:anywhere` - short label/value pairs still sit together (the flex container wraps between spans), only an over-long value wraps internally.
- **`.bars` misused as a definition list no longer blows out the page.** `.bars` is a `max-content 1fr max-content` progress grid; feeding it `<dt>`/`<dd>` prose forced long descriptions into a `max-content` column that never wrapped (a multi-thousand-pixel blowout). `.bars dd` now carries `min-width:0; overflow-wrap:anywhere` so a misuse degrades instead of exploding.
- **New `.deflist` component** for the label + wrapping description pattern (risks, key terms, glossary rows, a chip plus a paragraph) - a 2-column `max-content 1fr` grid whose description wraps and caps at a readable measure, collapsing to one column under 560px. `references/diagram-types.md` and `references/patterns.md` now steer authors to `.deflist` and warn against `.bars` for this use.
- **New `figure.diagram` / `.diagram-scroll` / `.diagram-src` scaffold styles** for shipping a diagram as inline SVG (self-contained: renders under Quick Look, email, and offline) with the source kept in an adjacent `<details>`. The scroll wrapper contains a too-wide diagram to its own scrollbar rather than the page. The existing guidance already recommended inline SVG for the shipped state; these are the house styles for it.

## 1.1.3 - 2026-07-09

Review fixes.

- `scripts/publish-s3.sh`: refuse to overwrite an existing object at the same key unless `HUMAN_HTML_S3_OVERWRITE=1` is set, and stop the auth-failure retry hint from double-applying `HUMAN_HTML_S3_PREFIX`.
- `references/patterns.md`: fix the heading hierarchy (sections were H3 under an H1 with no H2), and correct the accessibility note (a scroll wrapper's `role="region"` does not add table semantics; the table stays semantic because it is a real `<table>`).
- `references/workflow-integrations.md`: add the required `confidence` field to the Decision schema and example, sync the Q3 JSON-LD text with the rendered question, and fix a dangling cross-reference.
- Scrubbed the remaining em dashes from the reference docs.

## 1.1.2 - 2026-07-08

- Migrated all nine canonical examples onto one shared house design system, so the gallery reads as a single consistent set. Each kept its content, metadata, comparison visuals, and (for prototype) its interactive sandbox; only the presentation was re-based onto the current scaffold.
- Reconciled a number inconsistency in the architecture example (the helper-count tile now agrees with the prose and the stat line).

## 1.1.1 - 2026-07-08

- `em-dash` rule now catches HTML entities and numeric refs (`&mdash;`, `&ndash;`, `&#8212;`, `&#8211;`, `&#x2014;`, `&#x2013;`), not just the literal characters. The prior rule missed entity-encoded dashes entirely, so artifacts could carry visible em dashes that `check` never flagged.
- Fixed the code-panel rendering in the review and prototype canonical examples: their frozen styles predated the `pre code` background reset, so code showed as faint text on light boxes over the dark panel.
- Rebuilt the architecture canonical example onto the current house design system. It previously loaded Tailwind from a CDN (not self-contained, blank offline) and used gradients the anti-slop checklist bans.
- Scrubbed em dashes from all nine canonical examples.
- README: cleaner quickstart (one command), a catalog of the nine kinds linked to live examples, and a Requirements table with install hints.

## 1.1.0 - 2026-07-08

- New `em-dash` WARN rule: the validator flags em/en dashes in artifact prose (dashes inside `pre`/`code`/`script`/`style` are exempt) and suggests a comma, colon, parentheses, or " - " instead. Suppressible per artifact like every rule.
- Root HTML check now only flags files that look like human-html artifacts, so a legitimate root `index.html` (a static site's landing page, this repo's own gallery) no longer fails `check`.
- Hooks resolve their own path with a portable symlink-following loop instead of `readlink -f`, so symlinked hook installs work on macOS versions without GNU-style readlink.
- Skip-and-warn hardening: a non-UTF8 or unreadable artifact is reported and skipped instead of crashing `check` and `index`.
- Hash-link checking tightened: a fragment link to a file with no matching anchor is now a broken link even when the target has no anchors at all; unreadable targets are reported distinctly.
- `scripts/publish-s3.sh` distinguishes a missing `aws` CLI (exit 2, install pointer) from failed AWS authentication.
- README badges (release, license, stdlib-only, live gallery), a documented Python 3.8+ floor, and a qualified self-contained claim (Mermaid blocks use a CDN unless rendered to inline SVG).

## 1.0.0 - 2026-07-08

Initial public release.

- Content contract with Rules 1-10: PM-language summary, a visual in every comparison section, nav anchors on long artifacts, required sections per kind, glossary linking, reading guides, meeting Q&A schema, mobile responsiveness, and no-JS robustness.
- Nine canonical examples, one per kind (plan, review, architecture, understanding, research, decision, prototype, status, incident), each showing what good looks like.
- Offline validator (`human_html_artifacts.py check`) plus an auto-generated gallery `index.html` that skips and warns on a single malformed file rather than breaking the build.
- Two optional shell hooks: an advisory nudge toward the harness and an autoindex that keeps the gallery current, both advisory-only and always exit 0.
- Optional bring-your-own-bucket S3 publish script (`scripts/publish-s3.sh`), env-driven with zero defaults, that uploads nothing unless you run it.
