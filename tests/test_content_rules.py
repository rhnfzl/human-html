"""Regression tests for content-contract detection regexes.

Covers the js-content-fallback detector, which for a long time matched only
`.innerHTML =`. Content built with createElement + textContent + appendChild
passed the rule silently -- including in this skill's own
examples/prototype-canonical.html -- so "passes js-content-fallback" was not
evidence of a real no-JS static floor.
"""

import fnmatch
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

f_unowned = hha.find_unowned_judgment_headings

# Read maps must be depth-based ("Quick read" / "Full read"), never labelled by job
# title. This lives in the test rather than the validator on purpose: the decision was
# to fix the examples, not to add another rule. It guards the shipped examples from
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

    def test_retired_audience_marker_is_rejected_and_explained(self):
        """The alias is gone, and this test is the inverse of the one it replaces.

        `data-audience="pm"` was accepted so pre-rename artifacts would keep validating.
        Measured on a live lane of 197 artifacts, 158 carried it, 0 carried
        `data-summary`, and the newest of the 158 was written that same week. The alias
        was not easing a migration, it was the reason none started: nothing ever told an
        author, or the model copying the previous artifact, that the marker names a job
        title in the markup. Segmenting the reader is one of the spine's absolutes.

        Both errors must fire. `summary-first` alone would say "add a summary block" to
        an artifact that already has one, which sends the author looking for the wrong
        problem; `audience-segmentation` is the one that names the actual fix.
        """
        retired = _artifact("<p>x</p>").replace(
            '<section data-summary="true">', '<section data-audience="pm">'
        )
        errors, _ = hha.content_shape_violations(
            Path("a.html"), retired, "2026-07-26", REPO, "plan"
        )
        self.assertTrue(
            any("[rule=audience-segmentation]" in e for e in errors),
            "retired data-audience must be named as segmentation: " + str(errors),
        )
        self.assertTrue(
            any("[rule=summary-first]" in e for e in errors),
            "retired data-audience must no longer count as the summary marker: " + str(errors),
        )

    def test_rule_id_alias_for_the_retired_rule_name_still_answers(self):
        """The asymmetry is deliberate: a retired RULE ID keeps answering forever, because
        a suppression comment is an author's decision that must not silently invert. A
        retired CONTENT MARKER does not, because keeping it alive perpetuates the thing
        the rule exists to remove."""
        self.assertIn("pm-summary", hha._RULE_ID_ALIASES["summary-first"])

    def test_the_retired_marker_can_be_documented_without_failing(self):
        """A regex over the source cannot tell an attribute from one quoted in a comment
        or shown as escaped text, so an artifact explaining the migration failed the very
        rule it was explaining."""
        for body, label in (
            ('<!-- <section data-audience="pm"> --><p>x</p>', "in a comment"),
            ('<pre>&lt;section data-audience="pm"&gt;</pre>', "escaped in a pre"),
        ):
            with self.subTest(label):
                errors = hha.content_shape_violations(
                    Path("a.html"), _artifact(body), "2026-07-26", REPO, "plan"
                )[0]
                self.assertFalse(
                    any("[rule=audience-segmentation]" in e for e in errors), label
                )

    def test_a_real_audience_attribute_still_blocks(self):
        errors = hha.content_shape_violations(
            Path("a.html"), _artifact('<section data-audience="pm"><p>x</p></section>'),
            "2026-07-26", REPO, "plan",
        )[0]
        self.assertTrue(any("[rule=audience-segmentation]" in e for e in errors))

    def test_prose_near_a_read_map_mention_does_not_warn(self):
        """The windowed regex matched `read-map` anywhere and then any `<strong>` within
        800 characters, so an ordinary paragraph tripped it."""
        body = (
            "<p>The read-map goes above the first section.</p>"
            "<p><strong>Product launch</strong> is in June.</p>"
            '<section id="s"><h2>Context</h2><p>x</p></section>'
        )
        warnings = hha.content_shape_violations(
            Path("a.html"), _artifact(body), "2026-07-26", REPO, "plan"
        )[1]
        self.assertFalse(any("[rule=role-labelled-guide]" in w for w in warnings))

    def test_a_depth_labelled_reading_guide_does_not_warn(self):
        body = '<aside class="read-map"><div><strong>Quick read:</strong> summary</div></aside>'
        warnings = hha.content_shape_violations(
            Path("a.html"), _artifact(body), "2026-07-26", REPO, "plan"
        )[1]
        self.assertFalse(any("[rule=role-labelled-guide]" in w for w in warnings))

    def test_role_labelled_reading_guide_warns(self):
        body = (
            '<aside class="read-map"><div><strong>Exec:</strong> summary only</div></aside>'
            '<section id="s"><h2>Context</h2><p>x</p></section>'
        )
        warnings = hha.content_shape_violations(
            Path("a.html"), _artifact(body), "2026-07-26", REPO, "plan"
        )[1]
        self.assertTrue(
            any("[rule=role-labelled-guide]" in w for w in warnings),
            "a reading guide labelled by job title should warn: " + str(warnings),
        )


