"""`render --width 390` must lay the page out at 390 CSS pixels.

Headless Chrome will not open a window narrower than 500 pixels. Asked for
`--window-size=390,H` it lays the page out at 500 and then crops the
screenshot to 390, so every phone-width render was a picture of the wrong
layout: text cut at the right edge on a page that was fine, and a clean crop
of a page that overflowed at 390 for real. The audit workflow ("actually look
at the PNG") rests on that picture being true.

The fix loads a wrapper whose only content is an <iframe> of the requested
width at the left edge. The frame is its own viewport, so the page inside sees
the real width, and the crop Chrome takes from the left edge is exactly the
frame. Two cases: the pure planner, and a Chrome-backed probe (skipped, never
passed, when Chrome is absent) whose page paints green only when its own
`innerWidth` is 390. The PNG is read with the standard library, so no imaging
dependency is added for one pixel.
"""

import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).parents[1]
SCRIPT = REPO / "skills/human-html/human_html_artifacts.py"

_spec = importlib.util.spec_from_file_location("hha_render", SCRIPT)
assert _spec is not None and _spec.loader is not None, f"cannot load {SCRIPT}"
hha = importlib.util.module_from_spec(_spec)
sys.modules["hha_render"] = hha
_spec.loader.exec_module(hha)

# Paints the whole page green when the layout viewport is exactly 390 wide, red
# otherwise. No fonts, no layout: one pixel is the whole verdict.
PROBE = (
    '<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1">'
    '<body style="margin:0;background:#f00"><script>'
    'if (innerWidth === 390 && document.documentElement.clientWidth === 390) '
    'document.body.style.background = "#0f0";</script></body>'
)


def _png_pixel(path: Path, x: int, y: int) -> "tuple[int, int, int]":
    """Read one RGB pixel from a non-interlaced 8-bit RGB/RGBA PNG (what Chrome writes)."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, width, height, colour, idat = 8, 0, 0, 0, b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and interlace == 0 and colour in (2, 6), "unexpected PNG layout"
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
        pos += 12 + length
    channels = 4 if colour == 6 else 3
    stride = width * channels
    raw = zlib.decompress(idat)
    rows, prev = [], bytearray(stride)
    for r in range(height):
        start = r * (stride + 1)
        filt, line = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if filt == 1:
                line[i] = (line[i] + a) & 255
            elif filt == 2:
                line[i] = (line[i] + b) & 255
            elif filt == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    off = x * channels
    return tuple(rows[y][off:off + 3])


class RenderPlan(unittest.TestCase):
    def test_wide_renders_load_the_page_directly(self):
        path, window, frame = hha._render_plan(1000, 800, "a.html")
        self.assertEqual((path, window, frame), ("/a.html", 1000, None))
        path, window, frame = hha._render_plan(hha.CHROME_MIN_WINDOW_WIDTH, 800, "a.html")
        self.assertEqual((path, window, frame), ("/a.html", hha.CHROME_MIN_WINDOW_WIDTH, None))

    def test_narrow_renders_frame_the_page_at_the_requested_width(self):
        path, window, frame = hha._render_plan(390, 2200, "phone page.html")
        self.assertEqual(path, hha._RENDER_FRAME_PATH)
        self.assertEqual(window, 390, "the screenshot keeps the requested width")
        self.assertIsNotNone(frame)
        self.assertIn("width:390px;height:2200px", frame)
        self.assertIn('src="/phone page.html"', frame)
        self.assertIn("margin:0", frame, "the frame must sit at the left edge the crop keeps")


class RenderNarrowInChrome(unittest.TestCase):
    @unittest.skipUnless(hha._find_chrome(), "Chrome is needed to render")
    def test_page_inside_a_390_render_sees_390(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "probe.html"
            page.write_text(PROBE, encoding="utf-8")
            out = Path(tmp) / "probe.png"
            with open(os.devnull, "w") as sink:
                old = sys.stdout
                sys.stdout = sink
                try:
                    rc = hha.cmd_render(str(page), str(out), 390, 200)
                finally:
                    sys.stdout = old
            self.assertEqual(rc, 0, "render must succeed")
            r, g, b = _png_pixel(out, 10, 10)
            self.assertEqual((r, g, b), (0, 255, 0), f"page did not see innerWidth 390 (pixel {r},{g},{b})")

    @unittest.skipUnless(hha._find_chrome(), "Chrome is needed to render")
    def test_the_defect_is_real_without_the_frame(self):
        # The same probe through Chrome's bare window at 390: the page lays out at 500 and
        # stays red. This is what proves the frame is doing the work.
        chrome = hha._find_chrome()
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "probe.html"
            page.write_text(PROBE, encoding="utf-8")
            out = Path(tmp) / "bare.png"
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--window-size=390,200", "--virtual-time-budget=2000",
                            f"--screenshot={out}", page.as_uri()], capture_output=True, timeout=120)
            self.assertTrue(out.exists(), "bare render must produce a PNG")
            self.assertEqual(_png_pixel(out, 10, 10), (255, 0, 0), "bare Chrome window is wider than asked")


if __name__ == "__main__":
    unittest.main()
