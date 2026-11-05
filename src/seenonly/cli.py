"""seenonly page.html, or: curl -s https://example.com | seenonly"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, clean, clean_text


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="seenonly", description="Print only the text a person can see on a page, and report the rest.")
    p.add_argument("file", nargs="?", default="-", help="HTML file, or - for standard input (default)")
    p.add_argument("--css", action="append", default=[], metavar="FILE", help="a stylesheet the page links to (repeat for several)")
    p.add_argument("--phrases", choices=["remove", "flag", "off"], default="remove", help="visible sentences written as orders to an AI (default: remove)")
    p.add_argument("--plain", action="store_true", help="the input is plain text, not HTML")
    p.add_argument("--html", action="store_true", help="print the cleaned HTML instead of text")
    p.add_argument("--json", action="store_true", help="print text and findings as JSON")
    p.add_argument("--report", action="store_true", help="print findings instead of text")
    p.add_argument("--all", action="store_true", help="with --report: also list hidden text that does not look like an attack")
    p.add_argument("--check", action="store_true", help="exit with status 1 if the page looks like an attack")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    if a.file == "-":
        raw = sys.stdin.buffer.read()
    else:
        with open(a.file, "rb") as f:
            raw = f.read()
    source = raw.decode("utf-8", "replace")

    if a.plain:
        r = clean_text(source, phrases=a.phrases)
    else:
        css = ""
        for path in a.css:
            with open(path, encoding="utf-8", errors="replace") as f:
                css += f.read() + "\n"
        r = clean(source, phrases=a.phrases, css=css)

    if a.json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    elif a.report:
        for f in r.findings if a.all else r.suspicious:
            print(f"[{f.kind}] {f.reason}" + (f" at {f.location}" if f.location else "") + (f": {f.text}" if f.text else ""))
    elif a.html:
        print(r.html)
    else:
        print(r.text)

    if not a.json and not a.report and r.suspicious:
        print(f"seenonly: {len(r.suspicious)} suspicious item(s) removed. See --report.", file=sys.stderr)
    if r.external_css and not a.json:
        print("seenonly: the page links stylesheets that were not read. Pass them with --css for full coverage.", file=sys.stderr)
    return 1 if a.check and r.suspicious else 0


if __name__ == "__main__":
    raise SystemExit(main())
