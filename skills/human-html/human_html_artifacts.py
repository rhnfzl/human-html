#!/usr/bin/env python3
"""Create, index, and validate human-facing HTML review artifacts.

Workspace-agnostic: resolves the workspace root via $HUMAN_HTML_ROOT,
then by walking up from CWD looking for docs/human-html/, then falling
back to CWD (used by `init` to seed a new workspace).

Part of the human-html skill; bundled alongside SKILL.md and the hooks
wherever the agent installed the skill.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


KINDS = (
    "plan",
    "review",
    "architecture",
    "understanding",
    "research",
    "decision",
    "prototype",
    "status",
    "incident",
)

NAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-"
    r"(?P<kind>plan|review|architecture|understanding|research|decision|prototype|status|incident)-"
    r"(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.html$"
)

# Per-kind required-section rules. Each entry maps a required heading (matched
# case-insensitively against h2/h3 text) to a severity. "error" blocks the
# validator; "warn" prints to stderr without affecting exit code. Vale-style
# severity model: deeper rule sets can be added without forcing existing
# artifacts to migrate. See SKILL.md for the staged-rollout rationale.
REQUIRED_SECTIONS: dict[str, list[tuple[str, str]]] = {
    "incident": [
        (r"\btimeline\b", "error"),
        (r"\b(corrective\s+actions?|actions?|next\s+steps?)\b", "error"),
        (r"\b(impact|customer\s+impact|business\s+impact)\b", "warn"),
        (r"\b(root\s+cause|contributing\s+factors?)\b", "warn"),
    ],
    "plan": [(r"\brollback\b", "warn")],
    "decision": [(r"\bconsequences?\b", "warn")],
    "architecture": [(r"\bopen\s+questions?\b", "warn")],
}
TITLE_RE = re.compile(r"<title>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)

# Artifacts whose artifact-created is on or after this date are held to the content-shape
# rules below (PM-summary block, diagram-in-comparison, nav-when-many-sections). Earlier
# artifacts are grandfathered so historical content stays readable without forced migration.
RULES_EFFECTIVE_DATE = "2026-05-25"

# Headings that mean "this section compares two states" and therefore require a visual.
# The regex requires an explicit comparison pair (slash, hyphen, vs, versus, and) so it
# does not trip on standalone words like "Target audience" or "Current blockers".
COMPARISON_HEADING_RE = re.compile(
    r"\b("
    r"before\s*[/\-,]\s*after|"
    r"before\s+and\s+after|"
    # order-symmetric: match either direction of the common comparison pairs
    r"(?:current|baseline|old|previously)\s*(?:vs\.?|versus|/)\s*(?:proposed|target|new|now)|"
    r"(?:proposed|target|new|now)\s*(?:vs\.?|versus|/)\s*(?:current|baseline|old|previously)|"
    r"now\s*(?:vs\.?|versus)\s*then|"
    r"then\s*(?:vs\.?|versus)\s*now"
    r")\b",
    re.IGNORECASE,
)

# Anything matching one of these counts as a "visual" inside a comparison section.
# Class-name matchers handle both single- and double-quoted attribute values.
_VISUAL_PATTERNS = [
    re.compile(r"""<div[^>]*class=['"][^'"]*\bmermaid\b[^'"]*['"]""", re.IGNORECASE),
    re.compile(r"<svg\b", re.IGNORECASE),
    re.compile(r"<table\b", re.IGNORECASE),
    re.compile(r"<img\b", re.IGNORECASE),
    re.compile(r"\bgrid-cols-2\b", re.IGNORECASE),
    re.compile(r"\bmd:grid-cols-2\b", re.IGNORECASE),
    # the scaffold's OWN side-by-side layout primitive (documented in patterns.md as ".grid-2")
    re.compile(r"\bgrid-2\b", re.IGNORECASE),
    # ASCII / CSS-box diagrams (C4-L1, low-fi wireframes) the illustration menu recommends,
    # plus an explicit escape hatch for any author-built visual the patterns above miss.
    re.compile(r"""<pre[^>]*class=['"][^'"]*\bdiagram\b[^'"]*['"]""", re.IGNORECASE),
    re.compile(r"""\bdata-visual=['"]true['"]""", re.IGNORECASE),
]

# Walks h2 and h3 headings, both feed comparison-section detection.
_HEADING_RE = re.compile(r"<h([23])\b[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
# Strip HTML comments before scanning a section for a visual, so a commented-out
# `<!-- <svg>... -->` can't falsely satisfy the comparison-visual rule.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Mobile-responsiveness: an artifact a teammate opens on their phone must not
# render at desktop width or clip a wide table. Two mechanical checks back the
# "works on mobile" requirement in SKILL.md (the design gotchas stay documented).
_VIEWPORT_NAME_RE = re.compile(r"""<meta[^>]+name=['"]viewport['"]""", re.IGNORECASE)
_DEVICE_WIDTH_RE = re.compile(r"width\s*=\s*device-width", re.IGNORECASE)
_TABLE_RE = re.compile(r"<table[\s>]", re.IGNORECASE)
# Evidence that a table has SOME responsive treatment: a mobile breakpoint, an
# overflow-x scroll wrapper (raw CSS or Tailwind), or an explicit opt-in marker.
_RESPONSIVE_TABLE_RE = re.compile(
    r"@media[^{]*max-width"
    r"|overflow-x\s*:\s*(?:auto|scroll)"
    r"|overflow-x-(?:auto|scroll)"
    r"|data-responsive-table",
    re.IGNORECASE,
)
# Progressive enhancement: JS-disabled previews (iOS Quick Look, Android file /
# in-app previews, email) render HTML+CSS but run NO JavaScript. An artifact that
# builds its core content with .innerHTML and offers no <noscript> fallback shows
# up blank in those contexts. If it writes content with JS, it must degrade.
_JS_DOM_WRITE_RE = re.compile(r"\.innerHTML\s*=", re.IGNORECASE)
_NOSCRIPT_RE = re.compile(r"<noscript[\s>]", re.IGNORECASE)


def resolve_root() -> Path:
    """Resolve the workspace root via env var, CWD walk-up, or CWD fallback.

    Used by read-side commands (check / index) that must LOCATE an existing
    docs/human-html/ lane, so walking up from a subdirectory is correct here.
    """
    env = os.environ.get("HUMAN_HTML_ROOT")
    if env:
        return Path(env).resolve()
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "docs" / "human-html").is_dir():
            return candidate
    return cwd


def resolve_create_root() -> Path:
    """Resolve the root for CREATE commands (new / init).

    Deliberately does NOT walk up: an artifact should land in docs/human-html/
    of the CURRENT working directory, co-located with the project you are in,
    not in some ancestor's (or a sibling workspace's) lane. Set HUMAN_HTML_ROOT
    to override when you intentionally want the artifact in a different project.
    """
    env = os.environ.get("HUMAN_HTML_ROOT")
    if env:
        return Path(env).resolve()
    cwd = Path.cwd().resolve()
    for parent in cwd.parents:
        if (parent / "docs" / "human-html").is_dir():
            print(
                f"WARN: an existing docs/human-html/ lane is at {parent} (an ancestor of the "
                f"current directory); creating a SEPARATE lane at {cwd} forks the gallery. "
                f"Set HUMAN_HTML_ROOT={parent} to reuse the existing one.",
                file=sys.stderr,
            )
            break
    return cwd


def artifact_dir(root: Path) -> Path:
    return root / "docs" / "human-html"


def index_file(root: Path) -> Path:
    return artifact_dir(root) / "index.html"


@dataclass(frozen=True)
class Artifact:
    path: Path
    href: str
    date: str
    kind: str
    slug: str
    title: str
    source: str
    summary: str = ""
    keywords: tuple[str, ...] = ()


_SUPPRESS_COMMENT_RE = re.compile(r"\s*human-html-disable\s*:\s*([\w:.\-,\s]+)\s*", re.IGNORECASE)


_PUNCT_SPACE_RE = re.compile(r"\s+([,.;:!?])")


def _join_captured(chunks: list[str]) -> str:
    """Join captured text-node chunks with spaces (so adjacent inline elements like
    a number badge + text don't fuse into '1Pick'), collapse whitespace, then drop
    the spurious space a separate-chunk punctuation mark would leave ('Foo : Bar')."""
    text = " ".join(" ".join(chunks).split())
    return _PUNCT_SPACE_RE.sub(r"\1", text).strip()


class ArtifactHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.meta: dict[str, str] = {}
        self.has_body_marker = False
        self.has_pm_summary = False
        self.has_meta_ribbon = False
        self.has_provenance = False
        self.has_read_map = False
        self.has_meeting_qa = False
        self.nav_count = 0
        self.h2_count = 0
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.nav_hrefs: list[str] = []
        self.asset_refs: list[tuple[str, str]] = []
        self.suppressed_rules: set[str] = set()
        self._capture_heading: str | None = None
        self._heading_buffer: list[str] = []
        self._nav_depth = 0
        self._capture_provenance_script = False
        self._capture_meeting_qa_script = False
        self._script_buffer: list[str] = []
        self.provenance_json_scripts: list[str] = []
        self.meeting_qa_json_scripts: list[str] = []
        self.headings: list[str] = []
        # Index auto-extraction (summary/keywords fallbacks).
        self.description = ""
        self.keywords_meta = ""
        self.h2_headings: list[str] = []
        self.pm_lead = ""
        self._capture_pm_lead = False
        self._pm_lead_done = False
        self._capture_lead_tag: str | None = None
        self._lead_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        tag_name = tag.lower()
        if attr_map.get("id"):
            self.ids.add(html.unescape(attr_map["id"]))
        if tag_name == "meta":
            name = attr_map.get("name", "").lower()
            if name.startswith("artifact-"):
                self.meta[name] = html.unescape(attr_map.get("content", ""))
            elif name == "description":
                self.description = html.unescape(attr_map.get("content", ""))
            elif name == "keywords":
                self.keywords_meta = html.unescape(attr_map.get("content", ""))
        if tag_name == "body" and attr_map.get("data-human-html-artifact") == "true":
            self.has_body_marker = True
        if tag_name == "section" and attr_map.get("data-audience", "").lower() == "pm":
            self.has_pm_summary = True
            if not self._pm_lead_done:
                self._capture_pm_lead = True
        # Capture the first li/p text inside the PM-summary block as a fallback summary.
        if (
            tag_name in ("li", "p")
            and self._capture_pm_lead
            and not self._pm_lead_done
            and self._capture_lead_tag is None
        ):
            self._capture_lead_tag = tag_name
            self._lead_buffer = []
        if attr_map.get("data-meta-ribbon", "").lower() == "true":
            self.has_meta_ribbon = True
        if attr_map.get("data-provenance", "").lower() == "true":
            self.has_provenance = True
        if attr_map.get("data-meeting-qa", "").lower() == "true":
            self.has_meeting_qa = True
        # Read-map detection: class contains "read-map" or aria-label is "Reading map" / "Read map".
        css_classes = attr_map.get("class", "").lower().split()
        aria_label = attr_map.get("aria-label", "").strip().lower()
        if "read-map" in css_classes or aria_label in {"reading map", "read map", "audience read map"}:
            self.has_read_map = True
        if (
            tag_name == "script"
            and attr_map.get("type", "").lower() == "application/ld+json"
        ):
            script_id = attr_map.get("id", "").lower()
            if "provenance" in script_id:
                self.has_provenance = True
                self._capture_provenance_script = True
                self._script_buffer = []
            elif "meeting-qa" in script_id or "meetingqa" in script_id:
                self.has_meeting_qa = True
                self._capture_meeting_qa_script = True
                self._script_buffer = []
        if tag_name == "nav":
            self.nav_count += 1
            self._nav_depth += 1
        if tag_name in ("h2", "h3"):
            if tag_name == "h2":
                self.h2_count += 1
            self._capture_heading = tag_name
            self._heading_buffer = []
        if tag_name == "a" and attr_map.get("href"):
            href = html.unescape(attr_map["href"])
            self.hrefs.append(href)
            if self._nav_depth:
                self.nav_hrefs.append(href)
        if tag_name == "script" and attr_map.get("src"):
            self.asset_refs.append(("script", html.unescape(attr_map["src"])))
        if tag_name == "img" and attr_map.get("src"):
            self.asset_refs.append(("img", html.unescape(attr_map["src"])))
        if (
            tag_name == "link"
            and attr_map.get("href")
            and "stylesheet" in attr_map.get("rel", "").lower().split()
        ):
            self.asset_refs.append(("stylesheet", html.unescape(attr_map["href"])))

    def handle_data(self, data: str) -> None:
        if self._capture_provenance_script or self._capture_meeting_qa_script:
            self._script_buffer.append(data)
        if self._capture_heading:
            self._heading_buffer.append(data)
        if self._capture_lead_tag is not None:
            self._lead_buffer.append(data)

    def handle_comment(self, data: str) -> None:
        match = _SUPPRESS_COMMENT_RE.match(data)
        if not match:
            return
        for raw in match.group(1).split(","):
            rule = raw.strip().lower()
            if rule:
                self.suppressed_rules.add(rule)

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name == "script" and self._capture_provenance_script:
            self.provenance_json_scripts.append("".join(self._script_buffer).strip())
            self._capture_provenance_script = False
            self._script_buffer = []
        elif tag_name == "script" and self._capture_meeting_qa_script:
            self.meeting_qa_json_scripts.append("".join(self._script_buffer).strip())
            self._capture_meeting_qa_script = False
            self._script_buffer = []
        if tag_name == "nav" and self._nav_depth:
            self._nav_depth -= 1
        if self._capture_heading and tag_name == self._capture_heading:
            heading_text = _join_captured(self._heading_buffer)
            if heading_text:
                self.headings.append(heading_text)
                if self._capture_heading == "h2":
                    self.h2_headings.append(heading_text)
            self._capture_heading = None
            self._heading_buffer = []
        if self._capture_lead_tag is not None and tag_name == self._capture_lead_tag:
            lead_text = _join_captured(self._lead_buffer)
            self._capture_lead_tag = None
            self._lead_buffer = []
            if lead_text:
                self.pm_lead = lead_text
                self._pm_lead_done = True
                self._capture_pm_lead = False
        # PM block closed without capturing a lead: stop, so a later paragraph
        # outside the PM summary is never grabbed.
        if tag_name == "section" and self._capture_pm_lead and not self._pm_lead_done:
            self._capture_pm_lead = False
            self._pm_lead_done = True


def slugify(value: str) -> str:
    slug = value.lower().replace("&", " and ")
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "artifact"


def parse_title(content: str, fallback: str) -> str:
    match = TITLE_RE.search(content)
    if not match:
        return fallback
    title = re.sub(r"\s+", " ", match.group("title")).strip()
    return html.unescape(title) or fallback


def markdown_anchor(value: str) -> str:
    """Approximate GitHub-style anchors for local Markdown hash validation."""
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = _strip_tags(html.unescape(value)).strip().lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9\s-]+", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def hash_targets_for_path(path: Path, cache: dict[Path, set[str] | None]) -> set[str] | None:
    """Return valid hash targets for an HTML or Markdown file.

    Returns None when the target cannot be read (distinguishes "unverifiable"
    from "readable but has no anchors", which is a broken hash)."""
    resolved = path.resolve()
    if resolved in cache:
        return cache[resolved]

    targets: set[str] = set()
    try:
        content = resolved.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        cache[resolved] = None
        return None

    suffix = resolved.suffix.lower()
    if suffix in {".html", ".htm"}:
        parser = ArtifactHTMLParser()
        parser.feed(content)
        targets = parser.ids
    elif suffix == ".md":
        for line in content.splitlines():
            match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
            if not match:
                continue
            heading = match.group(1).strip()
            anchor = markdown_anchor(heading)
            if anchor:
                targets.add(anchor)
            for separator in (" \u2014 ", " \u2013 ", " - "):
                if separator in heading:
                    short_anchor = markdown_anchor(heading.split(separator, 1)[0])
                    if short_anchor:
                        targets.add(short_anchor)
                    break

    cache[resolved] = targets
    return targets