class ClaimOwnerTest(unittest.TestCase):
    """A section that commits somebody has to name who.

    The windowing is the part worth testing. An owner is normally declared on the
    section's own opening tag, which sits BEFORE the heading, so the search window
    cannot start where `comparison-visual`'s does. It also cannot run back
    unbounded, or a neighbouring section's owner would satisfy an unowned one.
    """

    def _warn_rules(self, body: str, *, mode: str = "", kind: str = "decision") -> list[str]:
        warnings = hha.content_shape_violations(
            Path("a.html"), _artifact(body, mode=mode, kind=kind), "2026-07-26", REPO, kind
        )[1]
        return [w for w in warnings if "[rule=claim-owner]" in w]

    def test_fires_on_unowned_judgment_heading(self):
        for heading in ("Decision", "Verdict", "Recommendation", "Corrective actions", "Next steps"):
            with self.subTest(heading=heading):
                warns = self._warn_rules(f'<section id="j"><h2>{heading}</h2><p>x</p></section>')
                self.assertEqual(len(warns), 1, f"{heading} should warn: {warns}")

    def test_silent_when_owner_on_the_section_opening_tag(self):
        # The tag precedes the heading, which is exactly why the window is widened.
        body = '<section id="j" data-owner="Ana Silva"><h2>Decision</h2><p>x</p></section>'
        self.assertEqual(self._warn_rules(body), [])

    def test_owner_on_a_sibling_does_not_count(self):
        """Ownership is an enclosing claim, not a nearby one. A `<p>` after the heading is
        a sibling, so it cannot answer for the section."""
        body = '<section id="j"><h2>Decision</h2><p data-owner="Ana Silva">x</p></section>'
        self.assertEqual(len(self._warn_rules(body)), 1)

    def test_owner_on_an_ancestor_covers_a_nested_heading(self):
        """Both reviewers reproduced the inverse under the old substring window: a `<div>`
        closed before the heading was taken for its container, so an owned section still
        warned."""
        body = (
            '<section id="j" data-owner="Ana Silva"><h2>Context</h2>'
            '<div class="callout">note</div><h3>Decision</h3><p>x</p></section>'
        )
        self.assertEqual(self._warn_rules(body), [])

    def test_a_closed_sibling_cannot_lend_its_owner(self):
        """The other half of the same reviewer finding: a preceding closed `<div>` with an
        unrelated data-owner used to satisfy an unowned judgment section."""
        body = (
            '<section id="s"><h2>Context</h2><div data-owner="chart source"></div>'
            "<h2>Decision</h2><p>x</p></section>"
        )
        self.assertEqual(len(self._warn_rules(body)), 1)

    def test_neighbouring_owner_does_not_satisfy_an_unowned_section(self):
        body = (
            '<section id="a" data-owner="Ana Silva"><h2>Context</h2><p>x</p></section>'
            '<section id="b"><h2>Decision</h2><p>x</p></section>'
        )
        self.assertEqual(len(self._warn_rules(body)), 1)

    def test_empty_owner_does_not_count(self):
        for value in ('""', '" "', '"&nbsp;"'):
            with self.subTest(value=value):
                body = f'<section id="j" data-owner={value}><h2>Decision</h2><p>x</p></section>'
                self.assertEqual(len(self._warn_rules(body)), 1)

    def test_unquoted_owner_counts(self):
        """Valid HTML, and the old regex required quotes."""
        body = '<section id="j" data-owner=Ana><h2>Decision</h2><p>x</p></section>'
        self.assertEqual(self._warn_rules(body), [])

    def test_a_longer_attribute_name_does_not_count(self):
        r"""`\bdata-owner` matched the tail of `data-source-data-owner`, because `-` is
        not a word character."""
        body = '<section data-source-data-owner="Ana"><h2>Decision</h2><p>x</p></section>'
        self.assertEqual(len(self._warn_rules(body)), 1)

    def test_an_owner_in_a_comment_or_shown_as_text_does_not_count(self):
        for body in (
            '<!-- <section data-owner="Ana"> --><section><h2>Decision</h2><p>x</p></section>',
            '<section><h2>Decision</h2><pre>&lt;section data-owner="Ana"&gt;</pre></section>',
        ):
            with self.subTest(body=body[:40]):
                self.assertEqual(len(self._warn_rules(body)), 1)

    def test_body_and_main_cannot_own_the_whole_page(self):
        """One attribute high enough up would silently satisfy every section below it."""
        art = _artifact('<section id="j"><h2>Decision</h2><p>x</p></section>').replace(
            "<main>", '<main data-owner="Ana Silva">'
        )
        warnings = hha.content_shape_violations(
            Path("a.html"), art, "2026-07-26", REPO, "decision"
        )[1]
        self.assertTrue(any("[rule=claim-owner]" in w for w in warnings))

    def test_implicitly_closed_elements_are_not_ancestors(self):
        """HTML closes some elements for you. `<p data-owner>` before an `<h2>` is a
        sibling to a browser, so it cannot own the heading; keeping it on the stack made
        the rule silently accept an unowned section."""
        for body, label in (
            ('<p data-owner="Ana Silva"><h2>Decision</h2>', "p closed by h2"),
            ('<ul><li data-owner="Ana Silva"><li><h2>Decision</h2></ul>', "li closed by li"),
            ('<table><tr><td data-owner="Ana"><tr><td><h2>Decision</h2></table>', "td/tr"),
        ):
            with self.subTest(label):
                self.assertEqual(len(self._warn_rules(body)), 1)

    def test_a_genuine_ancestor_still_owns_after_an_implicit_close(self):
        body = '<section data-owner="Ana Silva"><p>lead</p><h2>Decision</h2></section>'
        self.assertEqual(self._warn_rules(body), [])

    def test_a_trailing_slash_on_a_non_void_element_does_not_close_it(self):
        """HTML treats `<section/>` as a parse error and then ignores the slash, so the
        section stays open and owns what follows. Treating it as opened-and-closed made
        the rule disagree with every browser and warn on an owned section."""
        self.assertEqual(f_unowned('<section data-owner="Ana"/><h2>Decision</h2><p>x</p>'), [])

    def test_a_void_element_still_never_becomes_an_ancestor(self):
        self.assertEqual(f_unowned('<br data-owner="Ana"/><h2>Decision</h2>'), ["Decision"])

    def test_both_parsers_agree_on_duplicate_attributes(self):
        """The first fix reached the judgment parser only; the artifact parser kept
        last-wins, so the two disagreed about the same markup."""
        for markup, expected in (
            ('<section data-summary="true" data-summary="false"><h2>x</h2></section>', True),
            ('<section data-summary="false" data-summary="true"><h2>x</h2></section>', False),
        ):
            with self.subTest(markup=markup[:48]):
                parser = hha.ArtifactHTMLParser()
                parser.feed(markup)
                self.assertEqual(parser.has_summary_block, expected)

    def test_duplicate_owner_attributes_take_the_first(self):
        """A browser keeps the first; a dict comprehension keeps the last, which read an
        empty owner as owned and, reversed, invented a warning on a real one."""
        self.assertEqual(
            len(self._warn_rules('<section data-owner="" data-owner="Ana"><h2>Decision</h2></section>')), 1
        )
        self.assertEqual(
            self._warn_rules('<section data-owner="Ana" data-owner=""><h2>Decision</h2></section>'), []
        )

    def test_data_judgment_opts_a_non_matching_heading_in(self):
        """The escape hatch for a section whose heading states the judgment rather than
        naming it, e.g. "Lead with the narrow first stage" as a recommendation."""
        body = (
            '<section id="j" data-judgment="true">'
            "<h2>Lead with the narrow first stage</h2><p>x</p></section>"
        )
        self.assertEqual(len(self._warn_rules(body)), 1)
        owned = body.replace('data-judgment="true"', 'data-judgment="true" data-owner="Ana"')
        self.assertEqual(self._warn_rules(owned), [])

    def test_non_judgment_headings_never_fire(self):
        for heading in ("Context", "Findings", "Where we are", "Next", "Open questions"):
            with self.subTest(heading=heading):
                body = f'<section id="j"><h2>{heading}</h2><p>x</p></section>'
                self.assertEqual(self._warn_rules(body, kind="research"), [])

    def test_in_force_in_dynamic_mode(self):
        """Who holds a call does not depend on which sections exist, so this is not
        one of the three shape rules that stand down."""
        body = '<section id="j"><h2>Recommendation</h2><p>x</p></section>'
        self.assertEqual(len(self._warn_rules(body, mode="dynamic")), 1)


