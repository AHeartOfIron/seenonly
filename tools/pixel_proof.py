"""Prove the test corpus in a real browser, so the tests do not just agree with the code they test.

For each page: render it in Chromium, change the marker's letters (same length), render it again and
compare the screenshots. If no pixel changes, a person cannot see the marker: it is an attack. If
pixels change, a person can: it is a control, and removing it would be a false positive.

    pip install -e ".[proof]" && playwright install chromium
    python tools/pixel_proof.py
"""
import io
import sys
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))
from corpus import ATTACKS, CONTROLS, KNOWN_GAPS, MARKER, NO_PIXEL_PROOF, html_of, is_subtle, is_unreadable  # noqa: E402

OTHER = "".join("WVK"[i % 3] for i in range(len(MARKER)))
SUBTLE_LIMIT = 8  # out of 255: painted, but no person can read it


def shot(page, html: str) -> Image.Image:
    page.set_content(html, wait_until="load")
    return Image.open(io.BytesIO(page.screenshot(full_page=True, animations="disabled"))).convert("RGB")


def difference(page, html: str) -> int:
    """The largest change of any colour channel of any pixel, 0 to 255."""
    a, b = shot(page, html), shot(page, html.replace(MARKER, OTHER))
    if a.size != b.size:
        return 255
    return max(hi for _, hi in ImageChops.difference(a, b).getextrema())


def main() -> int:
    wrong = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # The width the library assumes in its media queries.
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        for name, item in sorted(ATTACKS.items()):
            if is_unreadable(item):
                continue
            d = difference(page, html_of(item))
            limit = SUBTLE_LIMIT if is_subtle(item) else 0
            if d > limit:
                wrong.append(f"attack {name}: a person can see it (pixel difference {d})")
        for name, item in sorted(CONTROLS.items()):
            if name in NO_PIXEL_PROOF:
                continue
            d = difference(page, html_of(item))
            if d <= SUBTLE_LIMIT:
                wrong.append(f"control {name}: a person cannot see it (pixel difference {d})")
        for name, item in sorted(KNOWN_GAPS.items()):
            d = difference(page, html_of(item))
            if d > SUBTLE_LIMIT:
                wrong.append(f"known gap {name}: a person can see it, so it is no gap (pixel difference {d})")
        version = browser.version
        browser.close()
    print(f"Chromium {version}: {len(ATTACKS)} attacks, {len(CONTROLS) - len(NO_PIXEL_PROOF)} controls, {len(KNOWN_GAPS)} known gaps")
    print("\n".join(wrong) or "All proven.")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
