"""What a person sees on a page, and a report of everything else."""
from __future__ import annotations

import html as html_lib
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from .chars import clean_chars
from .css import (Color, Sheet, blend, contrast, length_px, media_applies, parse_color, parse_declarations, split_top)
from .dom import Comment, Document, Element, Text, VOID, parse
from .phrases import detect, strip_sentences

NOT_RENDERED = {
    "head-only": {"title", "meta", "link", "base", "style", "script"},
    "fallback": {"noscript", "noframes", "noembed", "iframe", "object", "embed", "applet", "audio", "video", "canvas",
                 "frame", "frameset", "datalist", "template", "param", "source", "track", "area", "map"},
    "svg": {"desc", "metadata", "defs", "symbol", "clippath", "mask", "pattern", "lineargradient", "radialgradient",
            "filter", "marker"},
}
_DROP = NOT_RENDERED["head-only"] | NOT_RENDERED["fallback"] | NOT_RENDERED["svg"]
BLOCK = {
    "address", "article", "aside", "blockquote", "body", "br", "caption", "center", "dd", "details", "dialog", "dir",
    "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hgroup", "hr", "html", "legend", "li", "main", "menu", "nav", "ol", "option", "p", "pre", "section",
    "summary", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
}
# width and height do nothing to these unless display or position changes them.
INLINE = {"a", "abbr", "b", "bdi", "bdo", "cite", "code", "data", "dfn", "em", "font", "i", "kbd", "mark", "q", "s",
          "samp", "small", "span", "strong", "sub", "sup", "time", "tt", "u", "var"}
# Utility classes that mean "hidden" in Tailwind, Bootstrap and WordPress, for when the stylesheet
# is external and cannot be read. Anything in a stylesheet we can read overrides this.
HIDDEN_CLASSES = {"hidden", "invisible", "d-none", "sr-only", "visually-hidden", "visuallyhidden", "screen-reader-text",
                  "screen-reader-only", "opacity-0", "is-hidden", "u-hidden", "hide", "element-invisible"}
_SHOWN_AT_SOME_WIDTH = re.compile(r"^(?:(?:sm|md|lg|xl|2xl):(?:block|flex|inline|inline-block|grid|table)|d-(?:sm|md|lg|xl|xxl)-(?:block|flex|inline|inline-block|grid|table))$")
_SCANNED_ATTRS = {"alt", "title", "aria-label", "aria-description", "placeholder", "summary", "label", "value", "content"}
_PICTURES = {"img", "picture", "video", "canvas", "svg", "iframe", "object", "embed"}
_OFF = -500.0  # px: past this, text left of the page is out of reach
_OFF_RIGHT = 5000.0
_FONT_SIZES = {"xx-small": 9.0, "x-small": 10.0, "small": 13.0, "medium": 16.0, "large": 18.0, "x-large": 24.0,
               "xx-large": 32.0, "xxx-large": 48.0}
_MIN_CONTRAST = 1.10
_BLACK: Color = (0.0, 0.0, 0.0, 1.0)
_WHITE: Color = (255.0, 255.0, 255.0, 1.0)


@dataclass
class Finding:
    """One thing that was on the page but is not in the text a person sees."""
    kind: str        # hidden, maybe_hidden, comment, metadata, attribute, unicode, injection
    reason: str      # "display:none", "white on white", "override"...
    text: str        # what it said, cut to 300 characters
    location: str = ""
    injection: bool = False  # it also reads like an instruction to an AI

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Result:
    text: str
    html: str
    title: str = ""
    description: str = ""
    findings: List[Finding] = field(default_factory=list)
    external_css: bool = False  # the page links stylesheets that were not given to clean()

    @property
    def suspicious(self) -> List[Finding]:
        """The findings worth a human's attention. Ordinary pages have hidden menus; these are attacks."""
        return [f for f in self.findings if f.injection]

    def to_dict(self) -> dict:
        return {"text": self.text, "title": self.title, "description": self.description,
                "external_css": self.external_css, "findings": [f.to_dict() for f in self.findings]}


