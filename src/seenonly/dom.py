"""A small HTML tree, built the way a browser builds one where it matters for hiding text.

A regular expression cannot tell where a hidden block ends. An attacker relies on exactly
that, so the tree follows the browser rules an attacker can abuse: implied end tags, stray
end tags, and "self-closing" syntax that HTML ignores.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Dict, List, Optional, Union

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
CLOSES_P = {
    "address", "article", "aside", "blockquote", "center", "details", "dialog", "dir", "div", "dl", "fieldset",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "hr", "main",
    "menu", "nav", "ol", "p", "pre", "section", "table", "ul",
}
# An end tag does not reach past these: "<div hidden><table><td></div>" leaves the div open.
BARRIER = {"table", "td", "th", "caption", "html", "template", "object", "marquee", "applet"}
TABLE_PARTS = {"table", "tbody", "thead", "tfoot", "tr", "td", "th", "caption", "colgroup"}
_ROW_GROUP = {"tbody", "thead", "tfoot", "tr", "td", "th", "caption", "colgroup"}
# start tag: the open elements it closes, and where the search for them stops.
IMPLIED = {
    "li": ({"li"}, {"ul", "ol", "menu"}),
    "dt": ({"dt", "dd"}, {"dl"}),
    "dd": ({"dt", "dd"}, {"dl"}),
    "option": ({"option"}, {"select", "datalist", "optgroup"}),
    "optgroup": ({"option", "optgroup"}, {"select", "datalist"}),
    "tr": ({"tr", "td", "th", "caption", "colgroup"}, {"table", "tbody", "thead", "tfoot"}),
    "td": ({"td", "th"}, {"tr", "table"}),
    "th": ({"td", "th"}, {"tr", "table"}),
    "tbody": (_ROW_GROUP, {"table"}),
    "thead": (_ROW_GROUP, {"table"}),
    "tfoot": (_ROW_GROUP, {"table"}),
}
FOREIGN = {"svg", "math"}
# Chromium's limit: deeper elements hang off this ancestor, though they stay open. Without it a page
# of 100 000 nested divs makes every parent walk slow.
MAX_DEPTH = 512


class Text:
    __slots__ = ("data", "parent")

    def __init__(self, data: str, parent: "Element"):
        self.data = data
        self.parent = parent


class Comment:
    __slots__ = ("data", "parent")

    def __init__(self, data: str, parent: "Element"):
        self.data = data
        self.parent = parent


class Element:
    __slots__ = ("tag", "attrs", "parent", "children", "index", "classes", "kids")

    def __init__(self, tag: str, attrs: Dict[str, str], parent: Optional["Element"]):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: List[Union["Element", Text, Comment]] = []
        self.index = 0  # position among the parent's element children
        self.classes = attrs.get("class", "").split()
        self.kids: List["Element"] = []

    def elements(self) -> List["Element"]:
        return self.kids

    def walk(self):
        """This element and every element below it, in document order. Not recursive: a page
        can nest deeply on purpose to overflow a recursive parser."""
        stack = [self]
        while stack:
            el = stack.pop()
            yield el
            stack.extend(reversed(el.elements()))

    def path(self) -> str:
        """A short readable location, such as "body > div#a > p.note"."""
        parts = []
        el: Optional[Element] = self
        while el is not None and el.tag != "#document" and len(parts) < 4:
            s = el.tag
            if el.attrs.get("id"):
                s += "#" + el.attrs["id"]
            elif el.classes:
                s += "." + el.classes[0]
            parts.append(s)
            el = el.parent
        return " > ".join(reversed(parts))


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("#document", {}, None)
        self.stack = [self.root]
        self.has_doctype = False
        self.open: Dict[str, int] = {}  # how many of each tag are open, to skip searches that cannot succeed

    @property
    def top(self) -> Element:
        return self.stack[-1]

    def _in_foreign(self) -> bool:
        return self.open.get("svg", 0) > 0 or self.open.get("math", 0) > 0

    def _pop_to(self, i: int) -> None:
        for e in self.stack[i:]:
            self.open[e.tag] -= 1
        del self.stack[i:]

    def _implied_end(self, tag: str) -> None:
        if self._in_foreign():
            return
        if tag in CLOSES_P and self.open.get("p"):
            for i in range(len(self.stack) - 1, 0, -1):
                t = self.stack[i].tag
                if t == "p":
                    self._pop_to(i)
                    break
                if t in BARRIER or t == "button":
                    break
        if tag in IMPLIED and any(self.open.get(c) for c in IMPLIED[tag][0]):
            closes, stop = IMPLIED[tag]
            found = None
            for i in range(len(self.stack) - 1, 0, -1):
                t = self.stack[i].tag
                if t in closes:
                    found = i
                if t in stop:
                    break
            if found is not None:
                self._pop_to(found)

    def handle_starttag(self, tag, attrs):
        self._implied_end(tag)
        # The first value of a repeated attribute wins, as in a browser.
        d: Dict[str, str] = {}
        for k, v in attrs:
            d.setdefault(k.lower(), v if v is not None else "")
        parent = self.attach
        el = Element(tag, d, parent)
        el.index = len(parent.kids)
        parent.kids.append(el)
        parent.children.append(el)
        if tag not in VOID:
            self.stack.append(el)
            self.open[tag] = self.open.get(tag, 0) + 1

    def handle_startendtag(self, tag, attrs):
        # HTML ignores the slash: <div hidden/> opens a div. Only SVG and MathML close there.
        self.handle_starttag(tag, attrs)
        if self.top.tag == tag and tag not in VOID and self._in_foreign():
            self._pop_to(len(self.stack) - 1)

    def handle_endtag(self, tag):
        if not self.open.get(tag):
            return  # a stray end tag: the browser ignores it too
        table_tag = tag in TABLE_PARTS
        for i in range(len(self.stack) - 1, 0, -1):
            t = self.stack[i].tag
            if t == tag:
                self._pop_to(i)
                return
            if t in BARRIER and not (table_tag and t != "template"):
                return

    @property
    def attach(self) -> Element:
        return self.stack[min(len(self.stack), MAX_DEPTH) - 1]

    def handle_data(self, data):
        self.attach.children.append(Text(data, self.attach))

    def handle_comment(self, data):
        self.attach.children.append(Comment(data, self.attach))

    def handle_decl(self, decl):
        if decl.lower().startswith("doctype"):
            self.has_doctype = True

    def unknown_decl(self, data):  # <![CDATA[ ... ]]> is a comment in HTML
        self.handle_comment(data)

    def handle_pi(self, data):
        self.handle_comment(data)


class Document:
    def __init__(self, root: Element, has_doctype: bool):
        self.root = root
        self.has_doctype = has_doctype


def parse(html: str) -> Document:
    b = _Builder()
    b.feed(html)
    b.close()
    return Document(b.root, b.has_doctype)