class DocsMatchTheCodeTest(unittest.TestCase):
    """The documentation and the checker must agree about what the checker does.

    Asked for by a reviewer after finding that the references still described the
    pre-change contract. It earned its place immediately: the first run found
    `size-budget`, a rule the checker had been emitting for releases with no row in the
    documented table at all, so nobody reading the contract knew it existed.
    """

    SKILL = REPO / "skills/human-html/SKILL.md"
    _EMITTED_RE = re.compile(r'_add\(\s*\w+,\s*parser,\s*"([a-z-]+)"')

    def _emitted_rule_ids(self) -> set[str]:
        return set(self._EMITTED_RE.findall(SCRIPT.read_text(encoding="utf-8")))

    def _documented_rule_ids(self) -> set[str]:
        text = self.SKILL.read_text(encoding="utf-8")
        table = re.search(r"\| Rule ID \| Severity.*?\n\n", text, re.S)
        assert table is not None, "the rule ID table is missing from SKILL.md"
        return set(re.findall(r"^\| `([a-z-]+)`", table.group(0), re.M))

    def test_every_emitted_rule_is_documented(self):
        undocumented = self._emitted_rule_ids() - self._documented_rule_ids()
        self.assertEqual(
            undocumented, set(),
            "these rules can fire but are not in the SKILL.md table, so a reader of the "
            f"contract cannot know they exist: {sorted(undocumented)}",
        )

    def test_every_documented_rule_can_actually_fire(self):
        phantom = self._documented_rule_ids() - self._emitted_rule_ids()
        self.assertEqual(
            phantom, set(),
            f"documented but never emitted, so the table promises what the checker does "
            f"not do: {sorted(phantom)}",
        )

    def test_the_spine_states_the_right_rule_count(self):
        spine = (REPO / "skills/human-html/references/artifact-spine.md").read_text(encoding="utf-8")
        words = {
            15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
            20: "twenty", 21: "twenty-one", 22: "twenty-two", 23: "twenty-three",
        }
        expected = words.get(len(self._documented_rule_ids()))
        self.assertIsNotNone(expected, "extend the number words in this test")
        self.assertIn(
            f"The {expected} content rules", spine,
            "artifact-spine.md opens by counting the rules; that count has drifted",
        )

    def test_the_readme_states_the_right_blocker_count(self):
        text = self.SKILL.read_text(encoding="utf-8")
        found = re.search(r"\| Rule ID \| Severity.*?\n\n", text, re.S)
        assert found is not None
        table = found.group(0)
        blockers = [
            row for row in table.splitlines()
            if row.startswith("| `") and re.search(r"\bBLOCK\b", row)
        ]
        words = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
        # nav-anchors and required-section are conditional, so the README counts the
        # rules that block unconditionally rather than every row mentioning BLOCK.
        unconditional = [r for r in blockers if "WARN" not in r]
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            f"blocks on {words[len(unconditional)]} rules", readme,
            f"README blocker count has drifted; unconditional blockers are "
            f"{[re.findall(r'`([a-z-]+)`', r)[0] for r in unconditional]}",
        )