def iter_html_files(root: Path) -> list[Path]:
    adir = artifact_dir(root)
    if not adir.exists():
        return []
    idx = index_file(root).resolve()
    return sorted(
        p
        for p in adir.rglob("*.html")
        if p.is_file() and p.resolve() != idx
    )


def _validate_local_reference(
    root: Path,
    source_path: Path,
    raw_ref: str,
    label: str,
    errors: list[str],
    source_ids: set[str] | None = None,
    hash_target_cache: dict[Path, set[str] | None] | None = None,
) -> None:
    ref = raw_ref.strip()
    if not ref:
        return
    source_ids = source_ids or set()
    hash_target_cache = hash_target_cache if hash_target_cache is not None else {}
    parsed = urlsplit(ref)
    if parsed.scheme or parsed.netloc:
        return
    rel = source_path.relative_to(root)
    fragment = unquote(parsed.fragment)
    if not parsed.path:
        if fragment and fragment not in source_ids:
            errors.append(f"{rel}: broken {label} hash {ref!r}")
        return
    target_path = Path(unquote(parsed.path))
    if target_path.is_absolute():
        errors.append(f"{rel}: {label} {ref!r} must be relative, not absolute")
        return
    resolved = (source_path.parent / target_path).resolve()
    artifact_root = artifact_dir(root).resolve()
    try:
        resolved.relative_to(artifact_root)
    except ValueError:
        if label != "href":
            errors.append(f"{rel}: {label} {ref!r} leaves docs/human-html/")
        return
    if not resolved.exists():
        errors.append(f"{rel}: broken {label} {ref!r}")
        return
    if fragment:
        if resolved == source_path.resolve():
            targets = source_ids
        else:
            targets = hash_targets_for_path(resolved, hash_target_cache)
        if targets is None:
            target_rel = resolved.relative_to(root)
            errors.append(
                f"{rel}: could not read {label} target {target_rel} to verify hash {ref!r}"
            )
        elif fragment not in targets:
            target_rel = resolved.relative_to(root)
            errors.append(f"{rel}: broken {label} hash {ref!r} (no #{fragment} in {target_rel})")


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _same_page_hash_ref(raw_ref: str) -> bool:
    parsed = urlsplit(raw_ref.strip())
    return not parsed.scheme and not parsed.netloc and not parsed.path and bool(parsed.fragment)


def find_comparison_violations(content: str) -> list[str]:
    """Return headings of comparison sections that have no visual."""
    matches = list(_HEADING_RE.finditer(content))
    if not matches:
        return []
    violations: list[str] = []
    for i, match in enumerate(matches):
        heading = _strip_tags(match.group(2)).strip()
        if not COMPARISON_HEADING_RE.search(heading):
            continue
        section_start = match.end()
        current_level = int(match.group(1))
        section_end = len(content)
        for next_match in matches[i + 1 :]:
            next_level = int(next_match.group(1))
            if next_level <= current_level:
                section_end = next_match.start()
                break
        section_body = _HTML_COMMENT_RE.sub("", content[section_start:section_end])
        if not any(pat.search(section_body) for pat in _VISUAL_PATTERNS):
            violations.append(heading)
    return violations


def _artifact_in_force(date_str: str) -> bool:
    """True if the artifact must satisfy the new content-shape rules."""
    try:
        artifact_date = dt.date.fromisoformat(date_str)
        cutoff = dt.date.fromisoformat(RULES_EFFECTIVE_DATE)
    except ValueError:
        return False
    return artifact_date >= cutoff


# Kinds where a reading guide adds enough value that we WARN if it is absent on
# a long enough artifact (mirrors the guidance in SKILL.md "Reading guide").
_READ_MAP_KINDS = {"architecture", "decision", "review", "plan", "incident"}


# Mechanical, low-false-positive subset of the SKILL.md "Anti-slop checklist":
# the violet AI-default accent ramp, placeholder text, the "Generated by AI"
# footer, and decorative emoji used as heading icons (arrows / ⚠ excluded so
# legitimate "Before → After" / warning headings don't trip it).
_SLOP_VIOLET_HEXES = ("#8b5cf6", "#7c3aed", "#a78bfa")
_SLOP_EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF]")

# House style: no em/en dashes in artifact prose (use a comma, colon,
# parentheses, or " - "). Code-bearing regions are exempt: dashes inside
# <pre>/<code>/<script>/<style> are often syntax, not prose. Both the literal
# characters and their HTML entities/numeric refs count: a named or numeric
# entity renders as an em dash just the same, so the rule catches encoded forms.
_DASH_EXEMPT_RE = re.compile(r"<(pre|code|script|style)\b.*?</\1\s*>", re.I | re.S)
_EM_EN_DASH_RE = re.compile(
    r"[–—]|&mdash;|&ndash;|&#8212;|&#8211;|&#x2014;|&#x2013;", re.IGNORECASE
)

# Token-aware constraint: a single self-contained artifact past this size is slow
# to load and expensive to feed back to a model. WARN (not block) - some legitimate
# corpora are large; the nudge is to split or trim.
_SIZE_BUDGET_BYTES = 512 * 1024


def _add(bucket: list[str], parser: ArtifactHTMLParser, rule_id: str, msg: str) -> None:
    """Append a violation unless the artifact has suppressed `rule_id` inline."""
    if rule_id in parser.suppressed_rules or "all" in parser.suppressed_rules:
        return
    bucket.append(f"{msg} [rule={rule_id}]")


def content_shape_violations(
    rel: Path, content: str, artifact_date: str, root: Path, kind: str = ""
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) per the post-cutoff content contract.

    Errors block (exit non-zero). Warnings print but exit 0.
    Returns empty lists for grandfathered (pre-cutoff) artifacts.

    Per-artifact suppression: a comment of the form
    ``<!-- human-html-disable: <rule-id>[,<rule-id>...] -->`` anywhere in the
    artifact suppresses the listed rules. Use the rule-id printed in brackets
    at the end of each violation message. The literal ``all`` suppresses every
    content-shape rule (use sparingly).
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not _artifact_in_force(artifact_date):
        return errors, warnings

    parser = ArtifactHTMLParser()
    parser.feed(content)

    if not parser.has_pm_summary:
        _add(
            errors, parser, "pm-summary",
            f'{rel}: missing top-level <section data-audience="pm"> '
            f"PM-summary block (plain-language three-bullet opener)",
        )

    for heading in find_comparison_violations(content):
        _add(
            errors, parser, "comparison-visual",
            f'{rel}: comparison section "{heading}" missing a visual '
            "(mermaid / svg / table / img / side-by-side grid)",
        )

    if parser.h2_count > 3 and parser.nav_count == 0:
        _add(
            errors, parser, "nav-anchors",
            f"{rel}: artifact has {parser.h2_count} <h2> sections but no <nav>; "
            "add an anchor list before the first <h2>",
        )
    elif parser.h2_count > 3 and not any(
        _same_page_hash_ref(href) and unquote(urlsplit(href).fragment) in parser.ids
        for href in parser.nav_hrefs
    ):
        _add(
            errors, parser, "nav-anchors",
            f"{rel}: artifact has {parser.h2_count} <h2> sections but its <nav> "
            "does not contain valid same-page anchor links",
        )

    effective_kind = kind or parser.meta.get("artifact-kind", "")
    for required_re, severity in REQUIRED_SECTIONS.get(effective_kind, []):
        pattern = re.compile(required_re, re.IGNORECASE)
        if not any(pattern.search(h) for h in parser.headings):
            bucket = errors if severity == "error" else warnings
            _add(
                bucket, parser, "required-section",
                f'{rel}: {effective_kind} kind is missing required section '
                f"matching /{required_re}/",
            )

    if not parser.has_meta_ribbon:
        _add(
            warnings, parser, "meta-ribbon",
            f"{rel}: missing metadata ribbon (a top-of-artifact strip with author / "
            'owner / status / date / tags); mark with data-meta-ribbon="true"',
        )

    if not parser.has_provenance:
        _add(
            warnings, parser, "provenance-footer",
            f"{rel}: missing provenance footer (prompt / model / reviewer); "
            'mark with data-provenance="true" or include '
            '<script type="application/ld+json" id="provenance">',
        )
    else:
        for field_warning in _provenance_field_warnings(rel, parser):
            _add(warnings, parser, "provenance-fields", field_warning)

    # Audience read-map: WARN on long artifacts of multi-audience kinds.
    if (
        effective_kind in _READ_MAP_KINDS
        and parser.h2_count > 3
        and not parser.has_read_map
    ):
        _add(
            warnings, parser, "read-map",
            f"{rel}: {effective_kind} artifact with {parser.h2_count} <h2> sections "
            'has no reading guide (add class="read-map" or '
            'aria-label="Reading map" to a block offering a Quick read vs Full read by anchor)',
        )

    # Meeting Q&A overlay: WARN per-question on missing required fields.
    if parser.has_meeting_qa:
        for qa_warning in _meeting_qa_warnings(rel, parser):
            _add(warnings, parser, "qa-overlay", qa_warning)

    # Shared-glossary linking (cross-doc known vocabulary): one WARN per artifact.
    glossary_path = artifact_dir(root) / "GLOSSARY.md"
    if glossary_path.exists():
        terms = _read_glossary_terms(glossary_path)
        unlinked = _unwrapped_glossary_terms(content, terms)
        if unlinked:
            _add(
                warnings, parser, "glossary-link",
                f"{rel}: glossary terms appear unwrapped: {', '.join(sorted(unlinked))} "
                "(wrap in <abbr title=...> or link to GLOSSARY.md#term)",
            )

    # Per-doc coined-term discipline (keyed off this doc's own <dfn> marks).
    allowlist = _load_jargon_allowlist(root)
    for rule_id, msg in plain_language_findings(
        content, allowlist=allowlist, kind=effective_kind
    ):
        _add(warnings, parser, rule_id, f"{rel}: {msg}")

    # Mobile: artifacts get opened on phones. A missing responsive viewport breaks
    # the page entirely (renders at desktop width); a wide table with no responsive
    # treatment clips or forces a tiny zoomed-out layout.
    if not (_VIEWPORT_NAME_RE.search(content) and _DEVICE_WIDTH_RE.search(content)):
        _add(
            errors, parser, "viewport-meta",
            f"{rel}: no responsive viewport meta -- add "
            '<meta name="viewport" content="width=device-width, initial-scale=1"> '
            "(without it the page renders at desktop width and is unusable on phones)",
        )
    if _TABLE_RE.search(content) and not _RESPONSIVE_TABLE_RE.search(content):
        _add(
            warnings, parser, "table-responsive",
            f"{rel}: a <table> is present with no responsive treatment -- add a "
            "@media (max-width) reflow (e.g. stack rows into cards via data-label) or "
            "wrap it in an overflow-x:auto container, or it clips/overflows on phones",
        )
    if _JS_DOM_WRITE_RE.search(content) and not _NOSCRIPT_RE.search(content):
        _add(
            warnings, parser, "js-content-fallback",
            f"{rel}: builds content with JavaScript (.innerHTML) but has no <noscript> "
            "fallback -- it renders BLANK in JS-disabled previews (iOS Quick Look, "
            "Android file/in-app previews, email). Pre-render the core content into the "
            "static HTML (JS then enhances it) or add a <noscript> fallback",
        )

    slop_hits: list[str] = []
    low = content.lower()
    violet = next((h for h in _SLOP_VIOLET_HEXES if h in low), "")
    if violet:
        slop_hits.append(f"violet AI-default accent {violet}")
    if "lorem ipsum" in low:
        slop_hits.append("placeholder text 'lorem ipsum'")
    if "generated by ai" in low:
        slop_hits.append("'Generated by AI' footer")
    emoji_heading = next((h for h in parser.headings if _SLOP_EMOJI_RE.search(h)), "")
    if emoji_heading:
        slop_hits.append(f'emoji icon in a heading ("{emoji_heading[:32]}")')
    if slop_hits:
        _add(
            warnings, parser, "slop-signal",
            f"{rel}: AI-default ('slop') signal(s): {'; '.join(slop_hits)} "
            "(see the Anti-slop checklist in SKILL.md)",
        )

    dash_count = len(_EM_EN_DASH_RE.findall(_DASH_EXEMPT_RE.sub("", content)))
    if dash_count:
        _add(
            warnings, parser, "em-dash",
            f"{rel}: {dash_count} em/en dash(es) in prose -- replace with a comma, "
            "colon, parentheses, or ' - ' (dashes inside <pre>/<code>/<script>/<style> "
            "are exempt)",
        )

    if len(content.encode("utf-8")) > _SIZE_BUDGET_BYTES:
        _add(
            warnings, parser, "size-budget",
            f"{rel}: artifact is {len(content.encode('utf-8')) // 1024} KiB "
            f"(> {_SIZE_BUDGET_BYTES // 1024} KiB) - slow to load and token-heavy; "
            "split it or move bulky evidence behind <details> / an appendix",
        )

    return errors, warnings


def _meeting_qa_warnings(rel: Path, parser: ArtifactHTMLParser) -> list[str]:
    """Warn when a meeting Q&A overlay is present but its JSON-LD is malformed
    or its questions are missing required fields."""
    if not parser.meeting_qa_json_scripts:
        return [
            f'{rel}: meeting Q&A overlay marker present (data-meeting-qa="true") but no '
            '<script type="application/ld+json" id="meeting-qa-data"> payload found'
        ]

    warnings: list[str] = []
    valid_statuses = {"answered", "partially_answered", "deferred", "action_item", "duplicate", "inferred"}

    for raw_script in parser.meeting_qa_json_scripts:
        try:
            decoded = json.loads(raw_script)
        except json.JSONDecodeError as exc:
            warnings.append(f"{rel}: invalid meeting Q&A JSON-LD ({exc.msg})")
            continue

        if not isinstance(decoded, dict):
            warnings.append(f"{rel}: meeting Q&A JSON-LD must be an object")
            continue

        questions = decoded.get("questions")
        if not isinstance(questions, list) or not questions:
            warnings.append(f"{rel}: meeting Q&A JSON-LD must include a non-empty `questions` array")
            continue

        for index, question in enumerate(questions):
            if not isinstance(question, dict):
                warnings.append(f"{rel}: meeting Q&A question #{index + 1} is not an object")
                continue
            qid = question.get("id") or f"#{index + 1}"
            missing: list[str] = []
            if not question.get("id"):
                missing.append("id")
            if not question.get("text"):
                missing.append("text")
            if not question.get("status"):
                missing.append("status")
            if not question.get("topic") and not question.get("topic_tags"):
                missing.append("topic (or topic_tags)")
            raw_status = question.get("status")
            status = ""
            if raw_status:
                if isinstance(raw_status, str):
                    status = raw_status.strip().lower()
                else:
                    warnings.append(
                        f"{rel}: meeting Q&A question {qid} has non-string status "
                        f"{raw_status!r}"
                    )
            if status and status not in valid_statuses:
                warnings.append(
                    f"{rel}: meeting Q&A question {qid} has unrecognised status {status!r} "
                    f"(expected one of: {', '.join(sorted(valid_statuses))})"
                )
            if status == "inferred":
                confidence = question.get("confidence")
                if (
                    isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not (0 <= float(confidence) <= 1)
                ):
                    warnings.append(
                        f"{rel}: inferred meeting Q&A question {qid} needs a numeric "
                        "confidence between 0 and 1"
                    )
                if not question.get("rationale"):
                    warnings.append(
                        f"{rel}: inferred meeting Q&A question {qid} needs a rationale"
                    )
            if missing:
                warnings.append(
                    f"{rel}: meeting Q&A question {qid} missing required fields: "
                    f"{', '.join(missing)}"
                )

    return warnings


