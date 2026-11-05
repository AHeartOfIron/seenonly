"""Just enough CSS to know what is hidden: values, colours, selectors, media queries, the cascade.

The goal is narrow. It does not lay out a page. It answers "which declaration wins for this
property on this element", and it reads a value the way a browser would, including the forms
an attacker can pick to get past a simple check: escapes, var(), calc(), modern colour spaces.
"""
from __future__ import annotations

import base64
import binascii
import math
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

from .dom import Element

# Declarations about anything else are dropped at parse time: this keeps large stylesheets fast.
RELEVANT = {
    "display", "visibility", "opacity", "font", "font-size", "color", "-webkit-text-fill-color", "background",
    "background-color", "background-image", "background-clip", "-webkit-background-clip", "position", "left", "right",
    "top", "bottom", "text-indent", "width", "height", "max-width", "max-height", "overflow", "overflow-x",
    "overflow-y", "clip", "clip-path", "transform", "translate", "scale", "content-visibility", "filter", "fill",
    "fill-opacity", "margin-left", "margin-top", "inset", "zoom", "white-space", "flex", "flex-grow", "padding",
    "padding-top", "padding-bottom", "padding-left", "padding-right", "backface-visibility", "-webkit-backface-visibility",
}
VIEWPORT_W, VIEWPORT_H = 1280, 800
ROOT_FONT = 16.0

NAMED = dict(
    black=0x000000, silver=0xc0c0c0, gray=0x808080, grey=0x808080, white=0xffffff, maroon=0x800000, red=0xff0000,
    purple=0x800080, fuchsia=0xff00ff, magenta=0xff00ff, green=0x008000, lime=0x00ff00, olive=0x808000,
    yellow=0xffff00, navy=0x000080, blue=0x0000ff, teal=0x008080, aqua=0x00ffff, cyan=0x00ffff, orange=0xffa500,
    aliceblue=0xf0f8ff, antiquewhite=0xfaebd7, aquamarine=0x7fffd4, azure=0xf0ffff, beige=0xf5f5dc, bisque=0xffe4c4,
    blanchedalmond=0xffebcd, blueviolet=0x8a2be2, brown=0xa52a2a, burlywood=0xdeb887, cadetblue=0x5f9ea0,
    chartreuse=0x7fff00, chocolate=0xd2691e, coral=0xff7f50, cornflowerblue=0x6495ed, cornsilk=0xfff8dc,
    crimson=0xdc143c, darkblue=0x00008b, darkcyan=0x008b8b, darkgoldenrod=0xb8860b, darkgray=0xa9a9a9,
    darkgreen=0x006400, darkgrey=0xa9a9a9, darkkhaki=0xbdb76b, darkmagenta=0x8b008b, darkolivegreen=0x556b2f,
    darkorange=0xff8c00, darkorchid=0x9932cc, darkred=0x8b0000, darksalmon=0xe9967a, darkseagreen=0x8fbc8f,
    darkslateblue=0x483d8b, darkslategray=0x2f4f4f, darkslategrey=0x2f4f4f, darkturquoise=0x00ced1,
    darkviolet=0x9400d3, deeppink=0xff1493, deepskyblue=0x00bfff, dimgray=0x696969, dimgrey=0x696969,
    dodgerblue=0x1e90ff, firebrick=0xb22222, floralwhite=0xfffaf0, forestgreen=0x228b22, gainsboro=0xdcdcdc,
    ghostwhite=0xf8f8ff, gold=0xffd700, goldenrod=0xdaa520, greenyellow=0xadff2f, honeydew=0xf0fff0, hotpink=0xff69b4,
    indianred=0xcd5c5c, indigo=0x4b0082, ivory=0xfffff0, khaki=0xf0e68c, lavender=0xe6e6fa, lavenderblush=0xfff0f5,
    lawngreen=0x7cfc00, lemonchiffon=0xfffacd, lightblue=0xadd8e6, lightcoral=0xf08080, lightcyan=0xe0ffff,
    lightgoldenrodyellow=0xfafad2, lightgray=0xd3d3d3, lightgreen=0x90ee90, lightgrey=0xd3d3d3, lightpink=0xffb6c1,
    lightsalmon=0xffa07a, lightseagreen=0x20b2aa, lightskyblue=0x87cefa, lightslategray=0x778899,
    lightslategrey=0x778899, lightsteelblue=0xb0c4de, lightyellow=0xffffe0, limegreen=0x32cd32, linen=0xfaf0e6,
    mediumaquamarine=0x66cdaa, mediumblue=0x0000cd, mediumorchid=0xba55d3, mediumpurple=0x9370db,
    mediumseagreen=0x3cb371, mediumslateblue=0x7b68ee, mediumspringgreen=0x00fa9a, mediumturquoise=0x48d1cc,
    mediumvioletred=0xc71585, midnightblue=0x191970, mintcream=0xf5fffa, mistyrose=0xffe4e1, moccasin=0xffe4b5,
    navajowhite=0xffdead, oldlace=0xfdf5e6, olivedrab=0x6b8e23, orangered=0xff4500, orchid=0xda70d6,
    palegoldenrod=0xeee8aa, palegreen=0x98fb98, paleturquoise=0xafeeee, palevioletred=0xdb7093, papayawhip=0xffefd5,
    peachpuff=0xffdab9, peru=0xcd853f, pink=0xffc0cb, plum=0xdda0dd, powderblue=0xb0e0e6, rebeccapurple=0x663399,
    rosybrown=0xbc8f8f, royalblue=0x4169e1, saddlebrown=0x8b4513, salmon=0xfa8072, sandybrown=0xf4a460,
    seagreen=0x2e8b57, seashell=0xfff5ee, sienna=0xa0522d, skyblue=0x87ceeb, slateblue=0x6a5acd, slategray=0x708090,
    slategrey=0x708090, snow=0xfffafa, springgreen=0x00ff7f, steelblue=0x4682b4, tan=0xd2b48c, thistle=0xd8bfd8,
    tomato=0xff6347, turquoise=0x40e0d0, violet=0xee82ee, wheat=0xf5deb3, whitesmoke=0xf5f5f5, yellowgreen=0x9acd32,
)