class ExamplesDoNotContradictThemselvesTest(unittest.TestCase):
    """A reviewer found the flagship examples undercutting the branch's own thesis.

    `review-canonical` said "the one required change" three times and listed two.
    `status-canonical` asked a person who owned nothing to confirm a blocker while the
    real owner went unnamed. Neither is reachable by a content rule, because both are
    the answer-first opener disagreeing with the detail rather than a missing marker.
    These two guards are narrow on purpose: they hold the shipped examples to the
    counts they claim, and nothing more.
    """

    EXAMPLES = REPO / "skills/human-html/examples"

    def _section_items(self, name: str, anchor: str) -> int:
        text = (self.EXAMPLES / name).read_text(encoding="utf-8")
        section = re.search(rf'<section[^>]*id="{anchor}".*?</section>', text, re.S)
        assert section is not None, f"{name} has no #{anchor}"
        return len(re.findall(r"<li\b", section.group(0)))

    def test_review_examples_required_count_matches_its_claim(self):
        text = (self.EXAMPLES / "review-canonical.html").read_text(encoding="utf-8")
        claims_one = "the one required change" in text
        self.assertTrue(claims_one, "the summary's wording changed; update this guard")
        self.assertEqual(
            self._section_items("review-canonical.html", "required"), 1,
            "the summary says one required change; #required lists a different number",
        )

    def test_status_example_asks_only_real_owners_to_confirm(self):
        text = (self.EXAMPLES / "status-canonical.html").read_text(encoding="utf-8")
        summary = re.search(r'<section[^>]*data-summary="true".*?</section>', text, re.S)
        assert summary is not None
        asked = set(re.findall(r"\b(Priya|Marcus|Jordan)\b", summary.group(0)))
        blockers = re.search(r'<section[^>]*id="blockers".*?</section>', text, re.S)
        assert blockers is not None
        owners = set(re.findall(r"\b(Priya|Marcus|Jordan)\b", blockers.group(0)))
        self.assertTrue(
            asked <= owners,
            f"the summary asks {sorted(asked - owners)} to confirm a blocker they do not "
            "own; an escalation path is not an owner",
        )


