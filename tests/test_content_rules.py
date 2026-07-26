"""Regression tests for content-contract detection regexes.

Covers the js-content-fallback detector, which for a long time matched only
`.innerHTML =`. Content built with createElement + textContent + appendChild
passed the rule silently -- including in this skill's own
examples/prototype-canonical.html -- so "passes js-content-fallback" was not
evidence of a real no-JS static floor.
"""

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).parents[1]
SCRIPT = REPO / "skills/human-html/human_html_artifacts.py"

_spec = importlib.util.spec_from_file_location("hha", SCRIPT)
assert _spec is not None and _spec.loader is not None, f"cannot load {SCRIPT}"
hha = importlib.util.module_from_spec(_spec)
# Register before exec: the script defines @dataclass types, and dataclasses
# resolves field types via sys.modules[cls.__module__], which is None for a
# module loaded from a spec but never registered.
sys.modules["hha"] = hha
_spec.loader.exec_module(hha)

# Read maps must be depth-based ("Quick read" / "Full read"), never labelled by job
# title. This lives in the test rather than the validator on purpose: the decision was
# to fix the examples, not to add a 16th rule. It guards the shipped examples from
# drifting back without putting another string heuristic into the contract.
_ROLE_READMAP_RE = re.compile(
    r"read-map.{0,800}?<strong>\s*(?:Exec|PM|Product|Engineer|Manager|Dev)\b",
    re.IGNORECASE | re.DOTALL,
)


class JsDomWriteDetectionTest(unittest.TestCase):
    """The rule must fire on DOM *insertion*, never on detached creation."""

    INSERTS = [
        ('el.innerHTML = "<li>x</li>";', "innerHTML assignment"),
        ('el.innerHTML="x";', "innerHTML, no surrounding space"),
        ('el.outerHTML = "<p>x</p>";', "outerHTML assignment"),
        ('el.insertAdjacentHTML("beforeend", h);', "insertAdjacentHTML"),
        ("el.replaceChildren(...nodes);", "replaceChildren"),
        ("listEl.appendChild(li);", "appendChild"),
        ("box.append(a, b);", "append"),
        ("box.prepend(node);", "prepend"),
        ("parent.insertBefore(node, ref);", "insertBefore"),
        ('document.write("<p>x</p>");', "document.write"),
        ('document.writeln("x");', "document.writeln"),
    ]

    # Creating a node attaches nothing to the page. Matching creation would fire
    # on the copy-button pattern in references/patterns.md, which builds its
    # control in JS so that no-JS surfaces never render a dead one.
    NON_INSERTS = [
        ('var li = document.createElement("li");', "detached creation only"),
        ('li.textContent = "Notes field";', "textContent on a detached node"),
        ('el.classList.add("on");', "class toggle"),
        ("el.setAttribute('aria-current', 'true');", "attribute write"),
        ("if (a.innerHTML === b) { }", "innerHTML read via === comparison"),
        ("if (a.innerHTML == b) { }", "innerHTML read via == comparison"),
        ("// Never assign innerHTML with interpolated values.", "prose comment"),
    ]

    def test_fires_on_dom_insertion(self):
        for snippet, why in self.INSERTS:
            with self.subTest(why=why):
                self.assertTrue(
                    hha._JS_DOM_WRITE_RE.search(snippet),
                    f"should flag JS DOM insertion ({why}): {snippet}",
                )

    def test_does_not_fire_without_insertion(self):
        for snippet, why in self.NON_INSERTS:
            with self.subTest(why=why):
                self.assertFalse(
                    hha._JS_DOM_WRITE_RE.search(snippet),
                    f"false positive ({why}): {snippet}",
                )