def _provenance_field_warnings(rel: Path, parser: ArtifactHTMLParser) -> list[str]:
    """Warn when provenance JSON-LD is present but missing documented fields."""
    if not parser.provenance_json_scripts:
        return [f"{rel}: provenance footer has no JSON-LD field block to validate"]

    warnings: list[str] = []
    for raw_script in parser.provenance_json_scripts:
        try:
            decoded = json.loads(raw_script)
        except json.JSONDecodeError as exc:
            warnings.append(f"{rel}: invalid provenance JSON-LD ({exc.msg})")
            continue

        objects = decoded if isinstance(decoded, list) else [decoded]
        provenance_objects = [obj for obj in objects if isinstance(obj, dict)]
        if not provenance_objects:
            warnings.append(f"{rel}: provenance JSON-LD must be an object or array of objects")
            continue

        for obj in provenance_objects:
            missing: list[str] = []
            if not (obj.get("@id") or obj.get("id")):
                missing.append("@id or id")
            if not obj.get("creator"):
                missing.append("creator")
            if not (obj.get("promptHash") or obj.get("prompt")):
                missing.append("promptHash or prompt")
            if not obj.get("dateCreated"):
                missing.append("dateCreated")
            if not obj.get("reviewer"):
                missing.append("reviewer")
            if missing:
                warnings.append(
                    f"{rel}: provenance JSON-LD missing fields: {', '.join(missing)}"
                )
    return warnings


def _read_glossary_terms(path: Path) -> set[str]:
    """Extract term headings (## Term Name) from the workspace GLOSSARY.md."""
    terms: set[str] = set()
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                terms.add(line[3:].strip())
    except OSError:
        pass
    return terms


def _unwrapped_glossary_terms(content: str, terms: set[str]) -> set[str]:
    """Return glossary terms whose FIRST prose occurrence is unwrapped.

    First-use-aware (the standard: define/link on first mention, then use freely):
    a term is flagged only if its earliest visible occurrence is NOT inside an
    <abbr> or an <a> link. Wrapping just the first mention clears it -- so common
    terms need not be wrapped on every occurrence (which would wreck readability).
    """
    if not terms:
        return set()
    prose = _body_prose(content)
    blanked = _tag_blank(prose)
    wrapper_spans = [
        (m.start(), m.end())
        for pat in (_ABBR_RE, re.compile(r"<a\b[^>]*>.*?</a>", re.IGNORECASE | re.DOTALL))
        for m in pat.finditer(prose)
    ]
    found: set[str] = set()
    for term in terms:
        m = _term_regex(term).search(blanked)
        if m and not any(s <= m.start() < e for s, e in wrapper_spans):
            found.add(term)
    return found


# ============================================================================
# Plain-language / jargon enforcement (registry-gated, all WARN).
# Every check fires ONLY on terms the author declared -- workspace GLOSSARY.md
# (## headings) or in-doc <dfn> -- minus a universally-known allowlist. We never
# auto-classify a word as jargon (audience-relative; the top false-positive
# source). Sources: Google / Microsoft / IETF RFC 7322 3.6 / NN-g / WCAG
# H28,H54,G112 / ISO-IEC Directives Part 2 16.5.6 / arc42 s12 / Federal PLG.
# ============================================================================

# Universally-known terms never treated as coined jargon. Extend per workspace
# via docs/human-html/.jargon-allowlist (one term per line; # comments).
_JARGON_ALLOWLIST_DEFAULT = frozenset({
    "API", "REST", "URL", "URI", "HTTP", "HTTPS", "JSON", "YAML", "XML", "HTML",
    "CSS", "SQL", "PDF", "CLI", "UI", "UX", "SDK", "JWT", "SSE", "SSO", "LLM",
    "MCP", "ID", "CPU", "RAM", "OS", "IDE", "CI", "CD", "PR", "VPN", "DNS",
    "TLS", "SSH", "AWS", "GCP", "RPC", "AI", "QA", "HTTP",
})

# Number of distinct coined terms above which we warn (Federal PLG: "<= 3,
# preferably 2"; we allow more headroom for engineering docs).
_TERM_COUNT_WARN = 8