class _Ctx:
    """What an element inherits."""
    __slots__ = ("vars", "visibility", "color", "color_known", "text_fill", "fill", "font", "indent", "bg", "bg_sure",
                 "clip_text", "positioned", "svg")

    def __init__(self):
        self.vars: Dict[str, str] = {}
        self.visibility = "visible"
        self.color: Optional[Color] = _BLACK
        self.color_known = False
        self.text_fill: Optional[str] = None
        self.fill: Optional[str] = None
        self.font = 16.0
        self.indent = 0.0
        self.bg: Optional[Color] = _WHITE
        self.bg_sure = True
        self.clip_text = False
        self.positioned = False  # an ancestor is the containing block, not the page
        self.svg = False

    def child(self) -> "_Ctx":
        c = _Ctx.__new__(_Ctx)
        for s in _Ctx.__slots__:
            setattr(c, s, getattr(self, s))
        return c


def _resolve_var(value: str, vars_: Dict[str, str], depth: int = 0) -> Optional[str]:
    """Replace var(--x, fallback). None if the variable has no value: the declaration is then void."""
    if "var(" not in value.lower():
        return value
    if depth > 8:
        return None
    m = re.search(r"var\(", value, re.I)
    start = m.start()  # type: ignore[union-attr]
    i, level = m.end(), 1  # type: ignore[union-attr]
    while i < len(value) and level:
        if value[i] == "(":
            level += 1
        elif value[i] == ")":
            level -= 1
        i += 1
    inner = value[m.end():i - 1]  # type: ignore[union-attr]
    name, sep, fallback = inner.partition(",")
    got = vars_.get(name.strip())
    if got is None:
        if not sep:
            return None
        got = fallback.strip()
    got = _resolve_var(got, vars_, depth + 1)
    if got is None:
        return None
    return _resolve_var(value[:start] + got + value[i:], vars_, depth + 1)


def _expand(name: str, value: str) -> List[Tuple[str, str]]:
    """Longhands of the shorthands that can hide text."""
    if name == "background":
        low = value.lower()
        if low in ("inherit", "initial", "unset", "revert", "none"):
            return [("background-color", low if low != "none" else "transparent"), ("background-image", "none")]
        color = "transparent"
        image = "none"
        for tok in split_top(low.replace(",", " , "), " "):
            tok = tok.strip()
            if not tok:
                continue
            if tok.startswith(("url(", "image(", "image-set(")) or "gradient(" in tok:
                image = tok
            elif parse_color(tok) is not None or tok == "currentcolor" or tok.startswith(("color-mix", "light-dark")):
                color = tok
        return [("background-color", color), ("background-image", image)]
    if name == "font":
        m = re.search(r"(?:^|\s)((?:[-+]?[\d.]+[a-z%]*|xx-small|x-small|small|medium|large|x-large|xx-large|xxx-large|calc\([^)]*\)))(?:\s*/\s*\S+)?\s+[^\s]", value, re.I)
        return [("font-size", m.group(1))] if m else []
    if name == "inset":
        vals = split_top(value, " ")
        vals = [v for v in vals if v.strip()]
        if len(vals) == 1:
            vals = vals * 4
        elif len(vals) == 2:
            vals = [vals[0], vals[1], vals[0], vals[1]]
        elif len(vals) == 3:
            vals = [vals[0], vals[1], vals[2], vals[1]]
        return list(zip(("top", "right", "bottom", "left"), vals)) if len(vals) >= 4 else []
    if name == "overflow":
        return [("overflow-x", value.split()[0]), ("overflow-y", value.split()[-1])]
    if name == "-webkit-background-clip":
        return [("background-clip", value)]
    return [(name, value)]


