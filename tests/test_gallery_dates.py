"""The gallery's relative dates count calendar days, not elapsed milliseconds.

The first version divided `Date.now() - localMidnight(iso)` by 86,400,000 and
floored it. Local midnights are 23 or 25 hours apart across a daylight-saving
change, so early on the morning after the clocks go forward, yesterday's
artifact read `today` and the day before read `1d ago`. A future-dated
artifact also fell into the `days <= 0` branch and read `today`.

The gallery is a Python f-string that ships JavaScript, so the only honest test
runs that JavaScript. The date code is lifted out of the rendered index and run
under node with a frozen clock in a timezone that observes DST; when node is
absent the case is skipped, never passed.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).parents[1]
SCRIPT = REPO / "skills/human-html/human_html_artifacts.py"

_spec = importlib.util.spec_from_file_location("hha_gallery", SCRIPT)
assert _spec is not None and _spec.loader is not None, f"cannot load {SCRIPT}"
hha = importlib.util.module_from_spec(_spec)
sys.modules["hha_gallery"] = hha
_spec.loader.exec_module(hha)

# From the line that fixes "today" through the end of rel(): the whole unit
# the browser runs, and nothing that touches the DOM.
_REL_BLOCK_RE = re.compile(
    r"(var t = new Date\(\), todayUtc = .*?\n\s*function rel\(iso\) \{.*?\n\s*\})",
    re.DOTALL,
)

# 00:30 on 30 March 2026 in Amsterdam: half an hour into the first full day
# after the clocks went forward, where the old arithmetic saw 23.5 hours
# since yesterday's midnight and floored it to zero days.
_FROZEN_LOCAL = "new Date(2026, 2, 30, 0, 30, 0)"

_CASES = {
    "2026-03-30": "today",
    "2026-03-29": "1d ago",
    "2026-03-28": "2d ago",
    "2026-03-01": "29d ago",
    "2026-02-28": "1mo ago",
    "2025-03-30": "1y ago",
    "2026-04-01": "dated 2026-04-01",
}


def _rel_block() -> str:
    html = hha.render_index([])
    match = _REL_BLOCK_RE.search(html)
    assert match, "gallery index no longer carries the calendar-day rel() block"
    return match.group(1)


class GalleryRelativeDates(unittest.TestCase):
    def test_gallery_counts_calendar_days_not_elapsed_time(self):
        block = _rel_block()
        # The elapsed-time form is the defect; it must not come back.
        self.assertNotIn("Date.now()", block)
        self.assertNotIn("T00:00:00", block)

    @unittest.skipUnless(shutil.which("node"), "node is needed to run the gallery script")
    def test_labels_hold_across_a_dst_change_and_name_future_dates(self):
        script = "\n".join(
            [
                # Freeze the clock: an argless `new Date()` returns the fixed instant,
                # everything else on Date is untouched.
                "const Real = Date;",
                "globalThis.Date = class extends Real {",
                f"  constructor(...a) {{ super(...(a.length ? a : [{_FROZEN_LOCAL}.getTime()])); }}",
                "  static UTC(...a) { return Real.UTC(...a); }",
                "};",
                _rel_block(),
                f"const cases = {json.dumps(_CASES)};",
                "const out = {};",
                "for (const iso of Object.keys(cases)) out[iso] = rel(iso);",
                "process.stdout.write(JSON.stringify(out));",
            ]
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "TZ": "Europe/Amsterdam"},
        )
        self.assertEqual(json.loads(result.stdout), _CASES)


if __name__ == "__main__":
    unittest.main()