_DFN_RE = re.compile(r"<dfn\b[^>]*>(.*?)</dfn>", re.IGNORECASE | re.DOTALL)
_ABBR_RE = re.compile(r"<abbr\b([^>]*)>(.*?)</abbr>", re.IGNORECASE | re.DOTALL)
_AHASH_RE = re.compile(
    r"""<a\b[^>]*\bhref\s*=\s*['"]#[^'"]*['"][^>]*>(.*?)</a>""",
    re.IGNORECASE | re.DOTALL,
)
_DT_DD_RE = re.compile(
    r"<dt\b[^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>", re.IGNORECASE | re.DOTALL
)
# Definition-quality checks run ONLY inside the designated key-terms list, so an
# ordinary <dl> (metadata, key/value) never trips circular / bare-ref.
_KEYTERMS_DL_RE = re.compile(
    r"""<dl\b[^>]*\bid\s*=\s*['"]?key-terms['"]?[^>]*>(.*?)</dl>""",
    re.IGNORECASE | re.DOTALL,
)
# Accept quoted OR unquoted title= (valid HTML allows both).
_TITLE_ATTR_RE = re.compile(
    r"""\btitle\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE
)


def _title_value(attrs: str) -> str:
    m = _TITLE_ATTR_RE.search(attrs)
    if not m:
        return ""
    return next((g for g in m.groups() if g is not None), "").strip()


def _term_regex(term: str) -> re.Pattern[str]:
    """Word-boundary matcher for a coined term that tolerates internal whitespace
    runs (``Agent   ID`` / ``Agent\\nID``) and terms ending in non-word chars
    (``C++``) -- a bare \\b fails on both."""
    parts = [re.escape(p) for p in term.split()]
    core = r"\s+".join(parts) if parts else re.escape(term)
    return re.compile(rf"(?<!\w){core}(?!\w)")


def _load_jargon_allowlist(root: Path) -> set[str]:
    allow = set(_JARGON_ALLOWLIST_DEFAULT)
    try:
        raw = (artifact_dir(root) / ".jargon-allowlist").read_text(encoding="utf-8")
    except OSError:
        return allow
    for line in raw.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            allow.add(s)
    return allow


def _body_prose(content: str) -> str:
    """Body HTML with non-prose blocks removed; tags kept.

    Strips script/style/code/pre and <svg>: diagram labels are not wrappable prose
    (you cannot put <dfn>/<abbr> inside SVG), so a coined term appearing only in a
    diagram must not count as a use.
    """
    m = re.search(r"<body\b[^>]*>(.*)</body>", content, re.IGNORECASE | re.DOTALL)
    body = m.group(1) if m else content
    return re.sub(
        r"<(script|style|code|pre|svg)\b[^>]*>.*?</\1>", "", body,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _tag_blank(s: str) -> str:
    """Replace every tag with equal-length spaces so prose offsets are preserved."""
    return re.sub(r"<[^>]+>", lambda m: " " * len(m.group(0)), s)


def _dfn_terms(content: str) -> set[str]:
    """Coined terms the author marked with <dfn> (prose token = its text content).

    Whitespace is collapsed so a wrapped ``Agent\\nID`` still matches ``Agent ID``
    in prose.
    """
    out: set[str] = set()
    for inner in _DFN_RE.findall(content):
        text = " ".join(_strip_tags(inner).split())
        if text:
            out.add(text)
    return out


def _mask_longer(text: str, term: str, registry: set[str]) -> str:
    """Blank occurrences of any longer registry term that CONTAINS `term`, so
    searching for `term` never matches inside a longer coined phrase
    (``Agent`` must not match inside ``Agent ID``)."""
    masked = text
    for other in registry:
        if other != term and len(other) > len(term) and _term_regex(term).search(other):
            masked = _term_regex(other).sub(lambda m: " " * len(m.group(0)), masked)
    return masked


def _coined_registry(content: str, allowlist: set[str]) -> set[str]:
    """Coined terms THIS doc marked with <dfn>, minus the universal allowlist.

    Deliberately per-doc (not the shared GLOSSARY.md): the shared glossary is the
    audience's already-known vocabulary and is handled by the separate
    glossary-link check. Flagging every shared term here would nag every doc --
    the false-positive trap plain-language linters are notorious for.
    """
    return {t for t in _dfn_terms(content) if t and t not in allowlist}


def plain_language_findings(
    content: str, *, allowlist: set[str], kind: str = "",
) -> list[tuple[str, str]]:
    """Return (rule_id, message) plain-language WARNINGs. Registry-gated; never blocks.

    Checks fire only on terms THIS doc marked coined with <dfn>, minus the
    allowlist -- so a script never guesses whether a word is jargon.
    """
    out: list[tuple[str, str]] = []
    registry = _coined_registry(content, allowlist)
    prose = _body_prose(content)
    blanked = _tag_blank(prose)

    # Spans of defining/linked instances -- a first use inside one is fine.
    wrapper_spans: list[tuple[int, int]] = []
    for pat in (_DFN_RE, _ABBR_RE, _AHASH_RE):
        for m in pat.finditer(prose):
            wrapper_spans.append((m.start(), m.end()))

    def _dfn_pos(term: str) -> int | None:
        """Earliest position where <dfn> marks this term (its defining instance)."""
        best: int | None = None
        for m in _DFN_RE.finditer(prose):
            if " ".join(_strip_tags(m.group(1)).split()) == term:
                best = m.start() if best is None else min(best, m.start())
        return best

    # 1. First-use gloss: the <dfn> defining instance must PRECEDE any bare use.
    #    A "bare use" is an occurrence outside every wrapper (<dfn>/<abbr>/#-link)
    #    and not immediately parenthesised. Fires only when the author both marked
    #    the term AND used it bare earlier -> a real ordering defect, near-zero FP.
    for term in sorted(registry):
        dfn_pos = _dfn_pos(term)
        if dfn_pos is None:
            continue
        # Mask longer coined phrases so "Agent" is not matched inside "Agent ID".
        searchable = _mask_longer(blanked, term, registry)
        for m in _term_regex(term).finditer(searchable):
            pos = m.start()
            if pos >= dfn_pos:
                break                       # reached/passed the definition; fine
            if any(s <= pos < e for s, e in wrapper_spans):
                continue                    # inside <abbr>/#-link -> already glossed
            after = searchable[m.end(): m.end() + 4]
            if "(" in after:
                continue                    # parenthetical gloss on this use
            out.append((
                "first-use-gloss",
                f"coined term {term!r} is used before it is defined -- put its <dfn> "
                "(with a plain gloss + example) on the FIRST use, or link the earlier "
                "use to #key-terms",
            ))
            break

    # 2. Novel-term-count cap: too many coined terms to hold at once.
    if len(registry) > _TERM_COUNT_WARN:
        shown = ", ".join(sorted(registry)[:8])
        out.append((
            "term-count",
            f"{len(registry)} distinct coined terms ({shown}...) -- too many to hold at "
            "once; rename or delete some rather than defining more (deletion beats "
            "definition)",
        ))

    # 3 + 4. Definition-quality checks -- ONLY inside the designated key-terms
    #    list, so an ordinary <dl> (metadata, key/value) never trips them.
    keyterms_html = "".join(_KEYTERMS_DL_RE.findall(content))
    for dt_raw, dd_raw in _DT_DD_RE.findall(keyterms_html):
        term = " ".join(_strip_tags(dt_raw).split())
        definition = " ".join(_strip_tags(dd_raw).split())
        low = definition.lower()
        # 4. bare cross-reference: only "see X" with no real defining clause.
        if re.fullmatch(r"see\s+.+", low) and len(definition.split()) <= 5:
            out.append((
                "bare-gloss-ref",
                f"key-term definition {definition!r} is only a cross-reference -- give a "
                "real defining clause, not just 'see ...'",
            ))
        # 3. circular: the definition repeats its own head term. Exempt allowlisted
        #    acronyms (expanding "MCP is the Model Context Protocol" is not circular).
        if (
            term
            and term not in allowlist
            and _term_regex(term).search(definition)
        ):
            out.append((
                "circular-gloss",
                f"definition of {term!r} repeats the term itself (circular; ISO/IEC "
                "16.5.6) -- define it in plainer words",
            ))
    # 6. abbr completeness (WCAG H28): a coined <abbr> needs a non-empty title.
    #    Allowlisted abbreviations (HTML, JSON, ...) are known -> not nagged.
    for attrs, inner in _ABBR_RE.findall(content):
        label = " ".join(_strip_tags(inner).split())
        if label in allowlist:
            continue
        if not _title_value(attrs):
            shown = label[:24] or "?"
            out.append((
                "abbr-title",
                f"<abbr>{shown}</abbr> has no title -- add title=\"full expansion\" so "
                "the abbreviation is accessible (WCAG H28)",
            ))

    # 7. Heading debut: a coined term must not make its first appearance in a
    #    heading -- introduce and gloss it in the first body sentence (Microsoft).
    heading_spans = [
        (m.start(), m.end())
        for m in re.finditer(r"<h([1-6])\b[^>]*>.*?</h\1>", prose, re.IGNORECASE | re.DOTALL)
    ]
    for term in sorted(registry):
        searchable = _mask_longer(blanked, term, registry)
        occ = [m.start() for m in _term_regex(term).finditer(searchable)]
        if occ and any(s <= occ[0] < e for s, e in heading_spans):
            out.append((
                "heading-debut",
                f"coined term {term!r} first appears inside a heading -- introduce and "
                "gloss it in the first body sentence instead",
            ))

    # 8. Key-terms block: an architecture/decision doc that coins several terms
    #    should collect them in a <dl id="key-terms"> (arc42 s12). Only fires once
    #    the author has marked >= 3 coined terms, so it never nags a plain doc.
    if kind in {"architecture", "decision"} and len(registry) >= 3:
        if not re.search(
            r"""<dl\b[^>]*\bid\s*=\s*['"]key-terms['"]""", content, re.IGNORECASE
        ):
            out.append((
                "key-terms-block",
                f"{len(registry)} coined terms but no <dl id=\"key-terms\"> block -- "
                "collect them in a key-terms list after the summary (arc42 s12)",
            ))

    return out


_SUMMARY_MAX = 200
_KW_STOPWORDS = {"and", "the", "for", "vs", "of", "a", "to", "in", "on", "with", "an", "is", "at"}


def _clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _truncate_summary(text: str, limit: int = _SUMMARY_MAX) -> str:
    text = _clean_text(text)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:—- ") + "…"


def _strip_lead_label(text: str) -> str:
    """PM-summary leads read 'Label: sentence' - keep the sentence."""
    if ":" in text[:60]:
        _, _, tail = text.partition(":")
        if tail.strip():
            return tail.strip()
    return text


def _sentence_case(text: str) -> str:
    """Capitalise the first letter, but leave camelCase / initialisms (iOS) alone."""
    if text and text[0].islower() and (len(text) < 2 or text[1].islower()):
        return text[0].upper() + text[1:]
    return text


def derive_summary(parser: ArtifactHTMLParser, meta: dict[str, str], title: str) -> str:
    """Hybrid summary: authored meta wins, else auto-extract from content."""
    candidates = [meta.get("artifact-summary", ""), parser.description]
    # Strip the label BEFORE the placeholder check: an unfilled scaffold lead reads
    # "What this does for the user: Replace with ..." - only the stripped tail reveals
    # the "Replace with" placeholder, which must not leak into the gallery summary.
    lead = _strip_lead_label(parser.pm_lead) if parser.pm_lead else ""
    if lead and not lead.lower().startswith("replace with"):
        candidates.append(lead)
    for heading in parser.h2_headings:
        if heading.strip().lower() not in {"in plain terms", "on this page"}:
            candidates.append(heading)
            break
    candidates.append(title)
    for candidate in candidates:
        cleaned = _clean_text(candidate)
        if cleaned:
            return _truncate_summary(_sentence_case(cleaned))
    return ""


def derive_keywords(
    parser: ArtifactHTMLParser, meta: dict[str, str], kind: str, slug: str
) -> tuple[str, ...]:
    """Hybrid keywords: authored meta wins, else derive from kind + slug tokens."""
    raw = meta.get("artifact-keywords", "") or parser.keywords_meta
    if raw.strip():
        candidates = [k.strip() for k in raw.split(",") if k.strip()]
    else:
        tokens = [
            t for t in re.split(r"[-_/]", slug)
            if len(t) >= 2 and t.lower() not in _KW_STOPWORDS
        ]
        candidates = [kind, *tokens]
    seen: set[str] = set()
    out: list[str] = []
    for keyword in candidates:
        lowered = keyword.lower()
        if lowered not in seen:
            seen.add(lowered)
            out.append(keyword)
        if len(out) >= 8:
            break
    return tuple(out)


def read_artifacts(root: Path) -> tuple[list[Artifact], list[str]]:
    artifacts: list[Artifact] = []
    errors: list[str] = []
    hash_target_cache: dict[Path, set[str] | None] = {}

    for path in iter_html_files(root):
        rel = path.relative_to(root)
        rel_from_artifacts = path.relative_to(artifact_dir(root))
        is_top_level = path.parent == artifact_dir(root)
        match = NAME_RE.match(path.name)
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            errors.append(f"{rel}: unreadable as UTF-8 HTML ({exc.__class__.__name__}); skipped")
            continue
        parser = ArtifactHTMLParser()
        parser.feed(content)
        meta = parser.meta

        identity_valid = True
        date = meta.get("artifact-created", "")
        kind = meta.get("artifact-kind", "")
        slug = rel_from_artifacts.with_suffix("").as_posix()

        if is_top_level and not match:
            errors.append(f"{rel}: filename must match YYYY-MM-DD-kind-slug.html")
            identity_valid = False

        if match:
            filename_date = match.group("date")
            filename_kind = match.group("kind")
            slug = match.group("slug")
            try:
                dt.date.fromisoformat(filename_date)
            except ValueError:
                errors.append(f"{rel}: invalid ISO date in filename")
                identity_valid = False
            if date and date != filename_date:
                errors.append(f"{rel}: artifact-created does not match filename date")
                identity_valid = False
            if kind and kind != filename_kind:
                errors.append(f"{rel}: artifact-kind does not match filename kind")
                identity_valid = False
            date = date or filename_date
            kind = kind or filename_kind

        if not parser.has_body_marker:
            errors.append(f'{rel}: missing body marker data-human-html-artifact="true"')
            identity_valid = False
        if meta.get("artifact-audience") != "human":
            errors.append(f"{rel}: missing or invalid artifact-audience=human")
            identity_valid = False
        if kind not in KINDS:
            errors.append(f"{rel}: missing or invalid artifact-kind")
            identity_valid = False
        try:
            dt.date.fromisoformat(date)
        except ValueError:
            errors.append(f"{rel}: missing or invalid artifact-created date")
            identity_valid = False

        for href in parser.hrefs:
            _validate_local_reference(
                root, path, href, "href", errors, parser.ids, hash_target_cache
            )
        for asset_kind, ref in parser.asset_refs:
            _validate_local_reference(
                root, path, ref, asset_kind, errors, parser.ids, hash_target_cache
            )

        if identity_valid:
            title = parse_title(content, Path(slug).name.replace("-", " ").title())
            artifacts.append(
                Artifact(
                    path=path,
                    href=rel_from_artifacts.as_posix(),
                    date=date,
                    kind=kind,
                    slug=slug,
                    title=title,
                    source=meta.get("artifact-source", "local"),
                    summary=derive_summary(parser, meta, title),
                    keywords=derive_keywords(parser, meta, kind, slug),
                )
            )

    return artifacts, errors


def root_html_errors(root: Path) -> list[str]:
    """Flag root-level HTML only when it LOOKS like a human-html artifact.

    A plain root index.html (a static site's landing page, this repo's own
    gallery) is legitimate; only artifact-shaped files belong in the lane."""
    errors: list[str] = []
    for p in sorted(root.glob("*.html")):
        looks_like_artifact = bool(NAME_RE.match(p.name))
        if not looks_like_artifact:
            try:
                head = p.read_text(encoding="utf-8", errors="ignore")[:4096]
            except OSError:
                continue
            looks_like_artifact = (
                "data-human-html-artifact" in head or 'name="artifact-kind"' in head
            )
        if looks_like_artifact:
            errors.append(
                f"{p.relative_to(root)}: HTML artifacts are not allowed at workspace root"
            )
    return errors


# Muted, distinguishable per-kind dot colours for the gallery (categorical legend,
# not decoration). Deliberately avoids the violet AI-default ramp the slop rule bans.
_KIND_COLORS = {
    "plan": "#2563eb", "review": "#c5542d", "architecture": "#2d7a55",
    "understanding": "#0e7490", "research": "#b45309", "decision": "#9f1239",
    "prototype": "#db2777", "status": "#6b7280", "incident": "#b91c1c",
}

# ---------------------------------------------------------------------------
# Theme system: a light/dark toggle baked into every artifact and the gallery.
# Base :root is light and renders on any engine. The dark palette (contrast-verified)
# is emitted by _dark_scheme_css() into two screen-scoped selectors: an explicit
# toggle choice (:root[data-theme="dark"]) and the OS preference with no explicit
# choice (:root:not([data-theme])). Wrapping the dark tokens in @media screen keeps
# PRINT on the light base, so PDF handoff stays light. Default follows the reader's
# OS; an explicit choice persists in localStorage. Progressive enhancement: with JS
# off, the page still follows the OS via the media query and the (non-functional)
# toggle button stays hidden. No .innerHTML is used, so the no-JS content contract
# (the js-content-fallback rule) is untouched.
# ---------------------------------------------------------------------------

_SCAFFOLD_DARK_TOKENS = (
    "        color-scheme: dark;\n"
    "        --bg:#0f1522; --surface:#161e2e; --surface-2:#1c2536; --surface-3:#232e42;\n"
    "        --ink:#e8edf5; --ink-2:#c3ccdb; --muted:#96a2b5; --faint:#8593a8;\n"
    "        --line:#253145; --line-strong:#33415a;\n"
    "        --accent:#6aa8dd; --accent-2:#85bce6; --accent-bg:#152740; --accent-line:#2c4a6b;\n"
    "        --crit:#f19488; --crit-bg:#351d22; --crit-line:#6b3936;\n"
    "        --high:#eda06b; --high-bg:#33251a; --high-line:#6b4a30;\n"
    "        --warn:#d8b45c; --warn-bg:#312a16; --warn-line:#665626;\n"
    "        --good:#74c99b; --good-bg:#16301f; --good-line:#2e5c42;\n"
    "        --info:#6aa8dd; --info-bg:#152740; --info-line:#2c4a6b;\n"
    "        --neutral:#9aa6ba; --neutral-bg:#232c3c; --neutral-line:#3a465a;\n"
    "        --shadow-sm:0 1px 2px rgba(0,0,0,.35);\n"
    "        --shadow:0 4px 14px rgba(0,0,0,.45), 0 1px 3px rgba(0,0,0,.3);"
)

# Gallery uses a smaller token subset; --warn-* here back the .skipped banner.
_INDEX_DARK_TOKENS = (
    "        color-scheme: dark;\n"
    "        --ink:#e8edf5; --muted:#96a2b5; --line:#253145; --soft:#1c2536;\n"
    "        --bg:#0f1522; --surface:#161e2e;\n"
    "        --accent:#6aa8dd; --accent-2:#e0895f; --good:#74c99b;\n"
    "        --warn-bg:#33251a; --warn-line:#6b4a30; --warn-fg:#eda06b;"
)


def _dark_scheme_css(tokens: str) -> str:
    """Emit the dark palette into two screen-scoped selectors (explicit toggle +
    OS preference). @media screen keeps print on the light base for PDF handoff."""
    return (
        "    @media screen {\n"
        '      :root[data-theme="dark"] {\n'
        f"{tokens}\n"
        "      }\n"
        "    }\n"
        "    @media screen and (prefers-color-scheme: dark) {\n"
        "      :root:not([data-theme]) {\n"
        f"{tokens}\n"
        "      }\n"
        "    }"
    )


# Blocking head init: applies a saved theme before first paint (no flash) and flags
# JS-on (.theme-js) so the toggle appears only when it can work.
_THEME_INIT = """  <script>
    (function(){try{var r=document.documentElement;r.classList.add('theme-js');var t=localStorage.getItem('hh-theme');if(t==='dark'||t==='light')r.dataset.theme=t;}catch(e){}})();
  </script>"""

_THEME_TOGGLE_BUTTON = '  <button class="theme-toggle" type="button" aria-label="Switch theme" title="Toggle light / dark"></button>'

# Fixed sun/moon toggle. Hidden until .theme-js is set (JS on) and hidden in print.
# --surface-2/--line-strong fall back to gallery tokens so one style fits both templates.
_THEME_TOGGLE_STYLE = r"""    .theme-toggle { display:none; }
    .theme-js .theme-toggle { position:fixed; top:16px; right:16px; z-index:100; width:40px; height:40px; padding:0; display:inline-flex; align-items:center; justify-content:center; font:inherit; font-size:18px; line-height:1; cursor:pointer; background:var(--surface-2, var(--soft)); color:var(--muted); border:1px solid var(--line); border-radius:999px; }
    .theme-js .theme-toggle:hover { color:var(--ink); border-color:var(--line-strong, var(--line)); }
    .theme-js .theme-toggle:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    .theme-toggle::before { content:"\263E"; }
    :root[data-theme="dark"] .theme-toggle::before { content:"\2600"; }
    @media (prefers-color-scheme:dark){ :root:not([data-theme]) .theme-toggle::before{ content:"\2600"; } }
    @media print { .theme-toggle { display:none; } }"""

_THEME_TOGGLE_SCRIPT = """  <script>
    (function(){
      var btn=document.querySelector('.theme-toggle'); if(!btn) return;
      function cur(){ return document.documentElement.dataset.theme || (window.matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'); }
      function label(){ btn.setAttribute('aria-label', cur()==='dark'?'Switch to light theme':'Switch to dark theme'); }
      label();
      btn.addEventListener('click', function(){
        var next=cur()==='dark'?'light':'dark';
        document.documentElement.dataset.theme=next;
        try{ localStorage.setItem('hh-theme', next); }catch(e){}
        label();
      });
    })();
  </script>"""

_INDEX_STYLE = """
    :root { color-scheme: light; --ink:#172033; --muted:#5a6577; --line:#dbe2ec; --soft:#f2f5f9; --bg:#f6f8fb; --surface:#fff;
      --accent:#226fb2; --accent-2:#c5542d; --good:#2d7a55;
      --warn-bg:#fff7ed; --warn-line:#f97316; --warn-fg:#9a3412;   /* backs .skipped; flips in dark */
      --display:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,ui-serif,serif;
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", "Helvetica Neue", sans-serif; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:var(--bg); }
    main { width:min(1180px, calc(100vw - 40px)); margin:0 auto; padding:44px 0 64px; }
    header { border-bottom:1px solid var(--line); padding-bottom:22px; margin-bottom:22px; }
    h1 { margin:0 0 8px; font-family:var(--display); font-size:clamp(2rem,4vw,3.2rem); font-weight:800; line-height:1.05; letter-spacing:-.02em; }
    p.lede { color:var(--muted); line-height:1.55; max-width:74ch; margin:0; }
    .meta { color:var(--muted); font-size:.85rem; margin-top:10px; }
    a { color:var(--accent); text-decoration:none; }
    :focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    a:hover { text-decoration:underline; }
    code { background:var(--soft); border:1px solid var(--line); border-radius:6px; padding:2px 5px; font-size:.88em; }
    .kind { display:inline-block; border:1px solid color-mix(in srgb, var(--accent) 30%, var(--line));
      background:color-mix(in srgb, var(--accent) 8%, var(--surface)); color:var(--accent);
      border-radius:999px; padding:3px 10px; font-size:.74rem; font-weight:700; letter-spacing:.02em; }
    .toolbar { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:0 0 14px; }
    .toolbar input[type=search] { flex:1 1 260px; padding:10px 12px; border:1px solid var(--line);
      border-radius:8px; font:inherit; color:var(--ink); background:var(--surface); }
    .chips { display:flex; flex-wrap:wrap; gap:6px; }
    .chip { border:1px solid var(--line); background:var(--soft); color:var(--muted); border-radius:999px;
      padding:5px 11px; font-size:.78rem; font-weight:650; cursor:pointer; }
    .chip[aria-pressed=true] { background:color-mix(in srgb, var(--accent) 12%, var(--surface)); color:var(--accent);
      border-color:color-mix(in srgb, var(--accent) 35%, var(--line)); }
    .count { color:var(--muted); font-size:.82rem; margin:0 0 16px; }
    .skipped { background:var(--warn-bg); border:1px solid var(--warn-line); color:var(--warn-fg); border-radius:8px;
      padding:10px 14px; margin:0 0 18px; font-size:.88rem; }
    .skipped code { background:var(--surface); }
    .cards { display:grid; grid-template-columns:repeat(auto-fill, minmax(300px,1fr)); gap:16px; }
    .card { border:1px solid var(--line); border-radius:10px; padding:15px 17px; background:var(--surface);
      display:flex; flex-direction:column; gap:8px; }
    .card[hidden] { display:none; }
    .card .top { display:flex; justify-content:space-between; align-items:center; gap:10px; }
    .kind::before { content:""; display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--c, var(--accent)); margin-right:6px; vertical-align:middle; }
    .card .when { display:flex; align-items:center; gap:6px; }
    .card .date { color:var(--muted); font-size:.8rem; font-variant-numeric:tabular-nums; }
    .card .rel { color:var(--muted); font-size:.72rem; }
    .new-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--accent-2); }
    .new-dot[hidden] { display:none; }
    .card h2 { margin:0; font-size:1rem; line-height:1.3; }
    .card h2 a { color:var(--accent); font-weight:680; }
    .card .summary { margin:0; color:var(--ink); font-size:.88rem; line-height:1.5; }
    .card .kw { display:flex; flex-wrap:wrap; gap:5px; margin-top:auto; padding-top:4px; }
    .card .kw span { background:var(--soft); border:1px solid var(--line); border-radius:6px;
      padding:2px 7px; font-size:.72rem; color:var(--muted); }
    .empty { color:var(--muted); text-align:center; padding:40px; grid-column:1/-1; }
    @media (max-width:560px) { .cards { grid-template-columns:1fr; } }
""".strip()

_INDEX_SCRIPT = """
  (function () {
    var q = document.getElementById('q');
    var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
    var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
    var count = document.getElementById('count');

    // Relative timestamps + "new since last visit" dots. Novelty is tracked per
    // artifact href in localStorage (not a timestamp), so an artifact added later
    // the same day still flags as new. Degrades silently (storage off / file://).
    var KEY = 'human-html:seen', now = Date.now(), seen = null;
    try { var raw = localStorage.getItem(KEY); if (raw) seen = JSON.parse(raw); } catch (e) {}
    function rel(iso) {
      var days = Math.floor((now - new Date(iso + 'T00:00:00').getTime()) / 86400000);
      if (days <= 0) return 'today';
      if (days === 1) return '1d ago';
      if (days < 30) return days + 'd ago';
      if (days < 365) return Math.floor(days / 30) + 'mo ago';
      return Math.floor(days / 365) + 'y ago';
    }
    var current = {};
    cards.forEach(function (c) {
      var iso = c.getAttribute('data-date');
      if (iso) { var r = c.querySelector('.rel'); if (r) r.textContent = rel(iso); }
      var a = c.querySelector('a[href]');
      var href = a ? a.getAttribute('href') : '';
      if (!href) return;
      current[href] = 1;
      // seen === null is the first visit: do not flag everything as new.
      var nd = c.querySelector('.new-dot');
      if (nd && seen && !seen[href]) nd.hidden = false;
    });
    try { localStorage.setItem(KEY, JSON.stringify(current)); } catch (e) {}

    // Fuzzy filter: substring first, then in-order subsequence fallback.
    function match(hay, needle) {
      if (hay.indexOf(needle) > -1) return true;
      var j = 0;
      for (var i = 0; i < hay.length && j < needle.length; i++) if (hay[i] === needle[j]) j++;
      return j === needle.length;
    }
    var activeKind = 'all';
    function apply() {
      var t = (q && q.value || '').trim().toLowerCase();
      var n = 0;
      cards.forEach(function (c) {
        var ok = (activeKind === 'all' || c.getAttribute('data-kind') === activeKind) &&
                 (!t || match(c.getAttribute('data-text'), t));
        c.hidden = !ok;
        if (ok) n++;
      });
      if (count) count.textContent = n + ' of ' + cards.length + ' shown';
    }
    if (q) q.addEventListener('input', apply);
    chips.forEach(function (ch) {
      ch.addEventListener('click', function () {
        activeKind = ch.getAttribute('data-kind');
        chips.forEach(function (x) { x.setAttribute('aria-pressed', x === ch ? 'true' : 'false'); });
        apply();
      });
    });
    apply();
  })();
""".strip()


def render_index(artifacts: list[Artifact], skipped: int = 0) -> str:
    ordered = sorted(artifacts, key=lambda a: (a.date, a.kind, a.slug), reverse=True)

    def card(a: Artifact) -> str:
        kw = "".join(f"<span>{html.escape(k)}</span>" for k in a.keywords)
        kw_block = f'\n        <div class="kw">{kw}</div>' if kw else ""
        summary_block = (
            f'\n        <p class="summary">{html.escape(a.summary)}</p>' if a.summary else ""
        )
        haystack = " ".join(
            [a.title, a.summary, " ".join(a.keywords), a.kind, a.date]
        ).lower()
        color = _KIND_COLORS.get(a.kind, "#226fb2")
        return (
            f'      <article class="card" data-kind="{html.escape(a.kind, quote=True)}"'
            f' data-date="{html.escape(a.date, quote=True)}" style="--c:{color}"'
            f' data-text="{html.escape(haystack, quote=True)}">\n'
            f'        <div class="top"><span class="kind">{html.escape(a.kind)}</span>'
            f'<span class="when"><span class="new-dot" hidden title="new since your last visit"></span>'
            f'<span class="date">{html.escape(a.date)}</span> <span class="rel"></span></span></div>\n'
            f'        <h2><a href="{html.escape(a.href, quote=True)}" target="_blank" rel="noopener">'
            f"{html.escape(a.title)}</a></h2>"
            f"{summary_block}{kw_block}\n"
            f"      </article>"
        )

    cards = "\n".join(card(a) for a in ordered) or '      <p class="empty">No artifacts yet.</p>'
    kinds_present = sorted({a.kind for a in ordered})
    chips = '<button class="chip" data-kind="all" aria-pressed="true">All</button>' + "".join(
        f'\n        <button class="chip" data-kind="{html.escape(k, quote=True)}"'
        f' aria-pressed="false">{html.escape(k)}</button>'
        for k in kinds_present
    )
    latest = max((a.date for a in artifacts), default="no artifacts")
    banner = (
        f'    <div class="skipped">⚠ {skipped} file(s) could not be indexed '
        f"(failed the file contract). Run <code>check</code> to see why.</div>\n"
        if skipped
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Human HTML Artifacts</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ctext y='13' font-size='13'%3E🗂️%3C/text%3E%3C/svg%3E">
{_THEME_INIT}
  <style>
{_INDEX_STYLE}
{_THEME_TOGGLE_STYLE}
{_dark_scheme_css(_INDEX_DARK_TOKENS)}
  </style>
  <noscript><style>.toolbar, .count {{ display:none; }}</style></noscript>
</head>
<body>
{_THEME_TOGGLE_BUTTON}
  <main>
    <header>
      <h1>Human HTML Artifacts</h1>
      <p class="lede">Review, plan, architecture, understanding, research, decision, prototype, status, and incident artifacts, built for humans to read.</p>
      <div class="meta">{len(artifacts)} artifact(s) &middot; latest {html.escape(latest)}</div>
    </header>
{banner}    <div class="toolbar">
      <input type="search" id="q" placeholder="Filter by title, summary, or keyword&hellip;" aria-label="Filter artifacts">
      <div class="chips">
        {chips}
      </div>
    </div>
    <p class="count" id="count"></p>
    <div class="cards">
{cards}
    </div>
  </main>
  <script>
{_INDEX_SCRIPT}
  </script>
{_THEME_TOGGLE_SCRIPT}
</body>
</html>
"""


def write_index(root: Path) -> None:
    adir = artifact_dir(root)
    adir.mkdir(parents=True, exist_ok=True)
    artifacts, errors = read_artifacts(root)
    # Skip-and-warn: a single malformed file must never freeze the whole gallery
    # (the autoindex hook swallows aborts, which silently staled the index).
    # `check` stays strict for CI; here we render what's valid and surface the rest.
    skipped = len(iter_html_files(root)) - len(artifacts)
    if errors:
        for error in errors:
            print(f"WARN: {error}", file=sys.stderr)
    ordered = sorted(artifacts, key=lambda a: (a.date, a.kind, a.slug), reverse=True)
    idx = index_file(root)
    idx.write_text(render_index(artifacts, skipped), encoding="utf-8")
    # Projected machine-readable manifest so a subagent can read a few-KB JSON
    # instead of every artifact. .json is not globbed by iter_html_files.
    manifest = adir / "docs-index.json"
    manifest.write_text(
        json.dumps(
            {
                "count": len(ordered),
                "artifacts": [
                    {
                        "date": a.date, "kind": a.kind, "slug": a.slug, "title": a.title,
                        "summary": a.summary, "keywords": list(a.keywords),
                        "source": a.source, "href": a.href,
                    }
                    for a in ordered
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    suffix = f" ({skipped} skipped - run check)" if skipped else ""
    print(f"indexed {len(artifacts)} artifact(s){suffix} -> {idx.relative_to(root)}")


# Per-kind emoji favicon (stable across revisions - tab identity; do not change on rework).
_KIND_FAVICON = {
    "plan": "🗺️", "review": "🔍", "architecture": "🏛️", "understanding": "💡",
    "research": "🔬", "decision": "⚖️", "prototype": "🧪", "status": "📍", "incident": "🚨",
}

_SCAFFOLD_STYLE = """
    :root {
      color-scheme: light;                     /* base = light, renders on any engine; dark tokens live in the @media screen blocks appended after this constant */
      /* surfaces: cool off-white, slight blue-grey hue bias (never pure grey/white) */
      --bg: #f6f8fb; --surface: #ffffff; --surface-2: #f2f5f9; --surface-3: #e9eef4;
      /* ink: navy-biased grey ramp (never pure black) */
      --ink: #172033; --ink-2: #3c4657; --muted: #5a6577; --faint: #66707f;  /* --faint is text-safe AA (4.7:1 on --bg) */
      /* structure */
      --line: #dbe2ec; --line-strong: #c6cfdc;
      /* brand accent (#226fb2) + tint */
      --accent: #226fb2; --accent-2: #1b5e97; --accent-bg: #eef5fb; --accent-line: #b9d5ec;
      /* severity: fg / tint-bg / tint-line triples (semantic color only) */
      --crit: #c0342a; --crit-bg: #fbeae8; --crit-line: #f0c4be;
      --high: #a84522; --high-bg: #fbeee6; --high-line: #f0cdba;  /* fg contrast-locked to tint (5.2:1) */
      --warn: #845d06; --warn-bg: #f9f1d8; --warn-line: #e8d69a;  /* fg contrast-locked to tint (5.2:1) */
      --good: #2d7a55; --good-bg: #e9f5ee; --good-line: #b6ddc6;
      --info: #226fb2; --info-bg: #eef5fb; --info-line: #b9d5ec;
      --neutral: #5a6577; --neutral-bg: #eef1f5; --neutral-line: #d7dde6;
      /* legacy aliases: keep every existing selector below valid (safe incremental migration) */
      --blue: var(--accent); --soft: var(--surface-2);
      --orange: var(--high); --green: var(--good);
      --rose-bg: var(--high-bg); --rose-line: var(--high);
      --emerald-bg: var(--good-bg); --emerald-line: var(--good);
      /* elevation */
      --shadow-sm: 0 1px 2px rgba(23,32,51,.05);
      --shadow: 0 1px 2px rgba(23,32,51,.05), 0 8px 24px rgba(23,32,51,.06);
      /* radius */
      --radius: 10px; --radius-sm: 6px; --radius-lg: 14px;
      /* spacing scale */
      --s-1:4px; --s-2:6px; --s-3:8px; --s-4:12px; --s-5:14px; --s-6:16px; --s-7:18px; --s-8:20px; --s-9:24px; --s-10:32px; --s-12:48px;
      /* families: display serif for h1/numbers, sans body (NOT led by Inter), mono kickers */
      --display: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, ui-serif, serif;
      --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", "Helvetica Neue", sans-serif;
      --mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
      /* fluid type scale: only the 3 biggest levels clamp; body & below fixed so copy never wobbles */
      --fs-h1: clamp(2rem, 1.35rem + 2.6vw, 3.2rem);
      --fs-h2: clamp(1.3rem, 1.15rem + .7vw, 1.6rem);
      --fs-h3: 1.05rem; --fs-lede: clamp(1.05rem, 1rem + .35vw, 1.18rem);
      --fs-body: 1rem; --fs-sm: .875rem; --fs-cap: .72rem;
      --lh-body: 1.62; --ls-caps: .1em;
      font-family: var(--sans);
    }
    * { box-sizing: border-box; }
    body { margin: 0; color: var(--ink); background: var(--bg); font-family: var(--sans); line-height: var(--lh-body); accent-color: var(--accent); text-rendering: optimizeLegibility; -webkit-font-smoothing: antialiased; font-feature-settings: "kern", "liga"; }
    main { width: min(1060px, calc(100vw - clamp(2rem, 8vw, 5rem))); margin: 0 auto; padding: clamp(28px,5vw,56px) 0 clamp(64px,10vw,96px); }
    header { border-bottom: 1px solid var(--line); padding-bottom: var(--s-9); margin-bottom: var(--s-10); }
    .eyebrow { font-family: var(--mono); color: var(--accent); font-size: var(--fs-cap); font-weight: 600; text-transform: uppercase; letter-spacing: .14em; }
    h1 { margin: 10px 0 12px; font-family: var(--display); font-size: var(--fs-h1); font-weight: 800; line-height: 1.05; letter-spacing: -.02em; }
    h2 { margin: 0 0 12px; font-size: var(--fs-h2); font-weight: 700; letter-spacing: -.01em; }
    h3 { margin: 18px 0 8px; font-size: var(--fs-h3); font-weight: 600; color: var(--ink); }
    h1, h2, h3 { text-wrap: balance; }
    p { color: var(--ink-2); line-height: var(--lh-body); max-width: 72ch; text-wrap: pretty; }
    li { max-width: 72ch; }
    a { color: var(--accent); }
    :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    .pm-summary { background: var(--surface-2); border-left: 4px solid var(--accent); padding: 20px 22px; border-radius: var(--radius); margin: 16px 0 32px; box-shadow: var(--shadow-sm); }
    .pm-summary h2 { color: var(--accent); margin-bottom: 12px; }
    .pm-summary ul { margin: 0; padding-left: 20px; }
    .pm-summary li { margin-bottom: 8px; color: var(--ink-2); line-height: 1.55; }
    .pm-summary li strong { color: var(--accent); }
    nav.toc { background: var(--surface-2); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 20px; margin: 16px 0 32px; }
    nav.toc ol { margin: 8px 0 0; padding-left: 22px; columns: 2; column-gap: 24px; }
    nav.toc li { margin-bottom: 4px; }
    nav.toc a { color: var(--accent); text-decoration: none; }
    nav.toc a:hover { text-decoration: underline; }
    section.section { margin-top: clamp(32px,5vw,52px); }
    section[id] { scroll-margin-top: var(--s-9); }
    section:target > h2 { color: var(--accent-2); }
    .grid-cols-2, .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--s-6); }
    .grid-3 { display: grid; grid-template-columns: repeat(3,1fr); gap: var(--s-6); }
    /* grid items default to min-width:auto and will not shrink below a wide child (a long <pre> or code
       line), pushing the page past a phone viewport. min-width:0 lets the child's overflow-x:auto scroll. */
    .grid-cols-2 > *, .grid-2 > *, .grid-3 > *, .compare-before, .compare-after { min-width: 0; }
    .compare-before { background: var(--high-bg); border-left: 4px solid var(--high); border-radius: var(--radius); padding: 16px; }
    .compare-after { background: var(--good-bg); border-left: 4px solid var(--good); border-radius: var(--radius); padding: 16px; }
    .compare-before > strong:first-child, .compare-after > strong:first-child { display: block; margin-bottom: 8px; font-family: var(--mono); font-size: var(--fs-cap); letter-spacing: .08em; text-transform: uppercase; }
    .compare-before > strong:first-child { color: var(--high); }
    .compare-after > strong:first-child { color: var(--good); }
    table { width: 100%; border-collapse: collapse; border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; }
    th, td { padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-variant-numeric: tabular-nums; }
    th { background: var(--surface-2); color: var(--muted); font-family: var(--mono); font-size: var(--fs-cap); text-transform: uppercase; letter-spacing: .08em; }
    tr:last-child td { border-bottom: 0; }
    .table-scroll { overflow-x: auto; border-radius: var(--radius); }
    .table-scroll table { display: table; }
    code { background: var(--surface-2); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 2px 5px; font-family: var(--mono); font-size: .88em; overflow-wrap: anywhere; }
    pre { background: #0f172a; color: #e2e8f0; border-radius: var(--radius); padding: 14px; overflow: auto; border: 1px solid var(--line); }
    pre code { background: transparent; border: 0; color: inherit; }
    .mermaid svg { max-width: 100%; height: auto; }
    .mermaid:not([data-processed]) { font-family: var(--mono); font-size: var(--fs-sm); white-space: pre; overflow-x: auto; background: var(--surface-2); border: 1px dashed var(--line-strong); border-radius: var(--radius); padding: var(--s-6); color: var(--muted); }
    /* shipped diagram: inline SVG in a scroll wrapper, mermaid/source kept in an adjacent <details>.
       The wrapper's overflow-x contains a too-wide diagram to its own scrollbar instead of the page. */
    figure.diagram { margin: var(--s-7) 0; }
    .diagram-scroll { overflow-x: auto; }
    .diagram-scroll svg { max-width: 100%; height: auto; display: block; margin: 0 auto; }
    .diagram-src { margin-top: var(--s-4); }
    .diagram-src summary { cursor: pointer; color: var(--muted); font-size: var(--fs-sm); }
    .diagram-src pre { white-space: pre; overflow-x: auto; }
    .needs-verification { display: inline-block; font-family: var(--mono); padding: 2px 8px; border-radius: var(--radius-sm); font-size: var(--fs-cap); font-weight: 700; background: var(--warn-bg); color: var(--warn); border: 1px solid var(--warn-line); }
    /* responsive overrides for components live next to the component (in _EXTRA_SCAFFOLD_STYLE) */
    @media (max-width: 820px) {
      .grid-cols-2, .grid-2, .grid-3 { grid-template-columns: 1fr; }
      nav.toc ol { columns: 1; }
      table { display: block; overflow-x: auto; }
    }
""".strip()

_MERMAID_SCRIPT = """
  <script type="module">
    /* Self-contained by default: fetch Mermaid from the CDN ONLY if this page actually has a
       diagram. A diagram-free artifact makes ZERO network calls and renders fully offline; add
       a <div class="mermaid"> later and it still renders (the guard checks the DOM at load). */
    if (document.querySelector(".mermaid")) {
      const { default: mermaid } = await import("https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs");
      /* Pick the palette at load from the resolved theme (data-theme, else the OS preference).
         Diagrams render to static SVG, so this matches the page on load; a mid-session toggle
         re-themes them on the next reload. Keep both sets in sync with the :root light/dark tokens. */
      const _root = document.documentElement;
      const _dark = _root.dataset.theme ? _root.dataset.theme === "dark"
                                        : window.matchMedia("(prefers-color-scheme: dark)").matches;
      const _lightVars = { primaryColor: "#eef5fb", primaryBorderColor: "#b9d5ec", primaryTextColor: "#172033", lineColor: "#5a6577", fontFamily: "inherit", fontSize: "14px" };
      const _darkVars = { primaryColor: "#152740", primaryBorderColor: "#2c4a6b", primaryTextColor: "#e8edf5", lineColor: "#96a2b5", fontFamily: "inherit", fontSize: "14px" };
      mermaid.initialize({ startOnLoad: false, securityLevel: "loose", theme: "base",
        themeVariables: _dark ? _darkVars : _lightVars });
      await mermaid.run();   /* module scripts defer, so the DOM is parsed; run() renders every .mermaid once */
    }
  </script>
""".strip()

_LAYOUT_AUDIT = """
  <div id="layout-audit" hidden role="status">⚠ This artifact overflows horizontally at this width - wrap wide tables / diagrams / <code>pre</code> blocks so they scroll, or they will clip on a phone.</div>
  <script>
    (function () {
      var el = document.getElementById('layout-audit');
      if (!el) return;
      function check() { el.hidden = !(document.documentElement.scrollWidth > window.innerWidth + 2); }
      window.addEventListener('DOMContentLoaded', check);
      window.addEventListener('resize', check);
    })();
  </script>
""".strip()

_EXTRA_SCAFFOLD_STYLE = """
    .meta-ribbon { display:flex; flex-wrap:wrap; gap:var(--s-4) var(--s-9); padding:var(--s-5) var(--s-7); margin:0 0 var(--s-9); background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow-sm); font-size:var(--fs-sm); color:var(--muted); }
    .meta-ribbon span { white-space:normal; overflow-wrap:anywhere; }
    .meta-ribbon strong { color:var(--faint); font-family:var(--mono); font-size:var(--fs-cap); letter-spacing:.1em; text-transform:uppercase; font-weight:600; margin-right:var(--s-2); }
    .read-map { background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:var(--s-5) var(--s-7); margin:0 0 var(--s-9); font-size:var(--fs-sm); color:var(--ink); box-shadow:var(--shadow-sm); }
    .read-map div { margin:var(--s-1) 0; }
    .read-map strong { color:var(--accent); font-family:var(--mono); font-size:var(--fs-cap); letter-spacing:.08em; text-transform:uppercase; margin-right:var(--s-2); }
    .read-map a { color:var(--accent); }
    .provenance { margin-top:var(--s-12); padding-top:var(--s-7); border-top:1px solid var(--line); font-size:var(--fs-sm); color:var(--faint); }
    .provenance code { background:transparent; border:0; color:var(--ink); font-family:var(--mono); }
    .provenance a { color:var(--accent); text-decoration:none; }
    .callout { border:1px solid var(--line); border-left:4px solid var(--muted); background:var(--surface-2); border-radius:var(--radius); padding:var(--s-4) var(--s-6); margin:var(--s-6) 0; }
    .callout > strong:first-child { display:block; margin-bottom:var(--s-1); font-family:var(--mono); font-size:var(--fs-cap); text-transform:uppercase; letter-spacing:.08em; }
    .callout-note { border-left-color:var(--accent); background:var(--accent-bg); }
    .callout-note > strong:first-child { color:var(--accent); }
    .callout-note > strong:first-child::before { content:"📌 "; content:"📌 " / ""; }
    .callout-tip { border-left-color:var(--good); background:var(--good-bg); }
    .callout-tip > strong:first-child { color:var(--good); }
    .callout-tip > strong:first-child::before { content:"💡 "; content:"💡 " / ""; }
    .callout-warning { border-left-color:var(--warn); background:var(--warn-bg); }
    .callout-warning > strong:first-child { color:var(--warn); }
    .callout-warning > strong:first-child::before { content:"⚠️ "; content:"⚠️ " / ""; }
    .callout-important { border-left-color:var(--crit); background:var(--crit-bg); }
    .callout-important > strong:first-child { color:var(--crit); }
    .callout-important > strong:first-child::before { content:"❗ "; content:"❗ " / ""; }
    /* ---- collapsible (appendix lane) ---- */
    details { background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:0 var(--s-6); margin:var(--s-6) 0; }
    summary { cursor:pointer; padding:var(--s-4) 0; font-weight:600; color:var(--accent); }
    summary:hover { color:var(--accent-2); }
    details[open] > summary { border-bottom:1px solid var(--line); margin-bottom:var(--s-4); }
    #layout-audit { position:fixed; left:0; right:0; bottom:0; z-index:9999; margin:0; padding:var(--s-3) var(--s-5); background:var(--warn-bg); color:var(--warn); border-top:1px solid var(--warn-line); font-size:var(--fs-sm); text-align:center; }
    #layout-audit[hidden] { display:none; }
    #layout-audit code { background:var(--surface); }
    .confidence { display:inline-block; font-family:var(--mono); padding:2px 8px; border-radius:var(--radius-sm); font-size:var(--fs-cap); font-weight:700; border:1px solid transparent; }
    .confidence-high { background:var(--good-bg); color:var(--good); border-color:var(--good-line); }
    .confidence-medium { background:var(--accent-bg); color:var(--accent); border-color:var(--accent-line); }
    .confidence-low { background:var(--warn-bg); color:var(--warn); border-color:var(--warn-line); }
    /* components own their measure via grid tracks; the 72ch cap applies to open prose only */
    .keycard p, .card p, .tile p, .metric p, .compare-before p, .compare-after p, .callout p { max-width:none; }
    /* ---- KPI tiles (shared: incident .metrics/.metric inherit these) ---- */
    .tiles, .metrics { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:var(--s-5); margin:var(--s-8) 0; }
    .tile, .metric { position:relative; overflow:hidden; background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:var(--s-7) var(--s-7) var(--s-6); box-shadow:var(--shadow-sm); }
    .tile::before { content:""; position:absolute; inset:0 auto 0 0; width:4px; background:var(--sv,var(--accent)); }
    .tile .n, .metric strong { display:block; font-family:var(--display); font-size:clamp(1.8rem,4vw,2.4rem); font-weight:800; line-height:1; color:var(--sv,var(--ink)); font-variant-numeric:tabular-nums; }
    .tile .k, .metric span { display:block; font-family:var(--mono); font-size:var(--fs-cap); letter-spacing:.12em; text-transform:uppercase; color:var(--muted); font-weight:600; margin-top:var(--s-3); }
    .tile .d { font-size:.8rem; color:var(--faint); margin-top:var(--s-1); }
    .tile.crit{--sv:var(--crit);} .tile.high{--sv:var(--high);} .tile.warn{--sv:var(--warn);} .tile.good{--sv:var(--good);} .tile.info{--sv:var(--accent);} .tile.neutral{--sv:var(--neutral);}
    /* ---- stripe / accent cards ---- */
    .card { background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:var(--s-7) var(--s-8); box-shadow:var(--shadow-sm); }
    .card.tint-info { background:var(--info-bg); border-color:var(--info-line); }
    .card.tint-good { background:var(--good-bg); border-color:var(--good-line); }
    .card.tint-high { background:var(--high-bg); border-color:var(--high-line); }
    .card.tint-crit { background:var(--crit-bg); border-color:var(--crit-line); }
    .stripe { position:relative; padding-left:var(--s-7); }
    .stripe::before { content:""; position:absolute; left:0; top:.35rem; bottom:.35rem; width:3px; border-radius:3px; background:var(--accent); }
    .stripe.crit::before{background:var(--crit);} .stripe.high::before{background:var(--high);} .stripe.warn::before{background:var(--warn);} .stripe.good::before{background:var(--good);}
    /* ---- keycard: big number + prose ---- */
    .keycard { display:grid; grid-template-columns:auto 1fr; gap:var(--s-8); align-items:center; margin:var(--s-9) 0; padding:var(--s-8) var(--s-9); background:var(--surface); border:1px solid var(--line-strong); border-left:4px solid var(--sv,var(--accent)); border-radius:var(--radius); box-shadow:var(--shadow); }
    .keycard .big { font-family:var(--display); font-size:clamp(2.4rem,7vw,3.4rem); font-weight:800; line-height:.95; color:var(--sv,var(--accent)); font-variant-numeric:tabular-nums; }
    .keycard .big small { display:block; margin-top:var(--s-2); font-family:var(--mono); font-size:var(--fs-sm); font-weight:600; letter-spacing:.04em; text-transform:uppercase; color:var(--muted); }
    .keycard p b { color:var(--ink); }
    .keycard.crit{--sv:var(--crit);} .keycard.high{--sv:var(--high);} .keycard.good{--sv:var(--good);} .keycard.info{--sv:var(--accent);}
    /* ---- severity / status chips ---- */
    .chip { display:inline-block; font-family:var(--mono); font-size:var(--fs-cap); font-weight:700; padding:2px 8px; border-radius:var(--radius-sm); letter-spacing:.04em; font-variant-numeric:tabular-nums; border:1px solid transparent; }
    .chip.crit{color:var(--crit);background:var(--crit-bg);border-color:var(--crit-line);}
    .chip.high{color:var(--high);background:var(--high-bg);border-color:var(--high-line);}
    .chip.warn{color:var(--warn);background:var(--warn-bg);border-color:var(--warn-line);}
    .chip.good{color:var(--good);background:var(--good-bg);border-color:var(--good-line);}
    .chip.info{color:var(--accent);background:var(--accent-bg);border-color:var(--accent-line);}
    .chip.neutral{color:var(--muted);background:var(--neutral-bg);border-color:var(--neutral-line);font-weight:600;}
    /* ---- cross-links / chain caption / inline mono ---- */
    .chain { font-family:var(--mono); font-size:.8rem; color:var(--accent); font-weight:600; margin-top:var(--s-4); }
    .crosslink { font-weight:600; }
    .crosslink::before { content:"→ "; color:var(--accent); }
    code.m { font-family:var(--mono); color:var(--muted); background:var(--surface-2); padding:1px 6px; border-radius:var(--radius-sm); }
    /* ---- opt-in sticky nav rail: author wraps {nav}{body} in <div class="railed"> ---- */
    .railed { display:grid; grid-template-columns:220px minmax(0,1fr); gap:clamp(24px,4vw,48px); align-items:start; }
    .railed nav.toc { position:sticky; top:24px; margin:0; }
    .railed nav.toc ol { columns:1; }
    @media (max-width:900px) { .railed { grid-template-columns:1fr; } .railed nav.toc { position:static; } }
    /* component responsive overrides live HERE (after the base rules, in the later-injected _EXTRA) so they win the cascade */
    @media (max-width:820px) {
      .keycard { grid-template-columns:1fr; gap:var(--s-5); }
      .tiles, .metrics { grid-template-columns:1fr 1fr; }
    }
    @media (max-width:460px) { .tiles, .metrics { grid-template-columns:1fr; } }
    /* ---- sparkline: area fill, faint grid, emphasized endpoint ---- */
    .spark { color:var(--accent); overflow:visible; }
    .spark .line { stroke:currentColor; stroke-width:2; fill:none; }
    .spark .fill { fill:currentColor; opacity:.12; }
    .spark .grid { stroke:var(--line); stroke-width:1; }
    .spark .dot { fill:currentColor; }
    .spark.good { color:var(--good); } .spark.warn { color:var(--warn); } .spark.crit { color:var(--crit); }
    /* ---- bar rows / progress meter ---- */
    .bars { display:grid; grid-template-columns:max-content 1fr max-content; gap:var(--s-2) var(--s-4); align-items:center; margin:var(--s-6) 0; }
    .bars dt { font-family:var(--mono); font-size:var(--fs-sm); color:var(--muted); margin:0; }
    /* min-width:0 + wrap: if a plain <dd> paragraph is fed to this progress grid by mistake,
       it wraps and degrades instead of forcing a max-content column and blowing out the page
       (a chip + description definition list belongs in .deflist, not .bars). */
    .bars dd { margin:0; min-width:0; overflow-wrap:anywhere; }
    .bars .val { font-variant-numeric:tabular-nums; font-size:var(--fs-sm); }
    .bars .track, .progress { background:var(--surface-2); border-radius:999px; overflow:hidden; min-width:60px; margin:0; }
    .bars .fill, .progress .fill { display:block; height:12px; border-radius:inherit; background:var(--sv,var(--accent)); width:var(--w,50%); }
    .fill.crit { --sv:var(--crit); } .fill.high { --sv:var(--high); } .fill.warn { --sv:var(--warn); } .fill.good { --sv:var(--good); }
    /* ---- definition list: chip/label + wrapping description (risks, key terms, glossary rows) ----
       Use this, NOT .bars, for a <dl> of label + prose. .bars is a 3-col progress grid whose
       max-content columns never wrap a long <dd>; .deflist is a 2-col grid whose 1fr description
       column wraps and caps at a readable measure. Collapses to one column on narrow screens. */
    .deflist { display:grid; grid-template-columns:max-content 1fr; gap:var(--s-4) var(--s-6); align-items:baseline; margin:var(--s-6) 0; }
    .deflist dt { margin:0; }
    .deflist dd { margin:0; color:var(--ink-2); max-width:72ch; min-width:0; overflow-wrap:anywhere; }
    @media (max-width:560px){ .deflist{ grid-template-columns:1fr; gap:var(--s-2); } .deflist dd{ margin:0 0 var(--s-5); } }
    /* ---- delta: direction glyph is AT-hidden; carry direction in the text (signed value) ---- */
    .delta { font-family:var(--mono); font-size:var(--fs-sm); font-weight:700; font-variant-numeric:tabular-nums; }
    .delta.good { color:var(--good); } .delta.bad { color:var(--crit); } .delta.flat { color:var(--muted); }
    .delta.up::before { content:"▲ "; content:"▲ " / ""; }
    .delta.down::before { content:"▼ "; content:"▼ " / ""; }
    .delta.flat::before { content:"→ "; content:"→ " / ""; }
    /* ---- opt-in button (prototype controls); never restyles bare <button> ---- */
    .btn { font:inherit; padding:var(--s-2) var(--s-6); border:1px solid var(--accent-line); border-radius:var(--radius-sm); background:var(--accent-bg); color:var(--accent-2); font-weight:600; cursor:pointer; }
    .btn:hover { background:var(--accent); color:#fff; }
    /* print lives at the END of the later-injected constant so it wins every cascade tie */
    @media print {
      nav.toc, .read-map, #layout-audit { display: none; }
      .railed { display: block; }
      pre { background: var(--surface-2); color: var(--ink); border: 1px solid var(--line); }
      section.section, table, figure, pre, .callout, .compare-before, .compare-after, .metric, .tile, .card, .keycard, .chip, .confidence, .timeline .event, details { break-inside: avoid; }
      a[href^="http"]::after { content: " (" attr(href) ")"; font-size: .85em; color: var(--muted); }
      .kind, .sev, .callout, .compare-before, .compare-after, .meta-ribbon, .needs-verification, .chip, .tile, .card, .keycard, .stripe, .confidence, .timeline .actor, .pm-summary, .spark, .bars, .progress, .delta { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      details:not([open])::details-content { content-visibility: visible; display: block; }
    }
""".strip()

_INCIDENT_SCAFFOLD_STYLE = """
    .sev { display:inline-block; font-family:var(--mono); padding:3px 10px; border-radius:999px; font-size:var(--fs-cap); font-weight:700; letter-spacing:.04em; font-variant-numeric:tabular-nums; border:1px solid transparent; }
    .sev-1 { background:var(--crit-bg); color:var(--crit); border-color:var(--crit-line); }
    .sev-2 { background:var(--warn-bg); color:var(--warn); border-color:var(--warn-line); }
    .sev-3 { background:var(--accent-bg); color:var(--accent); border-color:var(--accent-line); }
    .sev-4 { background:var(--neutral-bg); color:var(--neutral); border-color:var(--neutral-line); }
    /* .metrics/.metric now inherited from the shared .tiles/.tile in _EXTRA_SCAFFOLD_STYLE */
    .timeline { border-left:3px solid var(--line); padding-left:var(--s-7); margin:var(--s-8) 0; }
    .timeline .event { position:relative; margin-bottom:var(--s-5); }
    .timeline .event::before { content:""; position:absolute; left:calc(-1 * var(--s-7) - 7.5px); top:.4em; width:9px; height:9px; border-radius:50%; background:var(--surface); border:2px solid var(--accent); }
    .timeline .event.crit::before { border-color:var(--crit); } .timeline .event.warn::before { border-color:var(--warn); } .timeline .event.good::before { border-color:var(--good); }
    .timeline .gap { margin:var(--s-6) 0; padding:var(--s-1) 0; color:var(--faint); font-family:var(--mono); font-size:var(--fs-cap); border-top:1px dashed var(--line); }
    .timeline .ts { font-family:var(--mono); color:var(--muted); font-size:var(--fs-sm); }
    .timeline .elapsed { display:inline-block; min-width:42px; color:var(--accent); font-weight:600; font-variant-numeric:tabular-nums; }
    .timeline .actor { display:inline-block; font-family:var(--mono); padding:1px 8px; background:var(--surface-2); border-radius:var(--radius-sm); font-size:var(--fs-cap); color:var(--muted); margin-right:var(--s-2); }
    .timeline .estimated { color:var(--warn); font-size:var(--fs-cap); font-style:italic; }
""".strip()


def _pm_summary_block() -> str:
    return """    <section data-audience="pm" class="pm-summary">
      <h2>In plain terms</h2>
      <ul>
        <li><strong>What this does for the user:</strong> Replace with the one-sentence product impact a PM should grasp without engineering context.</li>
        <li><strong>Why it matters:</strong> Replace with the business / user constraint that makes this worth reading.</li>
        <li><strong>What's being asked:</strong> Replace with the decision, approval, or review action the reader should take.</li>
      </ul>
    </section>"""


def _nav_block(items: list[tuple[str, str]]) -> str:
    rendered = "\n".join(f'        <li><a href="#{anchor}">{label}</a></li>' for anchor, label in items)
    return f"""    <nav class="toc" aria-label="On this page">
      <strong>On this page</strong>
      <ol>
{rendered}
      </ol>
    </nav>"""


def _kind_body(kind: str) -> tuple[list[tuple[str, str]], str]:
    """Return (nav_items, body_html) for the given kind."""
    if kind == "plan":
        nav = [("outcome", "Outcome"), ("approach", "Approach"), ("sequence", "Sequence"), ("risks", "Risks"), ("rollback", "Rollback")]
        body = """    <section id="outcome" class="section">
      <h2>Outcome</h2>
      <p>State in one paragraph what is true after this plan lands. Include user-visible behavior, not implementation detail.</p>
    </section>
    <section id="approach" class="section">
      <h2>Approach</h2>
      <p>How we get there. Add a structural diagram if the approach moves boundaries.</p>
      <div class="mermaid">
flowchart LR
  A[Starting state] --> B[Step] --> C[Outcome]
      </div>
    </section>
    <section id="sequence" class="section">
      <h2>Sequence</h2>
      <div class="table-scroll" role="region" aria-label="Plan sequence" tabindex="0">
      <table>
        <thead><tr><th>#</th><th>Step</th><th>Owner</th><th>Done when</th></tr></thead>
        <tbody>
          <tr><td>1</td><td>First action</td><td>tbd</td><td>Acceptance signal</td></tr>
        </tbody>
      </table>
      </div>
    </section>
    <section id="risks" class="section">
      <h2>Risks</h2>
      <ul><li>Risk and its mitigation</li></ul>
    </section>
    <section id="rollback" class="section">
      <h2>Rollback</h2>
      <p>What we do if it goes wrong. Be specific about which signal triggers rollback.</p>
    </section>"""
    elif kind == "review":
        nav = [("verdict", "Verdict"), ("strengths", "Strengths"), ("concerns", "Concerns"), ("required", "Required changes"), ("optional", "Optional changes"), ("re-entry", "Re-entry context")]
        body = """    <section id="verdict" class="section">
      <h2>Verdict</h2>
      <p>One-line summary: approve / request changes / block. Add the reasoning in the next sentence.</p>
    </section>
    <section id="strengths" class="section">
      <h2>Strengths</h2>
      <ul><li>What this work does well</li></ul>
    </section>
    <section id="concerns" class="section">
      <h2>Concerns</h2>
      <p>Issues that need attention. If a concern proposes a structural change, add a Before / after section here showing what would shift.</p>
    </section>
    <section id="required" class="section">
      <h2>Required changes</h2>
      <ul><li>Change that must land before merge</li></ul>
    </section>
    <section id="optional" class="section">
      <h2>Optional changes</h2>
      <ul><li>Nice-to-have that can land later</li></ul>
    </section>
    <section id="re-entry" class="section">
      <h2>Re-entry context</h2>
      <p>What a returning reader (or agent) must hold in their head to pick this up later.</p>
      <ul>
        <li><strong>Invariant:</strong> what must stay true.</li>
        <li><strong>Non-obvious coupling:</strong> X depends on Y in a way that is not visible locally.</li>
        <li><strong>Don't forget:</strong> the easy-to-miss step.</li>
      </ul>
    </section>"""
    elif kind == "architecture":
        nav = [("context", "Context"), ("before-after", "Before / after"), ("recommendation", "Recommendation"), ("sequence", "Sequence"), ("open-questions", "Open questions"), ("re-entry", "Re-entry context")]
        body = """    <section id="context" class="section">
      <h2>Context</h2>
      <p>The friction this addresses, in plain product terms first, then the technical shape.</p>
    </section>
    <section id="before-after" class="section">
      <h2>Before / after</h2>
      <p>How the shape changes.</p>
      <div class="grid-cols-2">
        <div class="compare-before">
          <strong>Before</strong>
          <div class="mermaid">
flowchart TB
  A[Current shape] --> B[Friction point]
          </div>
        </div>
        <div class="compare-after">
          <strong>After</strong>
          <div class="mermaid">
flowchart TB
  C[Proposed shape] --> D[Resolved]
          </div>
        </div>
      </div>
    </section>
    <section id="recommendation" class="section">
      <h2>Recommendation</h2>
      <p>The proposed change and the seam it lives at.</p>
    </section>
    <section id="sequence" class="section">
      <h2>Sequence</h2>
      <p>Stages of rollout. Smallest reversible step first.</p>
    </section>
    <section id="open-questions" class="section">
      <h2>Open questions</h2>
      <ul><li>What's still uncertain and who can answer</li></ul>
    </section>
    <section id="re-entry" class="section">
      <h2>Re-entry context</h2>
      <p>What a returning reader (or agent) must hold in their head to pick this up later: invariants, non-obvious coupling, and the easy-to-miss step.</p>
      <ul>
        <li><strong>Invariant:</strong> what must stay true.</li>
        <li><strong>Non-obvious coupling:</strong> X depends on Y in a way that is not visible locally.</li>
        <li><strong>Don't forget:</strong> the easy-to-miss step.</li>
      </ul>
    </section>"""
    elif kind == "understanding":
        nav = [("what-it-is", "What it is"), ("how-it-works", "How it works"), ("gotchas", "Gotchas"), ("where-to-dig", "Where to dig")]
        body = """    <section id="what-it-is" class="section">
      <h2>What this thing is</h2>
      <p>Plain definition. One sentence a new hire could repeat.</p>
    </section>
    <section id="how-it-works" class="section">
      <h2>How it works</h2>
      <p>Structural explanation with a diagram.</p>
      <div class="mermaid">
flowchart LR
  A[Entry point] --> B[Core] --> C[Output]
      </div>
    </section>
    <section id="gotchas" class="section">
      <h2>Gotchas</h2>
      <ul><li>Surprising behavior or hidden constraint</li></ul>
    </section>
    <section id="where-to-dig" class="section">
      <h2>Where to dig</h2>
      <ul><li><code>path/to/file.py</code> - what to look for</li></ul>
    </section>"""
    elif kind == "research":
        nav = [("question", "Question"), ("method", "Method"), ("findings", "Findings"), ("synthesis", "Synthesis"), ("open", "Open threads")]
        body = """    <section id="question" class="section">
      <h2>Question</h2>
      <p>The research question, stated narrowly enough to answer.</p>
    </section>
    <section id="method" class="section">
      <h2>Method</h2>
      <p>What we did. Sources, queries, codebases inspected.</p>
    </section>
    <section id="findings" class="section">
      <h2>Findings</h2>
      <div class="table-scroll" role="region" aria-label="Research findings" tabindex="0">
      <table>
        <thead><tr><th>Source</th><th>Finding</th><th>Confidence</th></tr></thead>
        <tbody>
          <tr><td>source</td><td>observation</td><td>high / med / low</td></tr>
        </tbody>
      </table>
      </div>
    </section>
    <section id="synthesis" class="section">
      <h2>Synthesis</h2>
      <p>What it means for the work we're shaping.</p>
    </section>
    <section id="open" class="section">
      <h2>Open threads</h2>
      <ul><li>Questions the research did not close</li></ul>
    </section>"""
    elif kind == "decision":
        nav = [("decision", "Decision"), ("context", "Context"), ("options", "Current vs proposed"), ("consequences", "Consequences"), ("reversibility", "Reversibility")]
        body = """    <section id="decision" class="section">
      <h2>Decision</h2>
      <p><strong>In the context of</strong> &lt;situation&gt;, <strong>facing</strong> &lt;forcing function&gt;, <strong>we decided</strong> &lt;option&gt; <strong>to achieve</strong> &lt;benefit&gt;, <strong>accepting</strong> &lt;trade-off&gt;.</p>
    </section>
    <section id="context" class="section">
      <h2>Context</h2>
      <p>Background a PM and an engineer both need.</p>
    </section>
    <section id="options" class="section">
      <h2>Current vs proposed</h2>
      <div class="table-scroll" role="region" aria-label="Current vs proposed comparison" tabindex="0">
      <table>
        <thead><tr><th>Aspect</th><th>Current</th><th>Proposed</th></tr></thead>
        <tbody>
          <tr><td>Shape</td><td>How things work today</td><td>What changes</td></tr>
          <tr><td>Risk</td><td>Today's failure modes</td><td>New trade-offs</td></tr>
        </tbody>
      </table>
      </div>
    </section>
    <section id="consequences" class="section">
      <h2>Consequences</h2>
      <ul>
        <li><strong>Positive:</strong> what gets better</li>
        <li><strong>Neutral:</strong> what shifts without net cost</li>
        <li><strong>Negative:</strong> what gets harder</li>
      </ul>
    </section>
    <section id="reversibility" class="section">
      <h2>Reversibility</h2>
      <p>How costly to undo if we are wrong.</p>
    </section>"""
    elif kind == "prototype":
        nav = [("goal", "Goal"), ("current-vs-target", "Current vs target"), ("mocked", "What's mocked"), ("real", "What's real"), ("try-it", "Try it")]
        body = """    <section id="goal" class="section">
      <h2>Goal</h2>
      <p>What this prototype is meant to teach us.</p>
    </section>
    <section id="current-vs-target" class="section">
      <h2>Current vs target</h2>
      <p>What this prototype mocks, and the production shape it points at.</p>
      <div class="mermaid">
flowchart LR
  A[Current production] --> B[Prototype shortcut] --> C[Target production]
      </div>
    </section>
    <section id="mocked" class="section">
      <h2>What's mocked</h2>
      <ul><li>Component / data / interaction faked for the prototype</li></ul>
    </section>
    <section id="real" class="section">
      <h2>What's real</h2>
      <ul><li>Component touched for real and worth keeping</li></ul>
    </section>
    <section id="try-it" class="section">
      <h2>Try it</h2>
      <p>How to run the prototype, what to look for, what counts as a positive signal.</p>
    </section>"""
    elif kind == "status":
        nav = [("where-we-are", "Where we are"), ("changes", "Recent changes"), ("blockers", "Blockers"), ("next", "Next")]
        body = """    <section id="where-we-are" class="section">
      <h2>Where we are</h2>
      <div class="tiles">
        <div class="tile good"><span class="n">3</span><span class="k">On track</span></div>
        <div class="tile warn"><span class="n">1</span><span class="k">At risk</span></div>
        <div class="tile crit"><span class="n">1</span><span class="k">Blocked</span></div>
      </div>
      <div class="table-scroll" role="region" aria-label="Workstream status" tabindex="0">
      <table>
        <thead><tr><th>Workstream</th><th>Status</th><th>Owner</th><th>ETA</th></tr></thead>
        <tbody>
          <tr><td>name</td><td><span class="chip good">ON TRACK</span></td><td>owner</td><td>date</td></tr>
        </tbody>
      </table>
      </div>
    </section>
    <section id="changes" class="section">
      <h2>Recent changes</h2>
      <ul><li>What landed since the last update</li></ul>
    </section>
    <section id="blockers" class="section">
      <h2>Blockers</h2>
      <ul><li>What's stuck, what unsticks it</li></ul>
    </section>
    <section id="next" class="section">
      <h2>Next</h2>
      <ul><li>What we are doing this week</li></ul>
    </section>"""
    elif kind == "incident":
        nav = [
            ("summary", "Public summary"),
            ("timeline", "Timeline"),
            ("impact", "Impact"),
            ("root-cause", "Root cause"),
            ("actions", "Corrective actions"),
            ("lessons", "Lessons learned"),
        ]
        body = """    <section id="summary" class="section">
      <h2>Public summary</h2>
      <p>Two to three sentences any customer or stakeholder can read. State what happened, who was affected, and what was done. Avoid blame; describe systems and behaviors. (Pattern: GitHub transparency reports + AWS PES.)</p>
    </section>
    <section id="timeline" class="section">
      <h2>Timeline</h2>
      <p>Fact-only chronology. Timestamps in UTC; elapsed offset from first detected impact. Mark estimated timestamps with <em class="estimated">(estimated)</em>. (Pattern: Google SRE + PagerDuty.)</p>
      <div class="timeline">
        <div class="event">
          <p class="ts"><strong>14:00:00</strong> &middot; <span class="elapsed">+0m</span> <span class="actor">monitoring</span> First impact: error rate climbs past threshold.</p>
        </div>
        <div class="event">
          <p class="ts"><strong>14:04:00</strong> &middot; <span class="elapsed">+4m</span> <span class="actor">on-call</span> Page received; investigation begins.</p>
        </div>
        <div class="event">
          <p class="ts"><strong>14:18:00</strong> &middot; <span class="elapsed">+18m</span> <span class="actor">responder</span> Mitigation applied; error rate falling.</p>
        </div>
        <div class="event">
          <p class="ts"><strong>14:35:00</strong> &middot; <span class="elapsed">+35m</span> <span class="actor">incident-commander</span> All clear; incident closed.</p>
        </div>
      </div>
    </section>
    <section id="impact" class="section">
      <h2>Impact &amp; metrics</h2>
      <div class="metrics">
        <div class="metric"><strong>SEV-2</strong><span>Severity</span></div>
        <div class="metric"><strong>4m</strong><span>MTTD</span></div>
        <div class="metric"><strong>18m</strong><span>MTTC (mitigation)</span></div>
        <div class="metric"><strong>35m</strong><span>MTTR (full recovery)</span></div>
      </div>
      <p>Describe customer impact in plain terms first, then internal metrics. Replace placeholder values with measured numbers.</p>
    </section>
    <section id="root-cause" class="section">
      <h2>Root cause &amp; contributing factors</h2>
      <p>Systemic causes only. Avoid naming individuals. Use Five Whys or equivalent. Collapse deeper RCA below.</p>
      <details><summary>Deeper RCA (logs, dashboards)</summary><p>Link to the raw evidence rather than embedding it.</p></details>
    </section>
    <section id="actions" class="section">
      <h2>Corrective actions</h2>
      <div class="table-scroll" role="region" aria-label="Corrective actions" tabindex="0">
      <table>
        <thead><tr><th>#</th><th>Action</th><th>Type</th><th>Owner</th><th>Due</th><th>Status</th></tr></thead>
        <tbody>
          <tr><td>1</td><td>Add the missing alert</td><td>prevent</td><td>tbd</td><td>2026-06-08</td><td>TODO</td></tr>
        </tbody>
      </table>
      </div>
    </section>
    <section id="lessons" class="section">
      <h2>Lessons learned</h2>
      <ul><li>What went well: rapid mitigation thanks to runbook.</li><li>What did not: detection delayed by 4m due to missing alert.</li></ul>
    </section>"""
    else:
        nav = [("body", "Body")]
        body = """    <section id="body" class="section">
      <h2>Body</h2>
      <p>Replace with the artifact content.</p>
    </section>"""
    return nav, body


def _meta_ribbon(kind: str, date: str, escaped_source: str) -> str:
    # `escaped_source` is already HTML-escaped by the caller (render_artifact).
    if kind == "incident":
        return f"""    <div class="meta-ribbon" data-meta-ribbon="true" aria-label="Artifact metadata">
      <span><strong>Kind</strong> incident</span>
      <span><strong>Severity</strong> <span class="sev sev-2">SEV-2</span></span>
      <span><strong>Incident date</strong> {date}</span>
      <span><strong>Resolved</strong> &lt;time UTC&gt;</span>
      <span><strong>Owner</strong> &lt;name&gt;</span>
      <span><strong>Status</strong> Draft</span>
      <span><strong>Read time</strong> ~6 min</span>
    </div>"""
    return f"""    <div class="meta-ribbon" data-meta-ribbon="true" aria-label="Artifact metadata">
      <span><strong>Kind</strong> {kind}</span>
      <span><strong>Created</strong> {date}</span>
      <span><strong>Owner</strong> &lt;name&gt;</span>
      <span><strong>Status</strong> Draft</span>
      <span><strong>Read time</strong> ~5 min</span>
      <span><strong>Source</strong> {escaped_source}</span>
    </div>"""


def _read_map_block(nav_items: list[tuple[str, str]]) -> str:
    if len(nav_items) < 3:
        return ""
    quick_targets = nav_items[:1] + nav_items[-1:]
    quick_links = " &middot; ".join(f'<a href="#{a}">{l}</a>' for a, l in quick_targets)
    return f"""    <aside class="read-map" aria-label="Reading map">
      <div><strong>Quick read:</strong> {quick_links}</div>
      <div><strong>Full read:</strong> All sections</div>
    </aside>"""


def _provenance_footer(kind: str, date: str, escaped_source: str, source: str) -> str:
    # `escaped_source` is already HTML-escaped by the caller (render_artifact).
    payload = {
        "@context": "https://schema.org/",
        "@type": "CreativeWork",
        "@id": f"urn:human-html:{date}:{kind}:{slugify(source)[:72]}",
        "additionalType": "ai-generated-artifact",
        "artifactKind": kind,
        "dateCreated": date,
        "creator": {
            "@type": "SoftwareApplication",
            "name": "<model-id>",
            "softwareVersion": "<version>",
        },
        "promptHash": "<sha256 of prompt; or replace with full prompt if non-sensitive>",
        "reviewer": "<human reviewer or role>",
        "source": source,
    }
    provenance_json = "\n".join(
        f"        {line}"
        for line in json.dumps(payload, indent=2).replace("</", "<\\/").splitlines()
    )
    return f"""    <footer class="provenance" data-provenance="true">
      <p class="provenance-line">
        Generated by <code>&lt;model&gt;</code> on {date} &middot;
        reviewed by <code>&lt;reviewer&gt;</code> &middot;
        source: {escaped_source}
      </p>
      <script type="application/ld+json" id="provenance">
{provenance_json}
      </script>
    </footer>"""


def render_artifact(title: str, kind: str, date: str, source: str) -> str:
    escaped_title = html.escape(title)
    escaped_source = html.escape(source)
    nav_items, body = _kind_body(kind)
    pm = _pm_summary_block()
    nav = _nav_block(nav_items)
    ribbon = _meta_ribbon(kind, date, escaped_source)
    read_map = _read_map_block(nav_items)
    provenance = _provenance_footer(kind, date, escaped_source, source)
    read_time = "6 min" if kind == "incident" else "5 min"
    extra_style = _EXTRA_SCAFFOLD_STYLE
    if kind == "incident":
        extra_style = f"{extra_style}\n{_INCIDENT_SCAFFOLD_STYLE}"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="artifact-kind" content="{kind}">
  <meta name="artifact-audience" content="human">
  <meta name="artifact-created" content="{date}">
  <meta name="artifact-source" content="{escaped_source}">
  <meta name="artifact-read-time" content="{read_time}">
  <!-- Gallery card text. Leave empty to auto-derive from the PM-summary; fill for a sharper one-liner. -->
  <meta name="artifact-summary" content="">
  <meta name="artifact-keywords" content="">
  <title>{escaped_title}</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ctext y='13' font-size='13'%3E{_KIND_FAVICON.get(kind, '📄')}%3C/text%3E%3C/svg%3E">
{_THEME_INIT}
  <style>
{_SCAFFOLD_STYLE}
{_THEME_TOGGLE_STYLE}
{_dark_scheme_css(_SCAFFOLD_DARK_TOKENS)}
{extra_style}
  </style>
{_MERMAID_SCRIPT}
</head>
<body data-human-html-artifact="true">
{_THEME_TOGGLE_BUTTON}
  <main>
    <header>
      <p class="eyebrow">{kind} &middot; {date}</p>
      <h1>{escaped_title}</h1>
    </header>
{ribbon}
{pm}
{read_map}
{nav}
{body}
{provenance}
  </main>
{_LAYOUT_AUDIT}
{_THEME_TOGGLE_SCRIPT}
</body>
</html>
"""


WORKSPACE_README = """# Human HTML Artifacts

## What lives here

This directory holds the HTML pages your team actually opens to review work.
Plans before they get built. Code reviews before they get merged. Architecture
explainers when someone new is trying to understand a system. Status snapshots
when a stakeholder asks "where are we." Decision aids when there is a real
choice to make.

If the artifact is meant for a human to read and act on, it lives here as
a single self-contained `.html` file. Open one in a browser, share the path,
print to PDF, archive it; it is portable and it is legible.

Agent scratch notes, ticket drafts, durable references, and meeting transcripts
stay as Markdown elsewhere in the repo. Those are the agent's memory layer.
This directory is the human's review layer.

## Naming pattern

```text
YYYY-MM-DD-kind-slug.html
```

Nested portable collections under `docs/human-html/<collection>/` may use short
filenames such as `index.html` or `flow-overview.html`. They are still checked
recursively for required metadata, the human body marker, and local links.

Allowed kinds:

```text
plan review architecture understanding research decision prototype status incident
```

## Commands

The script resolves the workspace root automatically by walking up from your
current directory. `<skill-dir>` is wherever your agent installed this skill
(e.g. `~/.claude/skills/human-html` for Claude Code, `~/.agents/skills/human-html`
for Codex):

```bash
python3 <skill-dir>/human_html_artifacts.py new plan "Title to review"
python3 <skill-dir>/human_html_artifacts.py check
python3 <skill-dir>/human_html_artifacts.py index
```

The `new` command refreshes `index.html` after creating an artifact. The
autoindex hook also regenerates `index.html` after direct edits to HTML files in
this directory.

## Canonical source

Skill: this skill's `SKILL.md`. Updates to the script, hooks,
or contract land there and propagate to every workspace that has wired the
hooks.
"""


def cmd_init(args: argparse.Namespace) -> None:
    """Initialise docs/human-html/ in the selected workspace root."""
    root = Path(args.root).resolve() if args.root else resolve_create_root()
    adir = artifact_dir(root)
    if adir.exists() and not args.force:
        raise SystemExit(
            f"{adir} already exists; pass --force to overwrite README and reset index"
        )
    adir.mkdir(parents=True, exist_ok=True)
    readme = adir / "README.md"
    if not readme.exists() or args.force:
        readme.write_text(WORKSPACE_README, encoding="utf-8")
        print(f"created {readme.relative_to(root)}")
    glossary_target = adir / "GLOSSARY.md"
    glossary_template = Path(__file__).resolve().parent / "templates" / "GLOSSARY.md"
    if not glossary_target.exists() and glossary_template.exists():
        glossary_target.write_text(glossary_template.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"created {glossary_target.relative_to(root)}")
    write_index(root)
    print(f"initialised human-html harness at {adir.relative_to(root)}")


def cmd_new(args: argparse.Namespace) -> None:
    root = resolve_create_root()
    adir = artifact_dir(root)
    adir.mkdir(parents=True, exist_ok=True)
    date = args.date or dt.date.today().isoformat()
    try:
        dt.date.fromisoformat(date)
    except ValueError as exc:
        raise SystemExit(f"invalid --date value: {date}") from exc
    slug = slugify(args.slug or args.title)
    path = adir / f"{date}-{args.kind}-{slug}.html"
    if path.exists() and not args.force:
        raise SystemExit(f"{path.relative_to(root)} already exists, pass --force to overwrite")
    path.write_text(render_artifact(args.title, args.kind, date, args.source), encoding="utf-8")
    print(f"created {path.relative_to(root)}")
    write_index(root)


def gather_content_findings(
    root: Path, artifacts: list[Artifact]
) -> tuple[list[str], list[str]]:
    """Run the post-cutoff content-shape contract across every in-force artifact."""
    errors: list[str] = []
    warnings: list[str] = []
    for artifact in artifacts:
        rel = artifact.path.relative_to(root)
        try:
            content = artifact.path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            warnings.append(f"{rel}: unreadable during content check ({exc.__class__.__name__}); skipped")
            continue
        art_errs, art_warns = content_shape_violations(
            rel, content, artifact.date, root, artifact.kind
        )
        errors.extend(art_errs)
        warnings.extend(art_warns)
    return errors, warnings


_FINDING_RULE_RE = re.compile(r"\s*\[rule=([^\]]+)\]\s*$")


def _structure_finding(text: str, severity: str) -> dict[str, str]:
    """Parse a '<file>: <message> [rule=<id>]' finding into a JSON-friendly record."""
    code = "file-contract"
    match = _FINDING_RULE_RE.search(text)
    body = text
    if match:
        code = match.group(1)
        body = text[: match.start()].rstrip()
    file, sep, message = body.partition(": ")
    if not sep:
        file, message = "", body
    return {"severity": severity, "file": file, "code": code, "message": message}


def cmd_check(fmt: str = "text") -> int:
    root = resolve_root()
    artifacts, errors = read_artifacts(root)
    errors.extend(root_html_errors(root))
    content_errors, content_warnings = gather_content_findings(root, artifacts)
    errors.extend(content_errors)
    grandfathered = sum(1 for a in artifacts if not _artifact_in_force(a.date))
    in_force = len(artifacts) - grandfathered

    if fmt == "json":
        payload = {
            "ok": not errors,
            "artifacts": len(artifacts),
            "in_force": in_force,
            "grandfathered": grandfathered,
            "errors": [_structure_finding(e, "error") for e in errors],
            "warnings": [_structure_finding(w, "warning") for w in content_warnings],
        }
        print(json.dumps(payload, indent=2))
        return 1 if errors else 0

    for warning in content_warnings:
        print(f"WARN: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    msg = f"ok: {len(artifacts)} human HTML artifact(s) validated"
    if grandfathered:
        msg += f" ({in_force} held to content contract, {grandfathered} grandfathered pre-{RULES_EFFECTIVE_DATE})"
    if content_warnings:
        msg += f"; {len(content_warnings)} warning(s)"
    print(msg)
    return 0


def cmd_index() -> None:
    write_index(resolve_root())


def _excalidraw_canonical(home: Path) -> Path | None:
    """The real excalidraw-mcp skill directory on disk (resolving symlinks), or None."""
    for p in (home / ".agents/skills/excalidraw-mcp", home / ".claude/skills/excalidraw-mcp"):
        if p.exists():
            return p.resolve()
    return None


def _client_skill_dirs(home: Path) -> list[Path]:
    """Per-client skill directories human-html may be surfaced through."""
    return [home / ".claude/skills", home / ".codex/skills", home / ".cursor/skills"]


def cmd_deps(fix: bool = False) -> int:
    """Report human-html's optional companions (and with --fix, link the
    excalidraw-mcp skill into any client skill dir that is missing it).

    A skill has no package manager (it is a directory under a client's skills/
    dir), and the validator itself needs only the Python stdlib -- so this
    REPORTS status. --fix does the ONE safe automation available: symlink an
    already-on-disk excalidraw-mcp into client dirs that exist but lack it. It
    never clobbers an existing entry, never creates a client dir that is not
    already set up, and cannot configure the Excalidraw MCP server (client config).
    Everything here is optional: human-html is fully usable with none of it.
    """
    import shutil

    home = Path.home()
    print("human-html companions (all OPTIONAL; the validator needs only Python stdlib):")
    print(f"  OK   Python {sys.version.split()[0]} -- validator imports stdlib only; nothing to pip install")

    canonical = _excalidraw_canonical(home)
    if canonical is None:
        print("  opt  excalidraw-mcp skill NOT found on disk -- optional; for hand-drawn <dfn>")
        print("       flow diagrams. Add the skill (clone/copy), then `deps --fix` links it")
        print("       into your client skill dirs.")
    else:
        for cdir in _client_skill_dirs(home):
            if not cdir.is_dir():
                continue  # that client is not set up here; skip it
            client = cdir.parent.name.lstrip(".")  # ".claude" -> "claude"
            link = cdir / "excalidraw-mcp"
            if os.path.lexists(link):
                print(f"  OK   excalidraw-mcp linked for {client} ({link})")
            elif fix:
                link.symlink_to(canonical, target_is_directory=True)
                print(f"  FIX  excalidraw-mcp linked for {client}: {link} -> {canonical}")
            else:
                print(f"  opt  excalidraw-mcp on disk but not linked for {client} -- run `deps --fix`")
    print("       note: excalidraw-mcp also needs the Excalidraw MCP server configured in")
    print("       your MCP client -- that lives in client config and cannot be set up here.")

    if shutil.which("mmdc"):
        print("  OK   mmdc (mermaid CLI) present -- optional, renders mermaid to inline SVG")
    else:
        print("  opt  mmdc (mermaid CLI) not found -- optional; live-CDN mermaid is fine for")
        print("       drafts. For shipped SVG: npm i -g @mermaid-js/mermaid-cli")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialise docs/human-html/ in current dir")
    init_parser.add_argument("--root", help="workspace root (default: CWD)")
    init_parser.add_argument("--force", action="store_true")

    new_parser = subparsers.add_parser("new", help="create a new artifact scaffold")
    new_parser.add_argument("kind", choices=KINDS)
    new_parser.add_argument("title")
    new_parser.add_argument("--slug")
    new_parser.add_argument("--date")
    new_parser.add_argument("--source", default="local")
    new_parser.add_argument("--force", action="store_true")
    new_parser.add_argument(
        "--index",
        action="store_true",
        help="deprecated compatibility flag; new always refreshes index.html",
    )

    subparsers.add_parser("index", help="refresh docs/human-html/index.html + docs-index.json")
    deps_parser = subparsers.add_parser("deps", help="report optional companions (excalidraw-mcp, mmdc) and how to get them")
    deps_parser.add_argument(
        "--fix", action="store_true",
        help="symlink an on-disk excalidraw-mcp into client skill dirs that lack it (never clobbers)",
    )
    check_parser = subparsers.add_parser("check", help="validate artifact names, metadata, and local links")
    check_parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="json emits structured findings (file/code/message) to stdout for agents",
    )

    args = parser.parse_args(argv)
    if args.command == "init":
        cmd_init(args)
        return 0
    if args.command == "new":
        cmd_new(args)
        return 0
    if args.command == "index":
        cmd_index()
        return 0
    if args.command == "deps":
        return cmd_deps(args.fix)
    if args.command == "check":
        return cmd_check(args.format)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
