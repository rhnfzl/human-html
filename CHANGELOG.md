# Changelog

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