class _Styler:
    def __init__(self, sheet: Sheet, quirks: bool):
        self.sheet, self.quirks = sheet, quirks
        self.cache: Dict[int, Dict[str, str]] = {}

    def hints(self, el: Element, in_svg: bool) -> List[Tuple[str, str]]:
        """What the browser's own stylesheet and old HTML attributes say. Any author CSS beats these."""
        a = el.attrs
        out: List[Tuple[str, str]] = []
        if "hidden" in a or (el.tag == "dialog" and "open" not in a) or (el.tag == "input" and a.get("type", "").lower() == "hidden"):
            out.append(("display", "none"))
        if "popover" in a:
            out.append(("display", "none"))
        if el.classes and any(c.lower() in HIDDEN_CLASSES for c in el.classes):
            if not any(_SHOWN_AT_SOME_WIDTH.match(c) for c in el.classes):
                out.append(("display", "none"))
        if el.tag == "font":
            if "color" in a:
                out.append(("color", a["color"]))
        if el.tag == "body" and "text" in a:
            out.append(("color", a["text"]))
        if "bgcolor" in a:
            out.append(("background-color", a["bgcolor"]))
        if "background" in a and el.tag in ("body", "table", "td", "th", "tr"):
            out.append(("background-image", "url()"))
        for name in ("width", "height"):
            if name in a and el.tag in ("svg", "table", "td", "th", "div"):
                if el.tag == "svg":
                    out.append((name, a[name]))
        for name in ("display", "visibility", "opacity", "fill", "fill-opacity", "font-size", "clip-path", "transform"):
            if name in a and in_svg:
                out.append((name, a[name]))
        return out

    def layered(self, el: Element, in_svg: bool) -> bool:
        if self.sheet.has_painted_pseudo(el, self.quirks):
            return True
        for k in el.kids:
            st = self.computed(k, in_svg)
            if st.get("position", "").lower() in ("absolute", "fixed") and (
                    k.tag in _PICTURES or "background-color" in st or st.get("background-image", "none") != "none"):
                return True
        return False

    def computed(self, el: Element, in_svg: bool) -> Dict[str, str]:
        got = self.cache.get(id(el))
        if got is None:
            got = self.cache[id(el)] = self._computed(el, in_svg)
        return got

    def _computed(self, el: Element, in_svg: bool) -> Dict[str, str]:
        best: Dict[str, Tuple[tuple, str]] = {}

        def put(name: str, value: str, key: tuple) -> None:
            for n, v in _expand(name, value) if not name.startswith("--") else [(name, value)]:
                if n not in best or key >= best[n][0]:
                    best[n] = (key, v)

        for name, value in self.hints(el, in_svg):
            put(name, value, (0, 0, (0, 0, 0), 0))
        for rule in self.sheet.matching(el, self.quirks):
            for name, value, imp in rule.decls:
                put(name, value, (1 if imp else 0, 1, rule.sel.spec, rule.order))
        if "style" in el.attrs:
            for i, (name, value, imp) in enumerate(parse_declarations(el.attrs["style"])):
                put(name, value, (1 if imp else 0, 2, (0, 0, 0), i))
        return {k: v[1] for k, v in best.items()}


def _font_px(value: str, parent: float) -> float:
    v = value.strip().lower()
    if v in ("inherit", "unset", "revert", "revert-layer"):
        return parent
    if v == "initial":
        return 16.0
    if v in _FONT_SIZES:
        return _FONT_SIZES[v]
    if v == "smaller":
        return parent * 0.83
    if v == "larger":
        return parent * 1.2
    px = length_px(v, parent, parent)
    return parent if px is None or px < 0 else px


def _color_value(value: str, ctx: _Ctx) -> Tuple[Optional[Color], bool]:
    """(colour, whether it is known)."""
    v = value.strip().lower()
    if v in ("inherit", "unset", "revert", "revert-layer"):
        return ctx.color, ctx.color_known
    if v == "currentcolor":
        return ctx.color, ctx.color_known
    if v == "initial":
        return _BLACK, True
    m = re.fullmatch(r"light-dark\(\s*(.*?)\s*,.*\)", v, re.S)
    if m:
        v = m.group(1)
    c = parse_color(v)
    return (c, True) if c is not None else (None, False)


