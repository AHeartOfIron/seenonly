"""What every test page is built from."""
MARKER = "QZXMARKERQZX"
_M = MARKER


def page(body: str, head: str = "", doctype: bool = True) -> str:
    dt = "<!doctype html>" if doctype else ""
    return (f'{dt}<html><head><meta charset="utf-8"><title>Test</title>{head}</head>'
            f'<body><h1>Visible heading</h1><p>Visible article text.</p>{body}<p>Closing line.</p></body></html>')


def style(css: str) -> str:
    return f"<style>{css}</style>"