_SYSTEM_COLORS = dict(canvas=0xffffff, canvastext=0x000000, field=0xffffff, fieldtext=0x000000, buttonface=0xefefef,
                      buttontext=0x000000, linktext=0x0000ee, visitedtext=0x551a8b, activetext=0xff0000, graytext=0x808080)
Color = Tuple[float, float, float, float]  # r, g, b in 0-255, alpha in 0-1


def unescape(s: str) -> str:
    r"""CSS escapes: "displ\61y" is "display", ".\68idden" is ".hidden"."""
    if "\\" not in s:
        return s

    def rep(m):
        if m.group(1):
            try:
                return chr(int(m.group(1), 16))
            except (ValueError, OverflowError):
                return "\ufffd"
        return m.group(2)

    return re.sub(r"\\(?:([0-9a-fA-F]{1,6})\s?|(.))", rep, s, flags=re.S)


def strip_comments(s: str) -> str:
    return re.sub(r"/\*.*?(?:\*/|$)", " ", s, flags=re.S)


def split_top(s: str, sep: str) -> List[str]:
    """Split on sep outside parentheses, brackets and quotes."""
    parts, cur, depth, quote, i = [], [], 0, "", 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            cur.append(s[i:i + 2])
            i += 2
            continue
        if quote:
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif c in "([":
            depth += 1
        elif c in ")]":
            depth = max(0, depth - 1)
        elif c == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    parts.append("".join(cur))
    return parts


# ---------- values ----------

def _number(tok: str, scale: float = 255.0) -> Optional[float]:
    tok = tok.strip()
    try:
        if tok.endswith("%"):
            return float(tok[:-1]) / 100 * scale
        if tok == "none":
            return 0.0
        return float(tok)
    except ValueError:
        return None


def _hue(tok: str) -> Optional[float]:
    tok = tok.strip().lower()
    m = re.fullmatch(r"([-+.\d]+)(deg|grad|rad|turn)?", tok)
    if not m:
        return 0.0 if tok == "none" else None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    return {"grad": v * 0.9, "rad": math.degrees(v), "turn": v * 360}.get(m.group(2) or "deg", v) % 360


def _hsl(h: float, s: float, l: float) -> Tuple[float, float, float]:
    def f(n):
        k = (n + h / 30) % 12
        return l - s * min(l, 1 - l) * max(-1, min(k - 3, 9 - k, 1))

    return f(0) * 255, f(8) * 255, f(4) * 255