def _hidden_by_style(el: Element, st: Dict[str, str], font: float, in_positioned: bool) -> Optional[str]:
    """Why this element and all it contains cannot be seen, or None."""
    display = st.get("display", "").lower()
    if display == "none":
        return "display:none"
    if display == "contents":
        return None
    op = st.get("opacity", "").strip().lower()
    if op and op not in ("inherit", "initial", "unset", "revert", "revert-layer"):
        v = length_px(op, percent_of=1.0)
        if v is not None and v <= 0.02:
            return f"opacity:{op}"
    if st.get("content-visibility", "").lower() == "hidden":
        return "content-visibility:hidden"

    pos = st.get("position", "").lower()
    if pos in ("absolute", "fixed", "relative"):
        for side in ("left", "top", "right", "bottom"):
            if side in st:
                # A percentage is of the containing block: the page, unless a positioned ancestor
                # takes that role. "left:-100%" in a small box is a tooltip beside it.
                px = length_px(st[side], font, None if in_positioned or side not in ("left", "right") else 1280.0)
                if px is None:
                    continue
                # Past the left or top edge is out of reach for good; past the right edge a page can
                # scroll, so that takes much further.
                if (side in ("left", "top") and px <= _OFF) or (side in ("right", "bottom") and px <= _OFF * 2):
                    return f"{side}:{st[side]}"
                if side == "left" and px >= _OFF_RIGHT:
                    return f"{side}:{st[side]}"
        clip = st.get("clip", "").lower().replace(",", " ")
        m = re.fullmatch(r"rect\(\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*\)", clip)
        if m and pos != "relative":
            top, right, bottom, left = (length_px(x, font) for x in m.groups())
            if None not in (top, right, bottom, left) and (bottom - top <= 1 or right - left <= 1):  # type: ignore[operator]
                return "clip:rect"
    for side in ("margin-left", "margin-top"):
        if side in st:  # a percentage here is a layout trick (Sphinx sidebars): it stays unknown
            px = length_px(st[side], font)
            if px is not None and px <= _OFF * 2:
                return f"{side}:{st[side]}"

    cp = st.get("clip-path", "").lower()
    if cp:
        m = re.match(r"inset\(\s*([-\d.]+)(%|px)?", cp)
        if m and m.group(2) == "%" and float(m.group(1)) >= 50:
            return f"clip-path:{cp}"
        if re.match(r"circle\(\s*0(?:px|%)?\b", cp) or re.match(r"ellipse\(\s*0(?:px|%)?\b", cp):
            return f"clip-path:{cp}"
        if cp.startswith("polygon(") and len({p.strip() for p in cp[8:-1].split(",")}) == 1:
            return f"clip-path:{cp}"

    reason = _hidden_by_transform(st, font)
    if reason:
        return reason
    fl = st.get("filter", "").lower()
    if re.search(r"opacity\(\s*0*(?:\.0*)?%?\s*\)", fl):
        return f"filter:{fl}"

    zoom = st.get("zoom", "").strip()
    if zoom:
        v = length_px(zoom, percent_of=1.0)
        if v is not None and 0 < v <= 0.05:
            return f"zoom:{zoom}"

    ox, oy = st.get("overflow-x", "").lower(), st.get("overflow-y", "").lower()
    if {ox, oy} & {"hidden", "clip"}:
        # Image replacement, the other direction: the text starts past the right edge of its box.
        indent = st.get("text-indent", "").strip().lower()
        if ox in ("hidden", "clip") and st.get("white-space", "").lower() in ("nowrap", "pre"):
            if indent.endswith("%") and (length_px(indent, percent_of=1.0) or 0) >= 1:
                return f"text-indent:{indent} with overflow:hidden"
        boxy = el.tag not in INLINE or pos in ("absolute", "fixed") or display not in ("", "inline")
        if boxy:
            for name, axis in (("width", ox), ("height", oy), ("max-width", ox), ("max-height", oy)):
                if name in st and axis in ("hidden", "clip"):
                    px = length_px(st[name], font, 1280.0)
                    if px is not None and px <= 1:
                        return f"{name}:{st[name]} with overflow:hidden"
    if el.tag == "svg":
        for name in ("width", "height"):
            if name in st:
                px = length_px(st[name], font, 1280.0)
                if px is not None and px <= 0:
                    return f"svg {name}:0"
    return None