def _artifact(body: str, *, mode: str = "", kind: str = "plan") -> str:
    """Minimal in-force artifact: passes everything except what a test targets."""
    mode_meta = f'<meta name="artifact-mode" content="{mode}">' if mode else ""
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="artifact-kind" content="{kind}">{mode_meta}
<meta name="artifact-created" content="2026-07-26">
<title>t</title></head>
<body data-human-html-artifact="true"><main>
<div data-meta-ribbon="true">ribbon</div>
<section data-summary="true"><h2>In plain terms</h2><ul><li>What: a thing.</li></ul></section>
{body}
<footer data-provenance="true">provenance</footer>
</main></body></html>"""


class DynamicModeTest(unittest.TestCase):
    """Dynamic mode stands down the three SHAPE rules and nothing else.

    The split exists because the rules were two populations wearing one coat:
    `required-section` encodes "a plan looks like this", `viewport-meta` encodes
    "a human on a phone can read this". Only the first kind is about structure, so
    only the first kind can be relaxed when the author invents the structure.
    """

    # Five h2 sections, no <nav>, no reading guide, no "rollback" heading: enough to
    # trip every shape rule at once.
    LONG_BODY = "\n".join(
        f'<section id="s{i}"><h2>Section {i}</h2><p>Body.</p></section>' for i in range(5)
    )

    def _check(self, mode: str) -> tuple[list[str], list[str]]:
        return hha.content_shape_violations(
            Path("a.html"), _artifact(self.LONG_BODY, mode=mode), "2026-07-26", REPO, "plan"
        )

    def test_standard_mode_blocks_on_nav_and_warns_on_shape(self):
        errors, warnings = self._check("")
        self.assertTrue(
            any("nav-anchors" in e for e in errors), f"nav must block in standard: {errors}"
        )
        self.assertTrue(any("required-section" in w for w in warnings), warnings)
        self.assertTrue(any("read-map" in w for w in warnings), warnings)

    def test_dynamic_mode_downgrades_nav_and_drops_the_skeleton_rules(self):
        errors, warnings = self._check("dynamic")
        self.assertEqual(errors, [], f"dynamic mode must not block on shape: {errors}")
        self.assertTrue(
            any("nav-anchors" in w for w in warnings),
            f"nav should still nudge, just not veto: {warnings}",
        )
        joined = " ".join(warnings)
        self.assertNotIn("required-section", joined)
        self.assertNotIn("read-map", joined)

    def test_dynamic_mode_does_not_relax_reader_protection(self):
        """The floor is the point: relaxing shape must not relax anything else."""
        no_viewport = _artifact("<p>x</p>", mode="dynamic").replace(
            '<meta name="viewport" content="width=device-width, initial-scale=1">', ""
        )
        errors, _ = hha.content_shape_violations(
            Path("a.html"), no_viewport, "2026-07-26", REPO, "plan"
        )
        self.assertTrue(
            any("viewport" in e for e in errors),
            f"viewport-meta must still block in dynamic mode: {errors}",
        )

    def test_summary_block_is_required_in_both_modes(self):
        for mode in ("", "dynamic"):
            with self.subTest(mode=mode or "standard"):
                stripped = re.sub(
                    r'<section data-summary="true">.*?</section>',
                    "",
                    _artifact("<p>x</p>", mode=mode),
                    flags=re.DOTALL,
                )
                errors, _ = hha.content_shape_violations(
                    Path("a.html"), stripped, "2026-07-26", REPO, "plan"
                )
                self.assertTrue(
                    any("summary-first" in e for e in errors),
                    f"answer-first opener must block in {mode or 'standard'}: {errors}",
                )

    def test_unrecognised_mode_warns_instead_of_failing_silently(self):
        """A typo'd mode must not quietly leave the author in standard mode.

        Falling through to the full rule set is the right default, but doing it
        silently means "dyanmic" looks identical to a validator that ignores the flag.
        """
        errors, warnings = hha.content_shape_violations(
            Path("a.html"),
            _artifact(self.LONG_BODY, mode="dyanmic"),
            "2026-07-26",
            REPO,
            "plan",
        )
        self.assertTrue(
            any("artifact-mode" in w for w in warnings),
            f"a typo'd mode must warn: {warnings}",
        )
        # and it must still be held to the full rule set, not half-relaxed
        self.assertTrue(
            any("nav-anchors" in e for e in errors),
            f"an unrecognised mode is standard, so nav must still block: {errors}",
        )

    def test_the_supported_modes_do_not_warn(self):
        for mode in ("", "standard", "dynamic"):
            with self.subTest(mode=mode or "absent"):
                _, warnings = hha.content_shape_violations(
                    Path("a.html"), _artifact("<p>x</p>", mode=mode), "2026-07-26", REPO, "plan"
                )
                self.assertFalse(
                    any("artifact-mode" in w for w in warnings),
                    f"{mode or 'absent'} is valid and must not warn: {warnings}",
                )

    def test_retired_rule_id_still_suppresses(self):
        """Renaming a rule must not invalidate suppressions written against the old ID.

        `pm-summary` became `summary-first`. `_add` matches the emitted ID exactly, so
        without an alias every artifact carrying
        `<!-- human-html-disable: pm-summary -->` turns a passing build into a BLOCKING
        error on upgrade. That is a silent breaking change for installed workspaces.
        """
        for suppressed in ("pm-summary", "summary-first"):
            with self.subTest(rule_id=suppressed):
                art = _artifact(
                    f"<!-- human-html-disable: {suppressed} -->"
                ).replace('<section data-summary="true"><h2>In plain terms</h2>'
                          "<ul><li>What: a thing.</li></ul></section>", "")
                errors, _ = hha.content_shape_violations(
                    Path("a.html"), art, "2026-07-26", REPO, "plan"
                )
                self.assertFalse(
                    any("summary-first" in e for e in errors),
                    f"suppressing {suppressed} must silence summary-first: {errors}",
                )

    def test_an_unsuppressed_missing_summary_still_blocks(self):
        """Guard the guard: the alias must not silence the rule for everyone."""
        art = _artifact("<p>x</p>").replace(
            '<section data-summary="true"><h2>In plain terms</h2>'
            "<ul><li>What: a thing.</li></ul></section>", "")
        errors, _ = hha.content_shape_violations(
            Path("a.html"), art, "2026-07-26", REPO, "plan"
        )
        self.assertTrue(any("summary-first" in e for e in errors), errors)

    def test_mode_written_as_an_attribute_warns(self):
        """The mode is a meta tag. Writing it as an attribute must not fail silently."""
        art = _artifact("<p>x</p>").replace(
            '<body data-human-html-artifact="true">',
            '<body data-human-html-artifact="true" data-artifact-mode="dynamic">',
        )
        _, warnings = hha.content_shape_violations(
            Path("a.html"), art, "2026-07-26", REPO, "plan"
        )
        self.assertTrue(
            any("artifact-mode" in w for w in warnings),
            f"an attribute-form mode must warn that it is not in effect: {warnings}",
        )

    def test_legacy_audience_marker_still_satisfies_the_rule(self):
        """Artifacts written before the rename must keep validating."""
        legacy = _artifact("<p>x</p>").replace(
            '<section data-summary="true">', '<section data-audience="pm">'
        )
        errors, _ = hha.content_shape_violations(
            Path("a.html"), legacy, "2026-07-26", REPO, "plan"
        )
        self.assertFalse(
            any("summary-first" in e for e in errors),
            'pre-rename data-audience="pm" must still count: ' + str(errors),
        )


class NoAudienceSegmentationTest(unittest.TestCase):
    """No artifact names a job title at the reader, in prose OR in markup.

    The read maps were relabelled depth-based for this reason; `data-audience="pm"`
    was the same segmentation one layer down, so it was renamed to
    `data-summary="true"`. This guards both halves from drifting back.
    """

    EXAMPLES = sorted((REPO / "skills/human-html/examples").glob("*.html"))

    def test_examples_do_not_use_the_pre_rename_marker(self):
        offenders = [
            p.name for p in self.EXAMPLES if "data-audience" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [], f'data-audience is retired: {offenders}')

    def test_scaffold_emits_the_renamed_marker(self):
        page = hha.render_artifact("T", "plan", "2026-07-26", "local")
        self.assertIn('data-summary="true"', page)
        self.assertNotIn("data-audience", page)

    def test_dynamic_scaffold_omits_nav_read_map_and_kind_sections(self):
        page = hha.render_artifact("T", "plan", "2026-07-26", "local", "dynamic")
        self.assertIn('<meta name="artifact-mode" content="dynamic">', page)
        self.assertNotIn("<nav", page)
        # the markup, not the string: .read-map lives in the shared scaffold CSS,
        # which is one constant for both modes and correctly stays.
        self.assertNotIn('aria-label="Reading map"', page)
        self.assertNotIn('class="read-map"', page)
        # and it still carries the floor it cannot relax
        self.assertIn('data-summary="true"', page)
        self.assertIn("width=device-width", page)


class SimulateNoJsTest(unittest.TestCase):
    """`render --no-js` rewrites the page the way a JS-disabled browser treats it.

    A Chrome flag would be simpler and none works: `--disable-javascript` is accepted
    and silently ignored (byte-identical screenshot to JS-on and to an invented flag),
    and `--blink-settings=scriptEnabled=false` makes headless Chrome emit nothing at all.
    A flag that quietly does nothing is the worst option, because the render would then
    certify a no-JS floor it never exercised.
    """

    def test_scripts_are_removed(self):
        out = hha.simulate_no_js(
            '<p>keep</p><script>document.title="x";</script><script src="a.js"></script><p>keep2</p>'
        )
        self.assertNotIn("<script", out)
        self.assertIn("keep", out)
        self.assertIn("keep2", out)

    def test_noscript_children_are_unwrapped(self):
        out = hha.simulate_no_js(
            '<div><noscript><style>.a{display:none}</style><p>fallback</p></noscript></div>'
        )
        self.assertNotIn("noscript", out)
        self.assertIn(".a{display:none}", out)
        self.assertIn("fallback", out)

    def test_a_noscript_mentioned_in_a_comment_does_not_eat_the_document(self):
        """The bug this guards cost a whole page.

        `prototype-canonical.html` documents its own floor in a comment that names
        `<noscript>`. That mention is a false opening tag, so a non-greedy unwrap ran from
        the comment to the REAL `</noscript>`, deleting everything between and leaving a
        stray open tag. Comments are stripped first for exactly this reason.
        """
        src = (
            "<div>"
            "<!-- the controls are hidden in no-JS previews (the <noscript> block below) -->"
            "<p id='keepme'>load-bearing content</p>"
            "<noscript><style>.js-only{display:none !important}</style></noscript>"
            "</div>"
        )
        out = hha.simulate_no_js(src)
        self.assertIn("load-bearing content", out, "content between the comment and the real tag was eaten")
        self.assertNotIn("noscript", out, f"a stray noscript tag survived: {out}")
        self.assertIn(".js-only{display:none !important}", out)

    def test_the_real_example_transforms_cleanly(self):
        proto = REPO / "skills/human-html/examples/prototype-canonical.html"
        out = hha.simulate_no_js(proto.read_text(encoding="utf-8"))
        self.assertNotIn("<script", out)
        self.assertNotIn("noscript", out)
        # the pre-rendered floor and the no-JS explanation both survive
        self.assertIn("Customer tier", out)
        self.assertIn("JavaScript is off", out)

    def test_noscript_hide_beats_inline_styles(self):
        """A `display: none` that loses to an inline style is not a floor.

        The `.js-only` controls carry `style="display:flex"`, and an inline declaration
        beats a stylesheet rule, so the plain rule left the slider on screen driving
        nothing. Only rendering with JS off showed it.
        """
        proto = (REPO / "skills/human-html/examples/prototype-canonical.html").read_text(
            encoding="utf-8"
        )
        noscript = re.search(r"<noscript\b.*?</noscript>", proto, re.DOTALL)
        assert noscript is not None, "the example must still ship a <noscript> floor"
        block = noscript.group(0)
        self.assertIn("display: none !important", block)
        inline_display = re.findall(r'class="js-only"[^>]*style="[^"]*display\s*:', proto)
        self.assertTrue(
            inline_display,
            "if no .js-only control carries an inline display any more, !important can go",
        )


class SourceFilesProvenanceTest(unittest.TestCase):
    """The optional `sourceFiles` block, and why only the revision is enforced.

    A files-read list without the revision it was read at cannot answer the question it
    exists for: is this artifact still true about those files? With the revision a reader
    runs `git diff <rev>..HEAD -- <paths>`. Without it the list is decoration.
    """

    def test_absent_block_is_silent(self):
        """Opting out must cost nothing. This is a pattern, not a requirement."""
        self.assertEqual(hha._source_files_warnings(Path("a.html"), {}), [])

    def test_complete_block_is_silent(self):
        obj = {"sourceFiles": {"paths": ["a.ts"], "readAtRevision": "9c2ad10"}}
        self.assertEqual(hha._source_files_warnings(Path("a.html"), obj), [])

    def test_paths_without_a_revision_warn(self):
        obj = {"sourceFiles": {"paths": ["a.ts"]}}
        warnings = hha._source_files_warnings(Path("a.html"), obj)
        self.assertTrue(any("readAtRevision" in w for w in warnings), warnings)

    def test_revision_without_paths_warns(self):
        obj = {"sourceFiles": {"paths": [], "readAtRevision": "9c2ad10"}}
        warnings = hha._source_files_warnings(Path("a.html"), obj)
        self.assertTrue(any("non-empty array" in w for w in warnings), warnings)

    def test_wrong_shape_warns_instead_of_crashing(self):
        for bad in (["a.ts"], "a.ts", 3, None):
            with self.subTest(value=bad):
                warnings = hha._source_files_warnings(Path("a.html"), {"sourceFiles": bad})
                self.assertTrue(warnings, f"{bad!r} should warn")

    def test_an_explicit_null_is_not_the_same_as_omission(self):
        """`"sourceFiles": null` means the author started the block and left it empty."""
        self.assertEqual(hha._source_files_warnings(Path("a.html"), {}), [])
        self.assertTrue(hha._source_files_warnings(Path("a.html"), {"sourceFiles": None}))

    def test_element_types_are_checked_not_just_truthiness(self):
        """The block's only job is to make a `git diff` runnable.

        A numeric revision or a path array of integers passes a truthiness check and
        produces an unusable command, which is the failure this guards.
        """
        bad_paths = [
            ([1, 2, 3], "integers"),
            (["a.ts", ""], "an empty string among real paths"),
            (["   "], "whitespace only"),
            ("a.ts", "a bare string instead of an array"),
        ]
        for paths, why in bad_paths:
            with self.subTest(paths=why):
                warnings = hha._source_files_warnings(
                    Path("a.html"), {"sourceFiles": {"paths": paths, "readAtRevision": "9c2ad10"}}
                )
                self.assertTrue(any("path strings" in w for w in warnings), f"{why}: {warnings}")

        for revision, why in ((12345, "a number"), ("", "empty"), ("  ", "whitespace")):
            with self.subTest(revision=why):
                warnings = hha._source_files_warnings(
                    Path("a.html"), {"sourceFiles": {"paths": ["a.ts"], "readAtRevision": revision}}
                )
                self.assertTrue(
                    any("readAtRevision" in w for w in warnings), f"{why}: {warnings}"
                )

    def test_the_worked_example_agrees_with_its_own_json_ld(self):
        """The visible list and the JSON-LD are one fact written twice.

        The failure mode is editing one and forgetting the other, which leaves a reader
        running a `git diff` over a path set the artifact no longer claims to have read.
        """
        path = REPO / "skills/human-html/examples/understanding-canonical.html"
        text = path.read_text(encoding="utf-8")
        block = re.search(r'<details class="files-read">(.*?)</details>', text, re.DOTALL)
        assert block is not None, "the worked example must keep its files-read block"
        shown = re.findall(r"<li><code>([^<]+)</code></li>", block.group(1))

        script = re.search(
            r'<script type="application/ld\+json" id="provenance">(.*?)</script>',
            text, re.DOTALL,
        )
        assert script is not None
        declared = json.loads(script.group(1))["sourceFiles"]

        self.assertEqual(shown, declared["paths"], "visible list and JSON-LD disagree")
        self.assertIn(f"Files read ({len(shown)})", block.group(1), "summary count is stale")
        self.assertIn(
            declared["readAtRevision"], block.group(1),
            "the revision in the JSON-LD is not the one shown to the reader",
        )


class EveryExampleTest(unittest.TestCase):
    """Rules that hold for every shipped example, dynamic or kind-shaped.

    The canonical tests above glob `*-canonical.html`, which would silently skip the
    dynamic examples. These are the checks that do not care about shape at all, so
    they run over everything in examples/.
    """

    EXAMPLES = sorted((REPO / "skills/human-html/examples").glob("*.html"))
    DYNAMIC = sorted((REPO / "skills/human-html/examples").glob("dynamic-*.html"))

    def test_validator_reports_no_errors_for_any_example(self):
        offenders = []
        for path in self.EXAMPLES:
            text = path.read_text(encoding="utf-8")
            parser = hha.ArtifactHTMLParser()
            parser.feed(text)
            errors, _ = hha.content_shape_violations(
                path, text, "2026-07-26", REPO, parser.meta.get("artifact-kind", "")
            )
            if errors:
                offenders.append((path.name, errors))
        self.assertEqual(offenders, [], f"examples must validate clean: {offenders}")

    def test_no_em_dashes_or_curly_quotes_in_any_example(self):
        """House style, and it is what the em-dash rule warns on."""
        offenders = []
        for path in self.EXAMPLES:
            text = path.read_text(encoding="utf-8")
            # Both directions of each pair: a file carrying only the closing form
            # would otherwise pass, which is exactly how smart quotes arrive.
            hits = [name for char, name in
                    (("—", "em dash"), ("–", "en dash"),
                     ("“", "curly quote (open)"), ("”", "curly quote (close)"),
                     ("‘", "curly apostrophe (open)"), ("’", "curly apostrophe (close)"))
                    if char in text]
            if hits:
                offenders.append((path.name, hits))
        self.assertEqual(offenders, [], f"house style: {offenders}")

    def test_dynamic_examples_exist_and_declare_the_mode(self):
        self.assertGreaterEqual(
            len(self.DYNAMIC), 3, "at least three dynamic examples are shipped"
        )
        for path in self.DYNAMIC:
            with self.subTest(example=path.name):
                self.assertIn(
                    '<meta name="artifact-mode" content="dynamic">',
                    path.read_text(encoding="utf-8"),
                )

    def test_dynamic_examples_do_not_converge_on_one_shape(self):
        """The point of shipping three is that none of them reads as the template.

        If they all landed on the same kind or the same heading set, an author would
        copy the shared shape and dynamic mode would have re-grown a skeleton.
        """
        kinds, headsets = set(), []
        for path in self.DYNAMIC:
            text = path.read_text(encoding="utf-8")
            parser = hha.ArtifactHTMLParser()
            parser.feed(text)
            kinds.add(parser.meta.get("artifact-kind", ""))
            headsets.append(frozenset(h.strip().lower() for h in parser.h2_headings))
        self.assertGreaterEqual(len(kinds), 3, f"dynamic examples share a kind: {kinds}")
        for i, a in enumerate(headsets):
            for b in headsets[i + 1:]:
                shared = a & b
                # "in plain terms" is the summary block, which every artifact has.
                shared -= {"in plain terms"}
                self.assertLessEqual(
                    len(shared), 1,
                    f"two dynamic examples share headings, so one is becoming a template: {shared}",
                )


class CanonicalExampleContractTest(unittest.TestCase):
    """The shipped examples are what agents copy, so they must obey the rules.

    SKILL.md tells agents to read the canonical example for a kind before
    writing a new artifact of that kind, which makes an example that violates
    the contract worse than a plain docs bug: the example wins.
    """

    EXAMPLES = sorted((REPO / "skills/human-html/examples").glob("*-canonical.html"))

    def test_examples_exist(self):
        self.assertTrue(self.EXAMPLES, "no canonical examples found")

    def test_no_role_based_read_maps(self):
        """SKILL.md: reading guides are depth-based, never labelled by job title."""
        offenders = []
        for path in self.EXAMPLES:
            text = path.read_text(encoding="utf-8")
            if _ROLE_READMAP_RE.search(text):
                offenders.append(path.name)
        self.assertEqual(
            offenders, [], f"role-based read maps (banned by SKILL.md): {offenders}"
        )

    def test_js_built_content_has_noscript_floor(self):
        """An example that inserts DOM in JS must ship a no-JS fallback."""
        offenders = []
        for path in self.EXAMPLES:
            text = path.read_text(encoding="utf-8")
            if hha._JS_DOM_WRITE_RE.search(text) and not hha._NOSCRIPT_RE.search(text):
                offenders.append(path.name)
        self.assertEqual(
            offenders, [], f"JS-inserted DOM with no <noscript> floor: {offenders}"
        )

    def test_mermaid_examples_carry_the_label_clip_fix(self):
        """Any example with a live mermaid diagram needs both halves of the clip fix.

        The page's kerning / ligatures widen the final SVG text past mermaid's own
        measurement, so node labels get cut off at the right edge. The scaffold got
        this fix; the examples were not backfilled, so every canonical diagram shipped
        with clipped labels. Both halves are required: the CSS that neutralizes text
        shaping inside .mermaid, and flowchart padding in the init config.
        """
        missing_css, missing_padding = [], []
        for path in self.EXAMPLES:
            text = path.read_text(encoding="utf-8")
            if 'class="mermaid"' not in text:
                continue
            if "foreignObject { overflow: visible" not in text:
                missing_css.append(path.name)
            if "flowchart: { htmlLabels: true, padding:" not in text:
                missing_padding.append(path.name)
        self.assertEqual(missing_css, [], f"missing .mermaid clip CSS: {missing_css}")
        self.assertEqual(
            missing_padding, [], f"missing flowchart padding: {missing_padding}"
        )


if __name__ == "__main__":
    unittest.main()
