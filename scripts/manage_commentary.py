#!/usr/bin/env python3
"""Safely edit only the HAI Commentary catalogue block in publications.html.

This tool avoids replacing the entire publications page when adding or publishing a
Commentary item. It locates the Commentary article and modifies only its
.series-titles block.

Examples:
  python scripts/manage_commentary.py --check
  python scripts/manage_commentary.py add-locked "New Commentary Title"
  python scripts/manage_commentary.py publish \
      --title "New Commentary Title" \
      --href "publications/commentary/new-commentary.html" \
      --code "HAI-CM-2026-19" \
      --date "August 12, 2026" \
      --author "Abdul Ahmed"
"""

from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "publications.html"
ARTICLE_START = '<article class="series-section" id="commentary">'
NEXT_ARTICLE = '<article class="series-section" id="special-reports">'
TITLES_START = '<div class="series-titles">'


def read_catalogue() -> str:
    if not CATALOGUE.exists():
        raise SystemExit("publications.html is missing")
    return CATALOGUE.read_text(encoding="utf-8")


def commentary_bounds(text: str) -> tuple[int, int]:
    start = text.find(ARTICLE_START)
    end = text.find(NEXT_ARTICLE)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit("Could not uniquely locate Commentary catalogue section")
    if text.count(ARTICLE_START) != 1:
        raise SystemExit("Expected exactly one Commentary catalogue section")
    return start, end


def titles_bounds(text: str) -> tuple[int, int]:
    article_start, article_end = commentary_bounds(text)
    titles_start = text.find(TITLES_START, article_start, article_end)
    if titles_start < 0:
        raise SystemExit("Could not locate Commentary series-titles block")
    content_start = titles_start + len(TITLES_START)
    titles_end = text.find("</div>", content_start, article_end)
    if titles_end < 0:
        raise SystemExit("Could not locate end of Commentary series-titles block")
    return content_start, titles_end


def write_targeted(original: str, replacement_block: str) -> None:
    start, end = titles_bounds(original)
    updated = original[:start] + replacement_block + original[end:]
    if original[:start] != updated[:start] or original[end:] != updated[start + len(replacement_block):]:
        raise SystemExit("Safety check failed: content outside Commentary block would change")
    CATALOGUE.write_text(updated, encoding="utf-8")


def check() -> int:
    text = read_catalogue()
    article_start, article_end = commentary_bounds(text)
    content_start, content_end = titles_bounds(text)
    block = text[content_start:content_end]
    if "published-entry" not in block:
        print("COMMENTARY CHECK FAILED: no published entries found")
        return 1
    if "access-icon locked" not in block:
        print("COMMENTARY CHECK FAILED: no locked entries found")
        return 1
    if article_start >= content_start or content_end >= article_end:
        print("COMMENTARY CHECK FAILED: section boundaries are inconsistent")
        return 1
    print("COMMENTARY CHECK PASSED: targeted editing boundaries are valid.")
    return 0


def add_locked(title: str) -> int:
    text = read_catalogue()
    start, end = titles_bounds(text)
    block = text[start:end]
    escaped = html.escape(title, quote=False)
    if title in block or escaped in block:
        print(f"No change: Commentary title already exists: {title}")
        return 0

    item = (
        f'              <li><span class="access-icon locked" role="img" '
        f'aria-label="Not publicly available" title="Not publicly available">&#128274;</span>'
        f'<cite>{escaped}</cite></li>\n'
    )

    if "<ol>" in block and "</ol>" in block:
        insert_at = block.rfind("</ol>")
        new_block = block[:insert_at] + item + block[insert_at:]
    else:
        new_block = block + "\n            <ol>\n" + item + "            </ol>\n          "

    write_targeted(text, new_block)
    print(f"Added locked Commentary title: {title}")
    return 0


def remove_locked_item(block: str, title: str) -> str:
    escaped = re.escape(html.escape(title, quote=False))
    pattern = re.compile(
        r'\s*<li><span class="access-icon locked"[^>]*>.*?</span><cite>'
        + escaped
        + r'</cite></li>\s*',
        re.DOTALL,
    )
    return pattern.sub("\n", block, count=1)


def publish(title: str, href: str, code: str, date: str, author: str) -> int:
    text = read_catalogue()
    start, end = titles_bounds(text)
    block = text[start:end]
    escaped_title = html.escape(title, quote=False)

    if f'<cite>{escaped_title}</cite>' in block and "published-entry" in block:
        # Distinguish an already-published entry from a locked listing.
        published_pattern = re.compile(
            r'<a class="published-entry"[^>]*>.*?<cite>' + re.escape(escaped_title) + r'</cite>.*?</a>',
            re.DOTALL,
        )
        if published_pattern.search(block):
            print(f"No change: Commentary is already published: {title}")
            return 0

    cleaned = remove_locked_item(block, title)
    published_entry = (
        f'\n            <a class="published-entry" href="{html.escape(href, quote=True)}">\n'
        f'              <span class="publication-access"><span class="access-icon unlocked" role="img" '
        f'aria-label="Publicly available" title="Publicly available">&#128275;</span></span>\n'
        f'              <span class="entry-type">{html.escape(code)} · {html.escape(date)}</span>\n'
        f'              <cite>{escaped_title}</cite>\n'
        f'              <span class="entry-author">{html.escape(author)}</span>\n'
        f'            </a>'
    )

    ol_pos = cleaned.find("<ol>")
    if ol_pos >= 0:
        new_block = cleaned[:ol_pos] + published_entry + "\n            " + cleaned[ol_pos:]
    else:
        new_block = cleaned + published_entry

    write_targeted(text, new_block)
    print(f"Published Commentary catalogue entry: {title}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate safe editing boundaries and exit")
    sub = parser.add_subparsers(dest="command")

    add = sub.add_parser("add-locked", help="Add one locked Commentary title")
    add.add_argument("title")

    pub = sub.add_parser("publish", help="Convert/add a Commentary title as a published entry")
    pub.add_argument("--title", required=True)
    pub.add_argument("--href", required=True)
    pub.add_argument("--code", required=True)
    pub.add_argument("--date", required=True)
    pub.add_argument("--author", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.check:
        return check()
    if args.command == "add-locked":
        return add_locked(args.title)
    if args.command == "publish":
        return publish(args.title, args.href, args.code, args.date, args.author)
    print("Choose --check, add-locked, or publish.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