def _hidden_by_transform(st: Dict[str, str], font: float) -> Optional[str]:
    tr = st.get("transform", "").lower()
    for fn, arg in re.findall(r"([a-z0-9]+)\(([^()]*(?:\([^()]*\)[^()]*)*)\)", tr):
        args = [a.strip() for a in arg.replace(",", " ").split()] if "calc" not in arg else [a.strip() for a in arg.split(",")]
        if fn in ("scale", "scalex", "scaley", "scale3d") and args:
            nums = [length_px(a, percent_of=1.0) for a in args]
            if fn == "scale3d":
                nums = nums[:2]
            if any(n is not None and abs(n) < 0.01 for n in nums):
                return f"transform:{fn}(0)"
        elif fn == "matrix" and len(args) == 6:
            a, b, c, d = (length_px(x) for x in args[:4])
            if None not in (a, b, c, d) and abs(a * d - b * c) < 1e-4:  # type: ignore[operator]
                return "transform:matrix(0)"
        elif fn in ("translate", "translatex", "translatey", "translate3d") and args:
            for a in args[:2]:
                px = length_px(a, font)  # a percentage stays unknown: slide-in drawers use -100%
                if px is not None and px <= _OFF * 2:
                    return f"transform:{fn}({a})"
        elif fn in ("rotatex", "rotatey") and args:
            m = re.fullmatch(r"([-\d.]+)deg", args[0])
            if m and abs(float(m.group(1))) % 180 == 90:
                return f"transform:{fn}(90deg)"
    sc = st.get("scale", "").strip().lower()
    if sc and re.fullmatch(r"0+(?:\.0+)?%?(?:\s.*)?", sc):
        return "scale:0"
    tl = st.get("translate", "").strip().lower()
    if tl:
        for a in tl.split()[:2]:
            px = length_px(a, font)
            if px is not None and px <= _OFF * 2:
                return f"translate:{a}"
    return None


def _apply(ctx: _Ctx, st: Dict[str, str]) -> None:
    """Move the inherited values down one element."""
    if "visibility" in st:
        v = st["visibility"].lower()
        if v == "initial":
            ctx.visibility = "visible"
        elif v not in ("inherit", "unset", "revert", "revert-layer"):
            ctx.visibility = v
    if "font-size" in st:
        ctx.font = _font_px(st["font-size"], ctx.font)
    if "text-indent" in st:
        v = st["text-indent"].lower()
        if v == "initial":
            ctx.indent = 0.0
        elif v not in ("inherit", "unset", "revert", "revert-layer"):
            px = length_px(v, ctx.font, 1280.0)
            ctx.indent = px if px is not None else 0.0
    if "color" in st:
        ctx.color, ctx.color_known = _color_value(st["color"], ctx)
    if "-webkit-text-fill-color" in st:
        ctx.text_fill = st["-webkit-text-fill-color"]
    if "fill" in st:
        ctx.fill = st["fill"]

    image = st.get("background-image", "none").lower()
    has_image = image not in ("none", "initial", "unset", "")
    clip = st.get("background-clip", "").lower()
    if clip == "text":
        ctx.clip_text = has_image or ctx.clip_text
    elif has_image:
        ctx.bg, ctx.bg_sure = None, False
    # inherit paints the parent's colour again: over that same colour, it changes nothing.
    if "background-color" in st and clip != "text" and st["background-color"].strip().lower() not in (
            "inherit", "initial", "unset", "revert", "revert-layer"):
        c, known = _color_value(st["background-color"], ctx)
        if not known or c is None:
            ctx.bg, ctx.bg_sure = None, False
        elif not has_image and ctx.bg is not None:
            ctx.bg = blend(c, ctx.bg)
            if c[3] >= 0.99:
                ctx.bg_sure = True
        elif not has_image and c[3] >= 0.99:
            ctx.bg, ctx.bg_sure = c, True
    # Taken out of the flow, it can sit over anything, so what is under it is no longer known.
    if st.get("position", "").lower() in ("absolute", "fixed") and "background-color" not in st:
        ctx.bg_sure = False