class ProseBudgetTest(unittest.TestCase):
    """The ceiling `required-section` never had, measured in words rather than bytes."""

    def _warns(self, body: str) -> list[str]:
        return hha.content_shape_violations(
            Path("a.html"), _artifact(body), "2026-07-26", REPO, "plan"
        )[1]

    def test_a_gt_inside_an_attribute_does_not_leak_into_the_count(self):
        """Stripping tags with `<[^>]+>` ends the tag at the first `>`, so the tail of an
        attribute value became prose the reader never sees."""
        self.assertEqual(hha.prose_words('<p title="one two > three four five">visible</p>'), 1)

    def test_preformatted_blocks_are_not_prose_but_inline_code_is(self):
        """Block-preformatted content is not read at prose speed and often is not read at
        all: a code sample, an ASCII diagram, or the mermaid source `embed-svg` parks in a
        collapsed <details>. Counting it meant the tooling inflated the length it measured.
        Inline `code` stays counted, because it sits inside a sentence."""
        self.assertEqual(hha.prose_words("<p>one</p><pre>two three four</pre>"), 1)
        self.assertEqual(hha.prose_words("<p>one <code>two</code> three</p>"), 3)
        self.assertEqual(hha.prose_words("<pre><code>a b c</code></pre>"), 0)

    def test_prose_words_ignores_markup_script_and_style(self):
        content = (
            "<p>one two three</p><script>var a = 1; var b = 2; var c = 3;</script>"
            "<style>.x{color:red;background:blue;border:0}</style>"
            "<svg><text>alpha beta gamma delta</text></svg><!-- four five six -->"
        )
        self.assertEqual(hha.prose_words(content), 3)

    def test_warns_past_the_budget(self):
        body = "<p>" + ("word " * (hha._PROSE_BUDGET_WORDS + 200)) + "</p>"
        self.assertTrue(any("[rule=prose-budget]" in w for w in self._warns(body)))

    def test_silent_under_the_budget(self):
        body = "<p>" + ("word " * 200) + "</p>"
        self.assertFalse(any("[rule=prose-budget]" in w for w in self._warns(body)))

    def test_budget_is_calibrated_above_every_shipped_example(self):
        """A ceiling that fires on the skill's own examples would be noise on arrival."""
        examples = sorted((REPO / "skills/human-html/examples").glob("*.html"))
        self.assertTrue(examples)
        worst = max(hha.prose_words(p.read_text(encoding="utf-8")) for p in examples)
        self.assertLess(worst, hha._PROSE_BUDGET_WORDS)


class ReadTimeTest(unittest.TestCase):
    """A declared read-time that tracks nothing is what a model writes when nothing
    constrains it. Measured on a live lane: 194 words claimed 5 min, 4,701 words claimed
    5 min, and the longest artifact gave up and said "browse"."""

    def _artifact_with(self, declared: str, words: int) -> str:
        art = _artifact("<p>" + ("word " * words) + "</p>")
        return art.replace(
            '<meta name="artifact-created" content="2026-07-26">',
            '<meta name="artifact-created" content="2026-07-26">'
            f'<meta name="artifact-read-time" content="{declared}">',
        )

    def _warns(self, declared: str, words: int) -> list[str]:
        return hha.content_shape_violations(
            Path("a.html"), self._artifact_with(declared, words), "2026-07-26", REPO, "plan"
        )[1]

    def test_warns_when_the_claim_does_not_track_the_prose(self):
        self.assertTrue(any("[rule=read-time]" in w for w in self._warns("5 min", 3000)))

    def test_a_zero_minute_claim_warns(self):
        """`0 min` carries a number, and zero is falsy, so it skipped the tolerance branch
        and handed the reader an impossible budget in silence."""
        self.assertTrue(any("[rule=read-time]" in w for w in self._warns("0 min", 3000)))

    def test_warns_when_the_field_carries_no_number(self):
        self.assertTrue(any("[rule=read-time]" in w for w in self._warns("browse", 3000)))

    def test_silent_within_tolerance(self):
        # ~870 words is about 4 minutes; a 5 minute claim is honest.
        self.assertFalse(any("[rule=read-time]" in w for w in self._warns("5 min", 870)))

    def test_silent_when_absent_on_a_scaffold_sized_artifact(self):
        """A fresh scaffold is placeholder prose. Nagging there trains an author to ignore
        the rule before they have written anything, so the nudge waits for real content."""
        warns = hha.content_shape_violations(
            Path("a.html"), _artifact("<p>x</p>"), "2026-07-26", REPO, "plan"
        )[1]
        self.assertFalse(any("[rule=read-time]" in w for w in warns))

    def test_warns_when_absent_once_the_artifact_has_real_content(self):
        body = "<p>" + ("word " * (hha._READ_TIME_MIN_WORDS + 100)) + "</p>"
        warns = hha.content_shape_violations(
            Path("a.html"), _artifact(body), "2026-07-26", REPO, "plan"
        )[1]
        self.assertTrue(any("[rule=read-time]" in w for w in warns), str(warns))

    def test_scaffold_ships_no_read_time_and_says_so_in_the_ribbon(self):
        page = hha.render_artifact("T", "plan", "2026-07-26", "local")
        self.assertIn('<meta name="artifact-read-time" content="">', page)
        self.assertIn("fill before publishing", page)


