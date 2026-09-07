#!/usr/bin/env python3
"""AEROXMD single-file compiler: website.html + css/styles.css + js/main.js -> index.html.

Usage:
    python3 build.py                    # defaults relative to website/
    python3 build.py [src] [css] [js] [out]

Google Fonts <link>s are left external on purpose (never inlined).
Never edit index.html directly -- it is generated output.
"""
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "website.html"
CSS = BASE / "css" / "styles.css"
JS = BASE / "js" / "main.js"
OUT = BASE / "index.html"


def main(args):
    src = Path(args[0]) if len(args) > 0 else SRC
    css_p = Path(args[1]) if len(args) > 1 else CSS
    js_p = Path(args[2]) if len(args) > 2 else JS
    out = Path(args[3]) if len(args) > 3 else OUT

    for p in (src, css_p, js_p):
        if not p.is_file():
            sys.exit(f"build.py: missing source file: {p}")

    if out.resolve() in (src.resolve(), css_p.resolve(), js_p.resolve()):
        sys.exit("build.py: output would overwrite a source file -- refusing.")

    html = src.read_text(encoding="utf-8")
    css = css_p.read_text(encoding="utf-8")
    js = js_p.read_text(encoding="utf-8")

    if "</style" in css:
        sys.exit("build.py: css contains literal '</style' -- refusing (would break inline block).")
    if "</script" in js:
        sys.exit("build.py: js contains literal '</script' -- refusing (would break inline block).")

    link_re = re.compile(
        r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*href=["\'](?:\./)?css/styles\.css["\'][^>]*>',
        re.IGNORECASE,
    )
    if not link_re.search(html):
        sys.exit("build.py: stylesheet link to css/styles.css not found in source.")
    html = link_re.sub(lambda m: "<style>\n" + css + "\n</style>", html, count=1)

    script_re = re.compile(
        r'<script\b[^>]*src=["\'](?:\./)?js/main\.js["\'][^>]*>\s*</script>',
        re.IGNORECASE,
    )
    if not script_re.search(html):
        sys.exit("build.py: script tag for js/main.js not found in source.")
    html = script_re.sub(lambda m: "<script>\n" + js + "\n</script>", html, count=1)

    out.write_text(html, encoding="utf-8")
    print(f"OK: {src.name} + {css_p.relative_to(BASE)} + {js_p.relative_to(BASE)} -> {out.name} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main(sys.argv[1:])
