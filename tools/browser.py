"""Shared by real_pages.py and why_dropped.py: load a page and ask Chromium what is on screen."""
import re

WORD = re.compile(r"\w+")

# Text a person can reach, according to the browser's own layout. Colour is deliberately not judged
# here, so that a colour mistake in seenonly shows up as dropped text.
SHOWN_JS = """() => {
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  const clippedAway = (el) => {
    for (let p = el; p && p !== document.documentElement; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.overflow !== 'visible' && (p.clientWidth <= 1 || p.clientHeight <= 1)) return true;
      if (s.position === 'absolute' && /rect\\(0/.test(s.clip)) return true;
      if (/inset\\((50|100)%/.test(s.clipPath)) return true;
      if (s.transform && /matrix\\(0, 0, 0, 0/.test(s.transform)) return true;
    }
    return false;
  };
  while (w.nextNode()) {
    const n = w.currentNode;
    if (!n.data.trim()) continue;
    const el = n.parentElement;
    if (!el || ['SCRIPT','STYLE','NOSCRIPT','TEMPLATE'].includes(el.tagName)) continue;
    if (!el.checkVisibility({opacityProperty: true, visibilityProperty: true})) continue;
    if (parseFloat(getComputedStyle(el).fontSize) <= 1) continue;
    range.selectNodeContents(n);
    const seen = [...range.getClientRects()].some(r =>
      r.width > 1 && r.height > 1 && r.right + scrollX > 0 && r.bottom + scrollY > 0);
    if (seen && !clippedAway(el)) out.push(n.data);
  }
  return out.join(' ');
}"""


def load(ctx, url):
    """(what the browser shows, the DOM, the stylesheets that apply to a screen)."""
    page = ctx.new_page()
    bodies = {}

    def keep(resp):
        try:
            if resp.request.resource_type == "stylesheet" and resp.ok:
                bodies[resp.url] = resp.text()
        except Exception:
            pass

    page.on("response", keep)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)
        shown = page.evaluate(SHOWN_JS)
        dom = page.content()
        # A file loaded for print or dark mode must carry that condition with it.
        media = page.evaluate("[...document.styleSheets].filter(s => s.href).map(s => [s.href, s.media.mediaText, s.disabled])")
    finally:
        page.close()
    known = {href: (m, off) for href, m, off in media}
    css = []
    for href, body in bodies.items():
        m, off = known.get(href, ("", False))
        if not off:
            css.append(f"@media {m} {{\n{body}\n}}" if m else body)
    return shown, dom, "\n".join(css)
