"""Regression tests for content-contract detection regexes.

Covers the js-content-fallback detector, which for a long time matched only
`.innerHTML =`. Content built with createElement + textContent + appendChild
passed the rule silently -- including in this skill's own
examples/prototype-canonical.html -- so "passes js-content-fallback" was not
evidence of a real no-JS static floor.
"""

import importlib.util
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