def _srgb(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return (12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055) * 255


def _oklab(l: float, a: float, b: float) -> Tuple[float, float, float]:
    lm = l + 0.3963377774 * a + 0.2158037573 * b
    mm = l - 0.1055613458 * a - 0.0638541728 * b
    sm = l - 0.0894841775 * a - 1.2914855480 * b
    lc, mc, sc = lm ** 3, mm ** 3, sm ** 3
    return (
        _srgb(4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc),
        _srgb(-1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc),
        _srgb(-0.0041960863 * lc - 0.7034186147 * mc + 1.7076147010 * sc),
    )


def parse_color(value: str) -> Optional[Color]:
    """A CSS colour as RGBA, or None if it cannot be worked out here (color-mix, system colours)."""
    v = value.strip().lower()
    if v == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    if v in _SYSTEM_COLORS:
        n = _SYSTEM_COLORS[v]
        return (float(n >> 16 & 255), float(n >> 8 & 255), float(n & 255), 1.0)
    if v.startswith("color-mix("):
        return _color_mix(v[10:-1]) if v.endswith(")") else None
    if v.startswith("color(") and v.endswith(")"):
        return _color_fn(v[6:-1])
    if v in NAMED:
        n = NAMED[v]
        return (float(n >> 16 & 255), float(n >> 8 & 255), float(n & 255), 1.0)
    if v.startswith("#"):
        h = v[1:]
        if not re.fullmatch(r"[0-9a-f]+", h) or len(h) not in (3, 4, 6, 8):
            return None
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (float(int(h[:2], 16)), float(int(h[2:4], 16)), float(int(h[4:6], 16)), a)
    m = re.fullmatch(r"(rgba?|hsla?|hwb|oklab|oklch|lab|lch)\((.*)\)", v, re.S)
    if not m:
        return None
    fn, body = m.group(1), m.group(2)
    alpha = 1.0
    if "/" in body:
        body, a_tok = body.rsplit("/", 1)
        parsed = _number(a_tok, 1.0)
        if parsed is None:
            return None
        alpha = parsed
    toks = [t for t in re.split(r"[\s,]+", body.strip()) if t]
    if len(toks) == 4:
        parsed = _number(toks[3], 1.0)
        if parsed is None:
            return None
        alpha, toks = parsed, toks[:3]
    if len(toks) != 3:
        return None
    alpha = max(0.0, min(1.0, alpha))
    if fn in ("rgb", "rgba"):
        r, g, b = _number(toks[0]), _number(toks[1]), _number(toks[2])
        if r is None or g is None or b is None:
            return None
        return (max(0.0, min(255.0, r)), max(0.0, min(255.0, g)), max(0.0, min(255.0, b)), alpha)
    if fn in ("hsl", "hsla", "hwb"):
        h, x, y = _hue(toks[0]), _number(toks[1], 1.0), _number(toks[2], 1.0)
        if h is None or x is None or y is None:
            return None
        if fn == "hwb":
            if x + y >= 1:
                g = x / (x + y) * 255
                return (g, g, g, alpha)
            r, g, b = _hsl(h, 1.0, 0.5)
            return (r * (1 - x - y) + x * 255, g * (1 - x - y) + x * 255, b * (1 - x - y) + x * 255, alpha)
        return _hsl(h, max(0.0, min(1.0, x)), max(0.0, min(1.0, y))) + (alpha,)
    if fn in ("oklab", "oklch"):
        l = _number(toks[0], 1.0)
        if l is None:
            return None
        if fn == "oklab":
            a, b = _number(toks[1], 0.4), _number(toks[2], 0.4)
            if a is None or b is None:
                return None
        else:
            ch, h = _number(toks[1], 0.4), _hue(toks[2])
            if ch is None or h is None:
                return None
            a, b = ch * math.cos(math.radians(h)), ch * math.sin(math.radians(h))
        return _oklab(l, a, b) + (alpha,)
    # lab and lch: lightness decides whether text can vanish; treat them as a grey of that lightness.
    l = _number(toks[0], 100.0)
    if l is None:
        return None
    y = ((l + 16) / 116) ** 3 if l > 8 else l / 903.3
    g = _srgb(y)
    return (g, g, g, alpha)


def _color_fn(body: str) -> Optional[Color]:
    """color(srgb 1 1 1 / .5). The wide gamuts are read as sRGB: close enough for "can this be seen"."""
    alpha = 1.0
    if "/" in body:
        body, a_tok = body.rsplit("/", 1)
        parsed = _number(a_tok, 1.0)
        if parsed is None:
            return None
        alpha = parsed
    toks = body.split()
    if len(toks) != 4 or toks[0] not in ("srgb", "srgb-linear", "display-p3", "a98-rgb", "prophoto-rgb", "rec2020"):
        return None
    r, g, b = _number(toks[1], 1.0), _number(toks[2], 1.0), _number(toks[3], 1.0)
    if r is None or g is None or b is None:
        return None
    if toks[0] == "srgb-linear":
        return (_srgb(r), _srgb(g), _srgb(b), alpha)
    return (max(0.0, min(1.0, r)) * 255, max(0.0, min(1.0, g)) * 255, max(0.0, min(1.0, b)) * 255, alpha)


def _color_mix(body: str) -> Optional[Color]:
    """color-mix(in srgb, white 30%, black). Mixed in sRGB whatever the space: the same reasoning."""
    parts = [p.strip() for p in split_top(body, ",")]
    if len(parts) != 3 or not parts[0].startswith("in "):
        return None
    colors, weights = [], []
    for p in parts[1:]:
        m = re.search(r"\s([\d.]+)%$", p)
        weights.append(float(m.group(1)) / 100 if m else None)
        c = parse_color(p[:m.start()] if m else p)
        if c is None:
            return None
        colors.append(c)
    a, b = weights
    if a is None and b is None:
        a, b = 0.5, 0.5
    elif a is None:
        a = 1 - b
    elif b is None:
        b = 1 - a
    total = a + b
    if total <= 0:
        return None
    a, b = a / total, b / total
    x, y = colors
    return (x[0] * a + y[0] * b, x[1] * a + y[1] * b, x[2] * a + y[2] * b, x[3] * a + y[3] * b)


def data_css(url: str) -> Optional[str]:
    """The stylesheet inside a data: URL, or None."""
    m = re.match(r"\s*data:text/css[^,]*?(;base64)?,(.*)$", url, re.I | re.S)
    if not m:
        return None
    try:
        if m.group(1):
            return base64.b64decode(unquote(m.group(2))).decode("utf-8", "replace")
    except (binascii.Error, ValueError):
        return None
    return unquote(m.group(2))


def luminance(c: Color) -> float:
    def f(x):
        x /= 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast(a: Color, b: Color) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def blend(top: Color, under: Color) -> Color:
    a = top[3]
    return (top[0] * a + under[0] * (1 - a), top[1] * a + under[1] * (1 - a), top[2] * a + under[2] * (1 - a), 1.0)


_NUM = re.compile(r"([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)([a-z%]*)")
_UNITS = {
    "px": 1.0, "rem": ROOT_FONT, "rlh": ROOT_FONT * 1.2, "pt": 96 / 72, "pc": 16.0, "in": 96.0, "cm": 96 / 2.54,
    "mm": 96 / 25.4, "q": 96 / 101.6, "vw": VIEWPORT_W / 100, "vh": VIEWPORT_H / 100, "dvw": VIEWPORT_W / 100,
    "dvh": VIEWPORT_H / 100, "svw": VIEWPORT_W / 100, "svh": VIEWPORT_H / 100, "lvw": VIEWPORT_W / 100,
    "lvh": VIEWPORT_H / 100, "vmin": VIEWPORT_H / 100, "vmax": VIEWPORT_W / 100,
}


def length_px(value: str, font_px: float = ROOT_FONT, percent_of: Optional[float] = None) -> Optional[float]:
    """A length in pixels, including calc(), min(), max() and clamp(). None if it cannot be resolved."""
    p = _Length(value.strip().lower(), font_px, percent_of)
    try:
        v = p.expr()
        p.ws()
        return v if p.i == len(p.s) else None
    except (ValueError, IndexError, TypeError, ZeroDivisionError, RecursionError):
        return None


class _Length:
    def __init__(self, s, font_px, percent_of):
        self.s, self.i, self.font, self.pct = s, 0, font_px, percent_of

    def ws(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def expr(self):
        v = self.term()
        while True:
            self.ws()
            if self.i < len(self.s) and self.s[self.i] in "+-":
                op = self.s[self.i]
                self.i += 1
                r = self.term()
                v = None if v is None or r is None else (v + r if op == "+" else v - r)
            else:
                return v

    def term(self):
        v = self.atom()
        while True:
            self.ws()
            if self.i < len(self.s) and self.s[self.i] in "*/":
                op = self.s[self.i]
                self.i += 1
                r = self.atom()
                v = None if v is None or r is None else (v * r if op == "*" else v / r)
            else:
                return v

    def atom(self):
        self.ws()
        s = self.s
        for name in ("calc", "min", "max", "clamp"):
            if s.startswith(name + "(", self.i):
                self.i += len(name) + 1
                args = [self.expr()]
                self.ws()
                while s[self.i] == ",":
                    self.i += 1
                    args.append(self.expr())
                    self.ws()
                if s[self.i] != ")":
                    raise ValueError
                self.i += 1
                if name == "calc":
                    return args[0]
                if any(a is None for a in args):
                    return None
                if name == "min":
                    return min(args)
                if name == "max":
                    return max(args)
                return max(args[0], min(args[1], args[2]))
        if s[self.i] == "(":
            self.i += 1
            v = self.expr()
            self.ws()
            if s[self.i] != ")":
                raise ValueError
            self.i += 1
            return v
        m = _NUM.match(s, self.i)
        if not m:
            raise ValueError
        self.i = m.end()
        n, unit = float(m.group(1)), m.group(2)
        if not unit:
            return n
        if unit == "%":
            return None if self.pct is None else n / 100 * self.pct
        if unit in ("em", "cap"):
            return n * self.font
        if unit in ("ex", "ch"):
            return n * self.font / 2
        if unit == "lh":
            return n * self.font * 1.2
        if unit not in _UNITS:
            raise ValueError
        return n * _UNITS[unit]


# ---------- declarations ----------

DISPLAY = {
    "none", "block", "inline", "inline-block", "flex", "inline-flex", "grid", "inline-grid", "table", "inline-table",
    "table-row", "table-cell", "table-caption", "table-column", "table-column-group", "table-row-group",
    "table-header-group", "table-footer-group", "list-item", "flow-root", "contents", "ruby", "ruby-text", "run-in",
    "flow", "math", "-webkit-box", "-webkit-inline-box", "-ms-flexbox", "-webkit-flex", "inherit", "initial", "unset",
    "revert", "revert-layer",
}
GLOBAL = {"inherit", "initial", "unset", "revert", "revert-layer"}
VISIBILITY = {"visible", "hidden", "collapse"} | GLOBAL
_SYSTEM = {"canvastext", "canvas", "linktext", "visitedtext", "activetext", "buttontext", "buttonface", "field",
           "fieldtext", "highlight", "highlighttext", "graytext", "mark", "marktext", "accentcolor", "accentcolortext"}
_FONT_KEYWORDS = {"xx-small", "x-small", "small", "medium", "large", "x-large", "xx-large", "xxx-large", "smaller",
                  "larger", "math"}


def _valid(name: str, value: str) -> bool:
    """A browser throws away a declaration it cannot read, so "display:none;display:x" stays none."""
    if "var(" in value.lower():
        return True
    v = value.lower()
    if name == "display":
        return bool(v.split()) and all(t in DISPLAY for t in v.split())
    if name == "visibility":
        return v in VISIBILITY
    if name in ("opacity", "fill-opacity"):
        return v in GLOBAL or re.fullmatch(r"[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?%?|calc\(.*\)", v) is not None
    if name in ("color", "-webkit-text-fill-color", "background-color"):
        return v in GLOBAL or v == "currentcolor" or v in _SYSTEM or v.startswith(("color-mix", "light-dark", "color(")) \
            or parse_color(v) is not None
    if name == "font-size":
        return v in GLOBAL or v in _FONT_KEYWORDS or length_px(v, percent_of=16.0) is not None
    return True


def parse_declarations(body: str) -> List[Tuple[str, str, bool]]:
    """(property, value, important). Only those that can hide text, and custom properties."""
    out = []
    for part in split_top(strip_comments(body), ";"):
        name, sep, value = part.partition(":")
        if not sep:
            continue
        name = name.strip()
        custom = name.startswith("--")
        if not custom:
            name = unescape(name).lower()
            if name not in RELEVANT:
                continue
        value = value.strip()
        important = False
        m = re.search(r"!\s*important\s*$", value, re.I)
        if m:
            important, value = True, value[:m.start()].strip()
        if not custom:
            value = unescape(value).strip()
            if not value or not _valid(name, value):
                continue
        out.append((name, value, important))
    return out


# ---------- selectors ----------

class Compound:
    __slots__ = ("tag", "id", "classes", "attrs", "pseudos")

    def __init__(self):
        self.tag: Optional[str] = None
        self.id: Optional[str] = None
        self.classes: List[str] = []
        self.attrs: List[Tuple[str, str, Optional[str], bool]] = []
        self.pseudos: List[Tuple[str, object]] = []


class Unsupported(Exception):
    pass


class NeverMatches(Exception):
    """:hover, ::before and the like: valid, but it describes no text at rest."""


_IDENT_RE = re.compile(r"(?:[-_a-zA-Z0-9\u0080-\U0010ffff]|\\[0-9a-fA-F]{1,6}\s?|\\.)+")
_TAG_RE = re.compile(r"\*|(?:[-_a-zA-Z0-9\u0080-\U0010ffff]|\\[0-9a-fA-F]{1,6}\s?|\\.)+")
_PSEUDO_RE = re.compile(r"-?[a-zA-Z][-a-zA-Z0-9]*")
_ATTR_RE = re.compile(
    r"\s*((?:[-_a-zA-Z0-9\u0080-\U0010ffff]|\\.)+)\s*(?:([~|^$*]?=)\s*(\"[^\"]*\"|'[^']*'|[^\s]+)\s*([isIS])?\s*)?"
)
_AT_REST_FALSE = {
    "hover", "focus", "active", "visited", "target", "checked", "focus-within", "focus-visible", "disabled",
    "indeterminate", "fullscreen", "open", "modal", "popover-open", "placeholder-shown", "autofill", "invalid",
    "user-invalid", "user-valid", "paused", "playing", "current", "past", "future", "selection", "before", "after",
    "first-line", "first-letter", "marker", "placeholder", "backdrop", "file-selector-button", "cue", "part", "slotted",
}
_AT_REST_TRUE = {"enabled", "valid", "optional", "read-write", "read-only", "defined", "scope"}


def _parse_compound(s: str, i: int) -> Tuple[Compound, int]:
    c = Compound()
    n = len(s)
    start = i
    m = _TAG_RE.match(s, i)
    if m:
        if m.group() != "*":
            c.tag = unescape(m.group()).lower()
        i = m.end()
    while i < n:
        ch = s[i]
        if ch == "#" or ch == ".":
            m = _IDENT_RE.match(s, i + 1)
            if not m:
                raise Unsupported(s)
            if ch == "#":
                c.id = unescape(m.group())
            else:
                c.classes.append(unescape(m.group()))
            i = m.end()
        elif ch == "[":
            j = s.find("]", i)
            if j < 0:
                raise Unsupported(s)
            m = _ATTR_RE.fullmatch(s[i + 1:j])
            if not m:
                raise Unsupported(s)
            val = m.group(3)
            if val and val[0] in "\"'":
                val = val[1:-1]
            c.attrs.append((unescape(m.group(1)).lower(), m.group(2) or "", val, (m.group(4) or "").lower() == "i"))
            i = j + 1
        elif ch == ":":
            i += 2 if s.startswith("::", i) else 1
            m = _PSEUDO_RE.match(s, i)
            if not m:
                raise Unsupported(s)
            name = m.group().lower()
            i = m.end()
            arg = None
            if i < n and s[i] == "(":
                depth, j = 0, i
                while j < n:
                    if s[j] == "(":
                        depth += 1
                    elif s[j] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                if depth:
                    raise Unsupported(s)
                arg = s[i + 1:j]
                i = j + 1
            if name in _AT_REST_FALSE or name.startswith(("-webkit-", "-moz-", "-ms-")):
                raise NeverMatches()
            if name in _AT_REST_TRUE:
                continue
            if name == "has":
                c.pseudos.append((name, _relative_list(arg or "")))
            elif name in ("not", "is", "where", "matches", "any"):
                c.pseudos.append((name, selector_list(arg or "")))
            elif name in ("first-child", "last-child", "only-child", "root", "empty", "link", "any-link",
                          "first-of-type", "last-of-type", "only-of-type"):
                c.pseudos.append((name, None))
            elif name in ("nth-child", "nth-last-child", "nth-of-type", "nth-last-of-type"):
                c.pseudos.append((name, _nth(arg or "")))
            elif name in ("lang", "dir"):
                c.pseudos.append((name, (arg or "").strip().strip("\"'").lower()))
            else:
                raise Unsupported(name)
        else:
            break
    if i == start:
        raise Unsupported(s)
    return c, i


def _nth(arg: str) -> Tuple[int, int, Optional[List["Complex"]]]:
    """An+B, with the selector of ":nth-child(2 of .x)" if there is one."""
    formula, sep, of = arg.partition(" of ")
    only = selector_list(of) if sep else None
    a = formula.strip().lower().replace(" ", "")
    if a == "odd":
        return (2, 1, only)
    if a == "even":
        return (2, 0, only)
    m = re.fullmatch(r"([-+]?\d*)n([-+]\d+)?", a)
    if m:
        k = m.group(1)
        return (int(k + "1") if k in ("", "+", "-") else int(k), int(m.group(2) or 0), only)
    if re.fullmatch(r"[-+]?\d+", a):
        return (0, int(a), only)
    raise Unsupported(arg)


def _inherited_attr(el: Optional[Element], name: str) -> str:
    while el is not None:
        if name in el.attrs:
            return el.attrs[name].lower()
        el = el.parent
    return ""


class Complex:
    """A selector as compounds, rightmost last, with the combinator before each."""
    __slots__ = ("parts", "spec", "lead")

    def __init__(self, parts):
        self.parts: List[Tuple[str, Compound]] = parts
        self.spec = _specificity(parts)
        self.lead = " "


def parse_complex(s: str) -> Complex:
    # A namespace prefix: stylesheets on web pages only ever mean "any".
    s = re.sub(r"(?:^|(?<=[\s>+~,(]))(?:\*|[-\w]*)\|(?=[\w*])", "", s.strip())
    i, parts, comb = 0, [], ""
    while i < len(s):
        while i < len(s) and s[i].isspace():
            comb = comb or " "
            i += 1
        if i >= len(s):
            break
        if s[i] in ">+~":
            comb = s[i]
            i += 1
            while i < len(s) and s[i].isspace():
                i += 1
        c, i = _parse_compound(s, i)
        parts.append((comb if parts else "", c))
        comb = ""
    if not parts:
        raise Unsupported(s)
    return Complex(parts)


def _relative_list(s: str) -> List[Complex]:
    """The argument of :has(): each selector remembers the combinator it starts with."""
    out = []
    for part in split_top(s, ","):
        part = part.strip()
        comb = part[0] if part[:1] in (">", "+", "~") else " "
        try:
            sel = parse_complex(part.lstrip(">+~ "))
        except NeverMatches:
            continue
        sel.lead = comb
        out.append(sel)
    return out


def selector_list(s: str) -> List[Complex]:
    out = []
    for part in split_top(s, ","):
        try:
            out.append(parse_complex(part))
        except NeverMatches:
            continue
    return out


def _specificity(parts) -> Tuple[int, int, int]:
    a = b = c = 0
    for _, comp in parts:
        a += 1 if comp.id else 0
        b += len(comp.classes) + len(comp.attrs)
        c += 1 if comp.tag else 0
        for name, arg in comp.pseudos:
            if name in ("not", "is", "matches", "any", "has"):
                if arg:
                    x = max(s.spec for s in arg)
                    a, b, c = a + x[0], b + x[1], c + x[2]
            elif name != "where":
                b += 1
    return (a, b, c)


def _attr_match(el: Element, name: str, op: str, val: Optional[str], ci: bool) -> bool:
    if name not in el.attrs:
        return False
    if not op:
        return True
    have = el.attrs[name]
    val = val or ""
    if ci:
        have, val = have.lower(), val.lower()
    if op == "=":
        return have == val
    if op == "~=":
        return val in have.split()
    if op == "|=":
        return have == val or have.startswith(val + "-")
    if not val:
        return False
    if op == "^=":
        return have.startswith(val)
    if op == "$=":
        return have.endswith(val)
    return val in have  # *=


def _match_compound(el: Element, c: Compound, quirks: bool) -> bool:
    if c.tag is not None and el.tag != c.tag:
        return False
    if c.id is not None:
        have = el.attrs.get("id")
        if have is None or (have.lower() != c.id.lower() if quirks else have != c.id):
            return False
    if c.classes:
        if quirks:
            lowered = {x.lower() for x in el.classes}
            if any(x.lower() not in lowered for x in c.classes):
                return False
        elif any(x not in el.classes for x in c.classes):
            return False
    for name, op, val, ci in c.attrs:
        if not _attr_match(el, name, op, val, ci):
            return False
    for name, arg in c.pseudos:
        if name == "not":
            if any(match(el, x, quirks) for x in arg):
                return False
        elif name in ("is", "where", "matches", "any"):
            if not any(match(el, x, quirks) for x in arg):
                return False
        elif name == "has":
            if not any(_has(el, x, quirks) for x in arg):
                return False
        elif name == "root":
            if el.tag != "html":
                return False
        elif name in ("link", "any-link"):
            if el.tag not in ("a", "area") or "href" not in el.attrs:
                return False
        elif name == "empty":
            if el.children:
                return False
        elif name == "lang":
            have = _inherited_attr(el, "lang")
            if have != arg and not have.startswith(f"{arg}-"):
                return False
        elif name == "dir":
            if (_inherited_attr(el, "dir") or "ltr") != arg:
                return False
        else:
            sibs = el.parent.elements() if el.parent else [el]
            if name.endswith("of-type"):
                sibs = [s for s in sibs if s.tag == el.tag]
            elif name in ("nth-child", "nth-last-child") and arg[2] is not None:
                sibs = [s for s in sibs if any(match(s, x, quirks) for x in arg[2])]
                if el not in sibs:
                    return False
            pos = sibs.index(el) + 1 if len(sibs) != len(el.parent.kids if el.parent else [el]) else el.index + 1
            last = len(sibs) - pos + 1
            if name in ("first-child", "first-of-type") and pos != 1:
                return False
            if name in ("last-child", "last-of-type") and last != 1:
                return False
            if name in ("only-child", "only-of-type") and len(sibs) != 1:
                return False
            if name in ("nth-child", "nth-last-child", "nth-of-type", "nth-last-of-type"):
                a, b = arg[0], arg[1]
                x = last if "last" in name else pos
                if a == 0:
                    if x != b:
                        return False
                elif (x - b) % a != 0 or (x - b) / a < 0:
                    return False
    return True


def _has(el: Element, sel: Complex, quirks: bool) -> bool:
    if sel.lead == " ":
        return any(match(d, sel, quirks) for d in el.walk() if d is not el)
    if sel.lead == ">":
        return any(match(k, sel, quirks) for k in el.kids)
    sibs = el.parent.kids if el.parent else []
    after = sibs[el.index + 1:]
    return any(match(k, sel, quirks) for k in (after[:1] if sel.lead == "+" else after))


def match(el: Element, sel: Complex, quirks: bool) -> bool:
    return _match_from(el, sel.parts, len(sel.parts) - 1, quirks)


def _match_from(el: Element, parts, k: int, quirks: bool) -> bool:
    comb, comp = parts[k]
    if not _match_compound(el, comp, quirks):
        return False
    if k == 0:
        return True
    if comb == ">":
        return el.parent is not None and _match_from(el.parent, parts, k - 1, quirks)
    if comb == " ":
        p = el.parent
        while p is not None:
            if _match_from(p, parts, k - 1, quirks):
                return True
            p = p.parent
        return False
    sibs = el.parent.elements() if el.parent else []
    if comb == "+":
        return el.index > 0 and _match_from(sibs[el.index - 1], parts, k - 1, quirks)
    if comb == "~":
        return any(_match_from(s, parts, k - 1, quirks) for s in sibs[:el.index])
    return False


# ---------- media queries ----------

def _cmp(a: float, op: str, b: float) -> bool:
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


def media_applies(query: str) -> bool:
    """A screen 1280 by 800, light theme. Width conditions matter: hiding only on phones is not hiding."""
    if not query.strip():
        return True
    dims = {"width": VIEWPORT_W, "height": VIEWPORT_H}
    for q in split_top(query, ","):
        q = q.strip().lower()
        negate = q.startswith("not ")
        if negate:
            q = q[4:]
        ok = True
        for token in re.split(r"\s+and\s+", q):
            token = token.strip()
            if token.startswith("only "):
                token = token[5:].strip()
            if token in ("screen", "all", ""):
                continue
            if not token.startswith("("):
                ok = False  # print, speech and the older media types
                continue
            m = re.fullmatch(r"\(\s*([-a-z]+)\s*:\s*([^)]+?)\s*\)", token)
            if m:
                name, val = m.group(1), m.group(2)
                mm = re.fullmatch(r"(?:(min|max)-)?(width|height)", name)
                px = length_px(val) if mm else None
                if mm and px is not None:
                    have = dims[mm.group(2)]
                    ok = ok and (have >= px if mm.group(1) == "min" else have <= px if mm.group(1) == "max" else have == px)
                elif name == "prefers-color-scheme":
                    ok = ok and val == "light"
                elif name == "prefers-reduced-motion":
                    ok = ok and val == "no-preference"
                elif name == "orientation":
                    ok = ok and val == "landscape"
                elif name in ("hover", "any-hover"):
                    ok = ok and val == "hover"
                elif name in ("pointer", "any-pointer"):
                    ok = ok and val == "fine"
                continue
            m = re.fullmatch(r"\(\s*(width|height)\s*(<=|>=|<|>)\s*([^)\s]+)\s*\)", token)
            if m:
                ok = ok and _cmp(dims[m.group(1)], m.group(2), length_px(m.group(3)) or 0)
                continue
            m = re.fullmatch(r"\(\s*([^)\s]+)\s*(<=|>=|<|>)\s*(width|height)\s*(?:(<=|>=|<|>)\s*([^)\s]+)\s*)?\)", token)
            if m:
                d = dims[m.group(3)]
                ok = ok and _cmp(length_px(m.group(1)) or 0, m.group(2), d)
                if m.group(4):
                    ok = ok and _cmp(d, m.group(4), length_px(m.group(5)) or 0)
        if ok != negate:
            return True
    return False


# ---------- stylesheets ----------

def _nest(parent: str, child: str) -> str:
    """The full selector of a nested rule. An "&" stands for the parent; without one it is a descendant."""
    if not parent:
        return child
    # A pseudo-element cannot go inside :is(), so a parent that names one stays out of it.
    outer = parent if "," not in parent else f":is({parent})"
    out = []
    for part in split_top(child, ","):
        part = part.strip()
        out.append(part.replace("&", outer) if "&" in part else f"{outer} {part}")
    return ",".join(out)


def _statements(css: str):
    """Yield ("decls", "", text) for loose declarations and ("rule", prelude, body) for each block.
    An at-statement ending in ";" comes as a rule with no body."""
    i, n = 0, len(css)
    loose = []
    while i < n:
        j, quote = i, ""
        while j < n:
            c = css[j]
            if c == "\\":
                j += 2
                continue
            if quote:
                if c == quote:
                    quote = ""
            elif c in "\"'":
                quote = c
            elif c in "{;}":
                break
            j += 1
        if j >= n:
            loose.append(css[i:n])
            break
        c = css[j]
        if c == "}":  # a stray closing brace
            i = j + 1
            continue
        if c == ";":
            text = css[i:j].strip()
            if text.startswith("@"):
                yield ("rule", text, None)
            elif text:
                loose.append(text + ";")
            i = j + 1
            continue
        level, k, quote = 1, j + 1, ""
        while k < n and level:
            c = css[k]
            if c == "\\":
                k += 2
                continue
            if quote:
                if c == quote:
                    quote = ""
            elif c in "\"'":
                quote = c
            elif c == "{":
                level += 1
            elif c == "}":
                level -= 1
            k += 1
        yield ("rule", css[i:j].strip(), css[j + 1:k - 1] if not level else css[j + 1:k])
        i = k
    text = "".join(loose).strip()
    if text:
        yield ("decls", "", text)


_PAINTING_PSEUDO = re.compile(r"::?(?:before|after)\s*$", re.I)


UNLAYERED = 1 << 20


def supports_applies(cond: str) -> bool:
    """@supports. A declaration we can judge is judged; anything else is assumed to be supported."""
    c = cond.strip()
    while c.startswith("(") and c.endswith(")") and _closes_last(c):
        inner = c[1:-1].strip()
        m = re.fullmatch(r"([-a-zA-Z]+)\s*:\s*(.+)", inner, re.S)
        if m and "(" not in m.group(1):
            name = m.group(1).lower()
            return _valid(name, m.group(2).strip()) if name in ("display", "visibility", "color", "opacity", "font-size") else True
        c = inner
    low = c.lower()
    if low.startswith("not ") or low.startswith("not("):
        return not supports_applies(c[3:])
    for word, combine in ((" or ", any), (" and ", all)):
        parts = _split_words(c, word)
        if len(parts) > 1:
            return combine(supports_applies(p) for p in parts)
    return True


def _closes_last(c: str) -> bool:
    depth = 0
    for i, ch in enumerate(c):
        depth += ch == "("
        depth -= ch == ")"
        if depth == 0:
            return i == len(c) - 1
    return False


def _split_words(c: str, word: str) -> List[str]:
    parts, depth, start, i, low = [], 0, 0, 0, c.lower()
    while i < len(c):
        depth += c[i] == "("
        depth -= c[i] == ")"
        if depth == 0 and low.startswith(word, i):
            parts.append(c[start:i])
            i += len(word)
            start = i
            continue
        i += 1
    parts.append(c[start:])
    return parts


class Rule:
    __slots__ = ("sel", "decls", "order", "layer")

    def __init__(self, sel: Complex, decls, order: int, layer: int):
        self.sel, self.decls, self.order, self.layer = sel, decls, order, layer


class Sheet:
    """All rules, indexed by the rightmost part of the selector so each element checks only a few."""

    def __init__(self):
        self.by_id: Dict[str, List[Rule]] = {}
        self.by_class: Dict[str, List[Rule]] = {}
        self.by_tag: Dict[str, List[Rule]] = {}
        self.universal: List[Rule] = []
        self.order = 0
        self.unsupported = 0
        self.has_import = False
        self.painted_pseudo: Dict[str, List[Complex]] = {}  # by rightmost class, or "*"
        self.layers: Dict[str, int] = {}  # by name, in the order first mentioned
        self.layer = UNLAYERED  # of the rules being read

    def add_rule(self, selectors: str, body: str) -> None:
        decls = parse_declarations(body)
        if not decls:
            return
        for part in split_top(selectors, ","):
            self.order += 1
            try:
                sel = parse_complex(part)
            except NeverMatches:
                self._note_pseudo(part, decls)
                continue
            except (Unsupported, RecursionError):
                self.unsupported += 1
                continue
            rule = Rule(sel, decls, self.order, self.layer)
            right = sel.parts[-1][1]
            if right.id:
                self.by_id.setdefault(right.id.lower(), []).append(rule)
            elif right.classes:
                self.by_class.setdefault(right.classes[0].lower(), []).append(rule)
            elif right.tag:
                self.by_tag.setdefault(right.tag, []).append(rule)
            else:
                self.universal.append(rule)

    def _layer_rank(self, name: str) -> int:
        return self.layers.setdefault(name, len(self.layers))

    def _note_pseudo(self, selector: str, decls) -> None:
        """A ::before or ::after that paints a background sits behind the element's text."""
        if not any(d[0].startswith("background") and d[1].lower() not in ("none", "transparent") for d in decls):
            return
        m = _PAINTING_PSEUDO.search(selector)
        if not m:
            return
        try:
            sel = parse_complex(selector[:m.start()])
        except (NeverMatches, Unsupported, RecursionError):
            return
        right = sel.parts[-1][1]
        self.painted_pseudo.setdefault(right.classes[0].lower() if right.classes else "*", []).append(sel)

    def has_painted_pseudo(self, el: Element, quirks: bool) -> bool:
        if not self.painted_pseudo:
            return False
        keys = [c.lower() for c in el.classes] + ["*"]
        return any(match(el, s, quirks) for k in keys for s in self.painted_pseudo.get(k, ()))

    def add_css(self, css: str) -> None:
        self._block(strip_comments(css), 0)

    def _block(self, css: str, depth: int, parent: str = "") -> None:
        """Read a list of rules. With parent, these are nested inside that selector."""
        if depth > 16:
            return
        for kind, prelude, body in _statements(css):
            if kind == "decls":
                if parent:
                    self.add_rule(parent, body)
                continue
            low = prelude.lower()
            if body is None:
                if low.startswith("@layer"):
                    for name in prelude[6:].split(","):
                        self._layer_rank(name.strip())
                elif low.startswith("@import"):
                    m = re.match(r"""@import\s+(?:url\(\s*)?["']?(data:[^"')]*)""", prelude, re.I)
                    inner = data_css(m.group(1)) if m else None
                    if inner is None:
                        self.has_import = True
                    else:
                        self._block(strip_comments(inner), depth + 1, parent)
            elif low.startswith("@media"):
                if media_applies(prelude[6:]):
                    self._block(body, depth + 1, parent)
            elif low.startswith("@supports"):
                if supports_applies(prelude[9:]):
                    self._block(body, depth + 1, parent)
            elif low.startswith("@layer"):
                outer = self.layer
                self.layer = self._layer_rank(prelude[6:].strip() or f"#anonymous{len(self.layers)}")
                self._block(body, depth + 1, parent)
                self.layer = outer
            elif low.startswith("@scope"):
                self._block(body, depth + 1, parent)
            elif not low.startswith("@"):
                self._block(body, depth + 1, _nest(parent, prelude))

    def matching(self, el: Element, quirks: bool) -> List[Rule]:
        found: List[Rule] = []
        if "id" in el.attrs:
            found += self.by_id.get(el.attrs["id"].lower(), [])
        for c in el.classes:
            found += self.by_class.get(c.lower(), [])
        found += self.by_tag.get(el.tag, [])
        found += self.universal
        return [r for r in found if match(el, r.sel, quirks)]
