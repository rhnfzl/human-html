# Changelog

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