def _hex(c: Optional[Color]) -> str:
    if c is None:
        return "?"
    return "#%02x%02x%02x" % (int(c[0]), int(c[1]), int(c[2]))


def _text_verdict(ctx: _Ctx, in_svg: bool) -> Tuple[Optional[str], Optional[str]]:
    """(why this text cannot be seen, why it perhaps cannot be seen)."""
    if ctx.visibility in ("hidden", "collapse"):
        return "visibility:" + ctx.visibility, None
    if ctx.font <= 1.0:
        return f"font-size:{ctx.font:g}px", None
    if ctx.indent <= _OFF:
        return f"text-indent:{ctx.indent:g}px", None
    if ctx.clip_text:
        return None, None
    color, known = ctx.color, ctx.color_known
    if in_svg and ctx.fill is not None:
        fill = ctx.fill.strip().lower()
        if fill == "none":
            return "fill:none", None
        c = parse_color(fill)
        color, known = (c, True) if c is not None else (None, False)
    if ctx.text_fill is not None:
        c, k = _color_value(ctx.text_fill, ctx)
        if c is not None:
            color, known = c, k
    if color is None:
        return None, None
    if color[3] <= 0.02:
        return "transparent text", None
    if not known:
        return None, None
    if ctx.bg is None:  # the background is unknown: only worth a note, against a page's usual white
        if contrast(blend(color, _WHITE), _WHITE) < _MIN_CONTRAST:
            return None, f"{_hex(color)} text, background unknown"
        return None, None
    painted = blend(color, ctx.bg)
    if contrast(painted, ctx.bg) < _MIN_CONTRAST:
        reason = f"{_hex(painted)} text on {_hex(ctx.bg)}"
        return (reason, None) if ctx.bg_sure else (None, reason)
    return None, None


def _snippet(s: str) -> str:
    s = " ".join(s.split())
    return s if len(s) <= 300 else s[:297] + "..."


def _all_text(el: Element) -> str:
    out: List[str] = []
    stack: List[object] = [el]
    while stack:
        n = stack.pop()
        if isinstance(n, Text):
            out.append(n.data)
        elif isinstance(n, Element):
            stack.extend(reversed(n.children))
    return " ".join(out)


class _Run:
    __slots__ = ("nodes",)

    def __init__(self):
        self.nodes: List[Text] = []


