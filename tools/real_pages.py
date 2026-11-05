"""How close is seenonly to a real browser on real pages?

Loads each page in Chromium, then compares the words on screen with the words of clean(). Page text
is not stored; only the numbers are printed.

  dropped  words on screen that seenonly removed (false positives, lower is better)
  leaked   words seenonly kept that are not on screen (missed hidden text, lower is better)

"On screen" comes from the browser's own layout: see tools/browser.py. Each page runs twice: with the
stylesheets the browser applied, and with the HTML alone, which is what a plain HTTP client has.

    python tools/real_pages.py
"""
import collections
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from browser import WORD, load  # noqa: E402
from seenonly import clean  # noqa: E402

URLS = """
https://en.wikipedia.org/wiki/Prompt_injection
https://uk.wikipedia.org/wiki/Женева
https://www.gov.uk/foreign-travel-advice/switzerland
https://www.bbc.com/news
https://www.theguardian.com/international
https://apnews.com/
https://www.who.int/news
https://www.un.org/en/
https://reliefweb.int/updates
https://www.icrc.org/en
https://www.nasa.gov/
https://developer.mozilla.org/en-US/docs/Web/CSS/display
https://docs.python.org/3/library/html.parser.html
https://github.com/python/cpython
https://news.ycombinator.com/
https://stackoverflow.com/questions/tagged/python
https://arxiv.org/abs/2302.12173
https://www.w3.org/TR/CSS2/visufx.html
https://getbootstrap.com/docs/5.3/utilities/display/
https://tailwindcss.com/docs/display
https://www.nginx.com/
https://www.debian.org/
https://www.admin.ch/gov/en/start.html
https://www.lemonde.fr/
https://www.spiegel.de/
https://www.ukrinform.ua/
https://wordpress.org/news/
https://www.nytimes.com/
https://www.amazon.com/
https://www.reddit.com/r/python/
""".split()


def words(text):
    return collections.Counter(WORD.findall(text.lower()))


def compare(browser_text, ours):
    b, o = words(browser_text), words(ours)
    total_b, total_o = sum(b.values()) or 1, sum(o.values()) or 1
    return sum((b - o).values()) / total_b * 100, sum((o - b).values()) / total_o * 100


def main():
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, locale="en-GB")
        for url in URLS:
            try:
                visible, dom, css = load(ctx, url)
            except Exception as e:
                print(f"{url}: not loaded ({str(e)[:60]})", file=sys.stderr)
                continue
            if len(WORD.findall(visible)) < 50:
                print(f"{url}: too little text, probably blocked", file=sys.stderr)
                continue
            t0 = time.perf_counter()
            full = clean(dom, css=css, phrases="off")
            ms = (time.perf_counter() - t0) * 1000
            bare = clean(dom, phrases="off")
            d1, l1 = compare(visible, full.text)
            d2, l2 = compare(visible, bare.text)
            phrases = len(clean(dom, css=css, phrases="flag").suspicious)
            rows.append((url, d1, l1, d2, l2, ms, len(dom) // 1024, phrases))
            print(f"{url[:58]:58} css: dropped {d1:5.1f}% leaked {l1:5.1f}%  html only: dropped {d2:5.1f}% leaked {l2:5.1f}%  {ms:5.0f} ms {len(dom)//1024:5} KB  suspicious {phrases}", flush=True)
        browser.close()
    if rows:
        med = lambda i: sorted(r[i] for r in rows)[len(rows) // 2]  # noqa: E731
        print(f"\n{len(rows)} pages, medians. With CSS: dropped {med(1):.1f}%, leaked {med(2):.1f}%. HTML only: dropped {med(3):.1f}%, leaked {med(4):.1f}%. Time {med(5):.0f} ms.")


if __name__ == "__main__":
    main()
