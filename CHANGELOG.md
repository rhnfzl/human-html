# Changelog

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