def clean(page: str, *, phrases: str = "remove", css: str = "") -> Result:
    """Keep only what a person sees on this HTML page.

    phrases: "remove" also drops visible sentences written as instructions to an AI,
             "flag" reports them but keeps them, "off" does not look.
    css: stylesheets the page links to, if you have them. Without them, hiding done only by an
         external stylesheet can be missed; Result.external_css says when that may have happened.
    """
    if phrases not in ("remove", "flag", "off"):
        raise ValueError('phrases must be "remove", "flag" or "off"')
    doc: Document = parse(page)
    findings: List[Finding] = []

    sheet = Sheet()
    external = False
    for el in doc.root.walk():
        if el.tag == "style" and media_applies(el.attrs.get("media", "")):
            sheet.add_css("".join(c.data for c in el.children if isinstance(c, Text)))
        elif el.tag == "link":
            rel = el.attrs.get("rel", "").lower().split()
            if "stylesheet" in rel and "alternate" not in rel and media_applies(el.attrs.get("media", "")):
                external = True
    if sheet.has_import:
        external = True
    if css:
        sheet.add_css(css)
    unseen_css = external and not css

    styler = _Styler(sheet, quirks=not doc.has_doctype)
    root = _Ctx()
    if unseen_css:
        # The colours may come from a file we did not see: nothing can be concluded from them.
        root.bg, root.bg_sure = None, False

    title = ""
    description = ""
    blocks: List[_Run] = [_Run()]
    removed: set = set()
    stack: List[Tuple[object, Optional[_Ctx]]] = [(c, root) for c in reversed(doc.root.children)]

    def scan(text: str, kind: str, location: str) -> None:
        hit = detect(clean_chars(text)[0])
        if hit:
            findings.append(Finding(kind, hit, _snippet(text), location, True))

    def report_hidden(el: Element, reason: str) -> None:
        said = _all_text(el)
        if said.strip():
            cleaned, _ = clean_chars(said)
            findings.append(Finding("hidden", reason, _snippet(cleaned), el.path(), detect(cleaned) is not None))

    while stack:
        node, ctx = stack.pop()
        if ctx is None:  # the end of a block element
            assert isinstance(node, Element)
            if blocks[-1].nodes:
                blocks.append(_Run())
            continue
        if isinstance(node, Comment):
            scan(node.data, "comment", node.parent.path() or "document")
            removed.add(id(node))
            continue
        if isinstance(node, Text):
            data, hid = clean_chars(node.data)
            node.data = data
            for reason, payload in hid:
                findings.append(Finding("unicode", reason, _snippet(payload), node.parent.path(),
                                        detect(payload) is not None or reason in ("unicode tag characters", "variation selector smuggling")))
            if not data.strip():
                blocks[-1].nodes.append(node)
                continue
            sure, maybe = _text_verdict(ctx, ctx.svg)
            if sure:
                findings.append(Finding("hidden", sure, _snippet(data), node.parent.path(), detect(data) is not None))
                removed.add(id(node))
                continue
            if maybe:
                findings.append(Finding("maybe_hidden", maybe, _snippet(data), node.parent.path(), detect(data) is not None))
            blocks[-1].nodes.append(node)
            continue
        assert isinstance(node, Element)
        el = node

        if el.tag == "title" and not title and not ctx.svg:
            title = " ".join(clean_chars(_all_text(el))[0].split())
        if el.tag == "meta":
            name = (el.attrs.get("name") or el.attrs.get("property") or "").lower()
            content = el.attrs.get("content", "")
            if name in ("description", "og:description", "twitter:description") and not description:
                description = " ".join(clean_chars(content)[0].split())
            if content:
                scan(content, "metadata", f"meta {name}".strip())
        if el.tag == "script" and "ld+json" in el.attrs.get("type", "").lower():
            scan(_all_text(el), "metadata", "script " + el.attrs.get("type", ""))
        # An <object> with nothing to load shows what is inside it. With a file it does not, and
        # whether the file loads cannot be known from here, so that text goes.
        empty_object = el.tag == "object" and not el.attrs.get("data", "").strip()
        if el.tag in _DROP and not empty_object:
            if el.tag not in NOT_RENDERED["head-only"]:
                scan(_all_text(el), "hidden", el.path())
            removed.add(id(el))
            continue

        st = styler.computed(el, ctx.svg or el.tag == "svg")
        cc = ctx.child()
        customs = {n: v for n, v in st.items() if n.startswith("--")}
        if customs:
            # var() resolves on the element that declares it; the result is what its children
            # inherit. A later change of --a further down does not alter --b: var(--a) up here.
            scope = {**ctx.vars, **customs}
            cc.vars = dict(ctx.vars)
            for name, value in customs.items():
                r = _resolve_var(value, scope)
                if r is None:
                    cc.vars.pop(name, None)
                else:
                    cc.vars[name] = r
        resolved: Dict[str, str] = {}
        for name, value in st.items():
            if name.startswith("--"):
                continue
            r = _resolve_var(value, cc.vars)
            if r is not None:
                for n, v in _expand(name, r):
                    resolved[n] = v
        # font-size first: em units in this element's own declarations use it.
        font = _font_px(resolved["font-size"], ctx.font) if "font-size" in resolved else ctx.font
        why = _hidden_by_style(el, resolved, font, ctx.positioned)
        if why:
            report_hidden(el, why)
            removed.add(id(el))
            continue
        _apply(cc, resolved)
        # Something else may be painted behind this text: a picture, a layer beside it, a ::before.
        # Then its colours prove nothing, and it is only noted.
        if styler.layered(el, cc.svg or el.tag == "svg"):
            cc.bg_sure = False
        if el.tag == "svg":
            cc.svg = True
        if resolved.get("position", "").lower() in ("absolute", "fixed", "relative", "sticky"):
            cc.positioned = True

        for attr, value in list(el.attrs.items()):
            if (attr in _SCANNED_ATTRS or attr.startswith("data-")) and value and el.tag != "meta":
                hit = detect(clean_chars(value)[0])
                if hit:
                    findings.append(Finding("attribute", f"{attr}: {hit}", _snippet(value), el.path(), True))
                    if phrases == "remove":
                        del el.attrs[attr]

        is_block = el.tag in BLOCK or resolved.get("display", "").lower() in ("block", "flex", "grid", "table", "list-item", "flow-root")
        if is_block:
            if blocks[-1].nodes:
                blocks.append(_Run())
            stack.append((el, None))
        if el.tag == "br":
            continue
        stack.extend((c, cc) for c in reversed(el.children))

    for el in doc.root.walk():
        if any(id(c) in removed for c in el.children):
            el.children = [c for c in el.children if id(c) not in removed]

    lines: List[str] = []
    for run in blocks:
        joined = " ".join("".join(n.data for n in run.nodes).split())
        if not joined:
            continue
        if phrases != "off":
            kept, hits = strip_sentences(joined)
            if hits:
                where = run.nodes[0].parent.path()
                for label, sentence in hits:
                    findings.append(Finding("injection", label, _snippet(sentence), where, True))
                if phrases == "remove":
                    # The sentence may cross inline tags, so the block's text goes back as one piece.
                    live = [n for n in run.nodes if n.data.strip()]
                    for n in live:
                        n.data = ""
                    if live:
                        live[0].data = kept
                    joined = " ".join(kept.split())
        if joined:
            lines.append(joined)

    if description and phrases == "remove" and detect(description):
        description = ""
    if title and phrases == "remove" and detect(title):
        findings.append(Finding("injection", detect(title) or "", _snippet(title), "title", True))
        title = ""
    return Result(text="\n".join(lines), html=_serialize(doc.root), title=title, description=description,
                  findings=findings, external_css=unseen_css)


