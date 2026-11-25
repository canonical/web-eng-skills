#!/usr/bin/env python3
"""Extract the reviewable content of a web page as plain text.

Usage: python3 extract_text.py <page.html> [--start-id main-content]

Prints the page title and meta description, then the main content region:
headings with their level, paragraphs and list items, links with their href,
and images with their alt text. Skips scripts, styles, SVGs, forms and the
contact modal, so the output is small enough to compare against a copydoc.

The region runs from the element with id=<start-id> to the first <footer>.
If that id is missing, the whole <body> is used.
"""

import argparse
import re
import sys
from html.parser import HTMLParser

SKIP = {"script", "style", "svg", "form", "noscript", "template"}
BLOCK = {"p", "li", "section", "tr", "dd", "dt", "blockquote", "figcaption"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class Extractor(HTMLParser):
    def __init__(self, start_id):
        super().__init__(convert_charrefs=True)
        self.start_id = start_id
        self.active = start_id is None
        self.done = False
        self.skip = 0
        self.out = []

    def emit(self, s):
        self.out.append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if not self.active and a.get("id") == self.start_id:
            self.active = True
        if tag == "footer" and self.active:
            self.done = True
        if not self.active or self.done:
            return
        if tag in SKIP or "p-modal" in (a.get("class") or ""):
            self.skip += 1
            return
        if self.skip:
            return
        if tag in HEADINGS:
            self.emit(f"\n\n[{tag}] ")
        elif tag in BLOCK:
            self.emit("\n")
        elif tag == "br":
            self.emit(" ")
        elif tag == "a":
            self.emit(f" <a href={a.get('href')}>")
        elif tag == "img":
            self.emit(f" [img alt=\"{a.get('alt')}\" src=…{(a.get('src') or '')[-60:]}]")
        elif tag == "button":
            self.emit(" <button>")

    def handle_endtag(self, tag):
        if not self.active or self.done:
            return
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "a":
            self.emit("</a>")
        elif tag == "button":
            self.emit("</button>")

    def handle_data(self, data):
        if self.active and not self.done and not self.skip and data.strip():
            self.emit(" ".join(data.split()) + " ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--start-id", default="main-content")
    args = ap.parse_args()

    with open(args.html, encoding="utf-8", errors="replace") as f:
        src = f.read()

    title = re.search(r"<title>(.*?)</title>", src, re.S | re.I)
    desc = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', src, re.I)
    print("TITLE:", " ".join(title.group(1).split()) if title else "(none)")
    print("META DESCRIPTION:", desc.group(1).strip() if desc else "(none)")

    start_id = args.start_id if f'id="{args.start_id}"' in src else None
    if start_id is None:
        print(f"(no id=\"{args.start_id}\" found; using the whole body)", file=sys.stderr)
    p = Extractor(start_id)
    p.feed(src)
    text = "".join(p.out)
    print("\n".join(line.rstrip() for line in text.splitlines() if line.strip()))


if __name__ == "__main__":
    main()
