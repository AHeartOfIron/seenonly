"""For one URL: what did seenonly remove that the browser shows, and for what reason? A debugging aid.

    python tools/why_dropped.py https://example.com [--bare]
"""
import collections
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from browser import WORD, load  # noqa: E402
from seenonly import clean  # noqa: E402


def main():
    url, bare = sys.argv[1], "--bare" in sys.argv
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, locale="en-GB")
        visible, dom, css = load(ctx, url)
        browser.close()
    r = clean(dom, css="" if bare else css, phrases="flag")
    shown = collections.Counter(WORD.findall(visible.lower()))
    per = collections.Counter()
    samples = {}
    for f in r.findings:
        if f.kind != "hidden":
            continue
        per[f.reason] += sum(1 for x in WORD.findall(f.text.lower()) if x in shown)
        samples.setdefault(f.reason, (f.location, f.text[:80]))
    for key, n in per.most_common(10):
        print(n, key, samples[key])
    for f in r.suspicious:
        print("SUSPICIOUS", f.kind, f.reason, f.location, f.text[:140])
    miss = collections.Counter(WORD.findall(r.text.lower())) - shown
    print("kept, not shown:", miss.most_common(12))


if __name__ == "__main__":
    main()