class ReviewStateTest(unittest.TestCase):
    """Three named states, because a live lane hand-rolled "pending" in nine distinct spellings."""

    def _provenance(self, extra: str) -> list[str]:
        body = (
            '<section id="s"><h2>Context</h2><p>x</p></section>'
            '<footer data-provenance="true">'
            '<script type="application/ld+json" id="provenance">'
            '{"@id":"urn:x","dateCreated":"2026-07-26",'
            '"creator":{"name":"m"},"prompt":"p","reviewer":"Ana Silva"' + extra + "}"
            "</script></footer>"
        )
        return hha.content_shape_violations(
            Path("a.html"), _artifact(body), "2026-07-26", REPO, "plan"
        )[1]

    def test_known_state_is_accepted(self):
        for state in hha._REVIEW_STATES:
            with self.subTest(state=state):
                warns = self._provenance(f',"reviewState":"{state}"')
                self.assertFalse([w for w in warns if "reviewState" in w], str(warns))

    def test_a_non_string_state_warns(self):
        """The isinstance guard used to gate the whole check, so a truthy non-string
        satisfied the missing-field test and was skipped by the value test: silent both
        ways. A JSON type slip is in scope for a field that exists because free text
        produced nine spellings of one state."""
        for literal, label in (("123", "number"), ("true", "boolean"),
                               ('["human-reviewed"]', "list"), ('{"v":"x"}', "object")):
            with self.subTest(label):
                warns = self._provenance(f',"reviewState":{literal}')
                self.assertTrue(any("reviewState" in w for w in warns), f"{label}: {warns}")

    def test_unknown_state_warns(self):
        warns = self._provenance(',"reviewState":"pending"')
        self.assertTrue(any("reviewState" in w for w in warns), str(warns))

    def test_missing_state_is_reported_as_a_missing_field(self):
        warns = self._provenance("")
        self.assertTrue(any("reviewState" in w for w in warns), str(warns))

    def test_scaffold_ships_unreviewed(self):
        page = hha.render_artifact("T", "plan", "2026-07-26", "local")
        self.assertIn('"reviewState": "unreviewed"', page)
        self.assertIn("not yet reviewed by a human", page)