def stylesheet_links(page: str, base_url: str = "") -> List[str]:
    """The stylesheets a page links for a screen, in order. Fetch them and pass them as css=.

    This library opens no connections. If you fetch what a stranger's page links to, guard against
    private addresses and large responses as you would for the page itself.
    """
    out: List[str] = []
    for el in parse(page).root.walk():
        if el.tag == "link" and el.attrs.get("href"):
            rel = el.attrs.get("rel", "").lower().split()
            if "stylesheet" in rel and "alternate" not in rel and media_applies(el.attrs.get("media", "")):
                out.append(urljoin(base_url, el.attrs["href"]))
    return out


def clean_text(text: str, *, phrases: str = "remove") -> Result:
    """The same for text that is not HTML: search snippets, API results, documents, tool output."""
    if phrases not in ("remove", "flag", "off"):
        raise ValueError('phrases must be "remove", "flag" or "off"')
    cleaned, hid = clean_chars(text)
    findings = [Finding("unicode", reason, _snippet(p), "", detect(p) is not None or reason != "run of zero-width characters")
                for reason, p in hid]
    if phrases != "off":
        out: List[str] = []
        for line in cleaned.split("\n"):
            kept, hits = strip_sentences(line)
            for label, sentence in hits:
                findings.append(Finding("injection", label, _snippet(sentence), "", True))
            out.append(kept if phrases == "remove" else line)
        cleaned = "\n".join(out)
    return Result(text=cleaned, html="", findings=findings)


def _serialize(root: Element) -> str:
    """The page without what was removed. Not an XSS sanitizer: scripts are gone, event handlers are not."""
    out: List[str] = []
    stack: List[object] = list(reversed(root.children))
    while stack:
        n = stack.pop()
        if isinstance(n, str):
            out.append(n)
        elif isinstance(n, Text):
            out.append(html_lib.escape(n.data, quote=False))
        elif isinstance(n, Element):
            attrs = "".join(f' {k}="{html_lib.escape(v)}"' for k, v in n.attrs.items())
            out.append(f"<{n.tag}{attrs}>")
            if n.tag not in VOID:
                stack.append(f"</{n.tag}>")
                stack.extend(reversed(n.children))
    return "".join(out)