class LayoutRegressionTest(unittest.TestCase):
    """Two layout bugs found in real artifacts, guarded so they cannot quietly return.

    Neither is reachable from a unit test in the usual sense, because both are CSS and
    only a browser can prove them. What a test CAN do is hold the fix in place, which is
    the actual risk: both rules look like tidy-up and would be easy to delete.
    """

    def test_keycard_does_not_depend_on_child_count(self):
        """A third child used to wrap into column 1, whose `auto` width then grew to fit a
        paragraph and starved the 1fr column to a one-word-per-line ribbon."""
        css = hha._SCAFFOLD_STYLE + hha._EXTRA_SCAFFOLD_STYLE
        self.assertIn(".keycard > * { grid-column:2;", css)
        self.assertRegex(css, r"\.keycard > :first-child:is\([^)]*\.big[^)]*\)")
        # the mobile single-column override must release the placement, or it conjures
        # an implicit second column and puts the hero back beside the text
        self.assertRegex(css, r"\.keycard > \*,[^\n]*grid-column:1; grid-row:auto")

    def test_embedded_diagram_font_is_not_a_generic_keyword(self):
        """`embed-svg` measures labels once and writes a fixed foreignObject height. A
        generic keyword resolves to a different physical font per OS, so the reader's
        re-flow overflows the baked box and the last line is clipped away."""
        for generic in ("system-ui", "ui-sans-serif", "ui-rounded", "-apple-system"):
            self.assertNotIn(generic, hha._DIAG_FONT)
        self.assertIn("Arial", hha._DIAG_FONT)

    def test_embedded_diagram_labels_overflow_rather_than_clip(self):
        """The base scaffold carried this for live `.mermaid` blocks from the start;
        `embed-svg` rewrites the wrapper and the rule did not follow it across."""
        self.assertIn("foreignObject", hha._DIAG_STYLE)
        self.assertIn("overflow: visible", hha._DIAG_STYLE)
        for wrapper in (".diagram-light", ".diagram-dark"):
            self.assertRegex(
                hha._DIAG_STYLE,
                rf"{re.escape(wrapper)} foreignObject[^}}]*\{{[^}}]*overflow: visible",
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
    runs `git diff <rev> -- <paths>`. Without it the list is decoration.
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

    def _files_read_parts(self, text: str) -> dict | None:
        """Pull a files-read block apart, or None when the artifact carries no block.

        Shared by the two guards below so they cannot end up disagreeing about what
        counts as a listed path, which is how the `<li>` blind spot below survived.
        """
        pattern = r'<details class="files-read">(.*?)</details>'
        # Comments come out first. A <script> or <textarea> merely NAMED inside a comment is
        # not an element, and treating it as an opening tag would delete everything up to the
        # next real closing tag, swallowing the block. Same bug simulate_no_js hit with
        # <noscript>; see human_html_artifacts.py.
        source = hha._HTML_COMMENT_RE.sub("", text)

        # Spans whose contents a browser renders as text, not markup. A block inside one is a
        # sample being displayed, not a block on the page.
        samples = [
            match.span()
            for match in re.finditer(
                r"<(textarea|script)\b[^>]*>.*?</\1\s*>", source,
                flags=re.DOTALL | re.IGNORECASE,
            )
        ]

        def is_sample(start: int) -> bool:
            return any(begin <= start < end for begin, end in samples)

        # Compared by position rather than by counting before and after the strip. Counting
        # cannot tell "an unbalanced tag ate a real block" from "the only block was a sample",
        # and those need opposite answers: the first is a guard failure, the second is simply
        # not a carrier.
        found = [m for m in re.finditer(pattern, source, re.DOTALL) if not is_sample(m.start())]
        if not found:
            return None
        html = found[0].group(1)
        blocks = [m.group(1) for m in found]
        summary = re.search(r"<summary\b[^>]*>(.*?)</summary>", html, re.DOTALL)
        return {
            "html": html,
            # Only the first block is parsed, so a second would go unchecked. The guards
            # assert this is 1 rather than quietly inspecting one block out of several.
            "blocks": len(blocks),
            "summary": summary.group(1) if summary else None,
            # Attributes on the <li> are tolerated: markup this pattern fails to match is
            # a visible path the guards cannot see, not a path that is absent.
            "shown": re.findall(r"<li\b[^>]*>\s*<code>([^<]+)</code>", html),
            "items": len(re.findall(r"<li\b", html)),
            # The command is line-wrapped in the source; collapse before matching.
            "command": re.search(r"<code>(git diff [^<]*)</code>", " ".join(html.split())),
        }

    def _summary_revision(self, parts: dict) -> str | None:
        """The revision as the summary shows it, as an exact token.

        Compared by equality rather than substring because `readAtRevision` is any
        non-empty string and so may be a branch or tag rather than a hex SHA. A declared
        `main` is a substring of a summary reading `domain`, so membership would call two
        different revisions equal.
        """
        if parts["summary"] is None:
            return None
        code = re.search(r"<code>([^<]+)</code>", parts["summary"])
        return code.group(1).strip() if code else None

    def _command_operands(self, parts: dict) -> list[str]:
        """The tokens the command passes before the `--`, without interpreting them.

        Deliberately does not try to work out *which* one is the revision. Every attempt
        at that needs to know which flags take a separate value, and git has several
        (`-S needle`, `-l 5`), so a flag's value gets reported as the revision whenever
        the command has no revision at all. The caller asks the answerable question
        instead: is the declared revision one of these tokens?
        """
        if parts["command"] is None:
            return []
        head, _, _ = parts["command"].group(1).partition(" -- ")
        return head.split()

    def test_every_files_read_block_agrees_with_its_own_json_ld(self):
        """The visible list and the JSON-LD are one fact written twice.

        The failure mode is editing one and forgetting the other, which leaves a reader
        running a `git diff` over a path set the artifact no longer claims to have read.
        Runs over every example carrying the block, so a new one is covered on arrival.

        The revision is checked in the summary and in the command separately, not just
        somewhere in the block: searching the whole block lets the summary drift to a
        different revision while the command still carries the declared one, and the
        summary is the revision the reader actually reads.
        """
        examples = sorted((REPO / "skills/human-html/examples").glob("*.html"))
        carriers = []
        for path in examples:
            parts = self._files_read_parts(path.read_text(encoding="utf-8"))
            if parts is None:
                continue
            carriers.append(path.name)
            with self.subTest(example=path.name):
                self.assertEqual(
                    parts["blocks"], 1,
                    "only the first files-read block is parsed, so a second one would "
                    "go unchecked; keep one block per artifact",
                )
                shown = parts["shown"]
                self.assertTrue(shown, "the block lists no files")
                self.assertEqual(
                    len(shown), parts["items"],
                    "an <li> in the block was not read as a path, so the visible list "
                    "could gain or lose a file without this guard noticing",
                )

                text = path.read_text(encoding="utf-8")
                script = re.search(
                    r'<script type="application/ld\+json" id="provenance">(.*?)</script>',
                    text, re.DOTALL,
                )
                assert script is not None, f"{path.name} has no provenance JSON-LD"
                declared = json.loads(script.group(1)).get("sourceFiles")
                self.assertIsNotNone(
                    declared, "a visible files-read block needs a sourceFiles object too"
                )
                self.assertEqual(shown, declared["paths"], "visible list and JSON-LD disagree")
                self.assertIn(
                    f"Files read ({len(shown)})", parts["html"], "summary count is stale"
                )

                revision = declared["readAtRevision"]
                assert parts["command"] is not None, f"{path.name} states no staleness command"
                self.assertEqual(
                    self._summary_revision(parts), revision,
                    "the revision the summary shows is not the one the JSON-LD declares",
                )
                operands = self._command_operands(parts)
                self.assertIn(
                    revision, operands,
                    "the command does not pass the revision the JSON-LD declares",
                )
                # And it must be the LAST thing before the `--`. Membership alone lets a
                # second commit operand through: `git diff <rev> HEAD -- <paths>` contains
                # the declared revision and is still a commit-to-commit diff, which reports
                # an uncommitted edit as clean. That is the same defect as the `<rev>..HEAD`
                # spelling this pattern exists to avoid, just written with a space.
                self.assertEqual(
                    operands[-1], revision,
                    "the declared revision must be the last thing the command passes before "
                    "the `--`, so no second commit operand can turn it into a diff between "
                    "two commits",
                )
        self.assertGreaterEqual(
            len(carriers), 2,
            "at least two shipped examples should demonstrate the pattern; found: " + str(carriers),
        )

    def test_every_staleness_command_covers_every_file_it_lists(self):
        """The `git diff` pathspec may exceed the listed files; it must never trim them.

        The block's promise is that empty output means nothing the artifact read has
        moved. A pathspec narrower than the list breaks that promise without ever
        looking broken: the command still prints nothing while a file a claim rests on
        has changed underneath it. Widening is legitimate and sometimes stronger, so
        this asserts containment rather than equality.
        """
        examples = sorted((REPO / "skills/human-html/examples").glob("*.html"))
        for path in examples:
            parts = self._files_read_parts(path.read_text(encoding="utf-8"))
            if parts is None:
                continue
            with self.subTest(example=path.name):
                command = parts["command"]
                assert command is not None, f"{path.name} states no staleness command"
                _, separator, pathspec = command.group(1).partition(" -- ")
                self.assertTrue(separator, "the staleness command has no `--` pathspec")
                # A glob pathspec is quoted in the command so the shell leaves it to git.
                scopes = [scope.strip("'\"") for scope in pathspec.split()]
                self.assertTrue(scopes, "the staleness command has an empty pathspec")
                for listed in parts["shown"]:
                    self.assertTrue(
                        any(
                            listed == scope
                            or listed.startswith(scope.rstrip("/") + "/")
                            # git's pathspec `*` crosses directory boundaries, and so does
                            # fnmatch's, so a glob scope covers what git says it covers.
                            or fnmatch.fnmatch(listed, scope)
                            for scope in scopes
                        ),
                        f"{listed} is listed as read but falls outside the pathspec "
                        f"{scopes}, so empty output would not prove it is untouched",
                    )

    def test_the_documented_snippet_obeys_the_rules_it_is_printed_beside(self):
        """The snippet in `patterns.md` is held *tighter* than a shipped artifact.

        It is the copy source, so it outranks the prose next to it: whatever it does is
        what the next artifact does. So its pathspec must match its declared paths
        exactly, rather than merely containing them. An artifact is allowed to widen,
        and `dynamic-port-correspondence.html` is where that exception is demonstrated
        with the clause explaining it; a bare widening in the snippet teaches the
        exception as the default and costs every copier a false alarm on an undeclared
        file. Nothing checked the snippet until now, which is how it came to list
        `routes/*.ts` while diffing the wider `routes/`.
        """
        doc = (REPO / "skills/human-html/references/patterns.md").read_text(encoding="utf-8")
        parts = self._files_read_parts(doc)
        self.assertIsNotNone(parts, "patterns.md no longer ships a files-read snippet")
        assert parts is not None
        self.assertEqual(
            parts["blocks"], 1,
            "only the first snippet is parsed, so a second one would go unchecked",
        )

        # The JSON-LD half is a fragment in its own fence, so brace it back into an object.
        fragment = re.search(r'("sourceFiles":\s*\{.*?\n\})', doc, re.DOTALL)
        assert fragment is not None, "patterns.md ships no sourceFiles snippet"
        declared = json.loads("{" + fragment.group(1) + "}")["sourceFiles"]

        self.assertEqual(
            parts["shown"], declared["paths"],
            "the snippet's visible list and its JSON-LD disagree",
        )
        self.assertEqual(
            len(parts["shown"]), parts["items"], "an <li> in the snippet was not read as a path"
        )
        revision = declared["readAtRevision"]
        self.assertIsNotNone(parts["summary"], "the snippet has no <summary>")
        self.assertIn(revision, parts["summary"], "the snippet's summary revision disagrees")
        command = parts["command"]
        assert command is not None, "the snippet states no staleness command"
        self.assertIn(revision, command.group(1), "the snippet's command revision disagrees")

        _, separator, pathspec = command.group(1).partition(" -- ")
        self.assertTrue(separator, "the snippet's command has no `--` pathspec")
        scopes = [scope.strip("'\"") for scope in pathspec.split()]
        self.assertEqual(
            sorted(scopes), sorted(parts["shown"]),
            "the snippet's pathspec must be exactly the paths it declares; widening is "
            "an artifact's call to make and to explain, and teaching it as the default "
            "costs every copier a false alarm on an undeclared file. Order is not "
            "checked: the same paths in a different order cover the same scope",
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
